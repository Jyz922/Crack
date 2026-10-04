"""L6: Sense-distinctness and lexical-granularity check.

L6 confirms that the two meanings anchored by L4 represent genuinely distinct
conceptual interpretations rather than subtle nuances of the same underlying sense.
Supports all major providers via the unified provider abstraction.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import google.genai as _genai
import google.genai.types as _genai_types
from google.genai.errors import ClientError as _GeminiClientError
from google.genai.errors import ServerError as _GeminiServerError
from pydantic import BaseModel, ConfigDict

from .config import DEFAULT_SETTINGS, Settings
from .enums import AmbiguityAblation, AnchoringStatus, DistinctnessStatus, Genre
from .providers import (
    PROVIDERS,
    call_openai_compatible,
    create_client,
    resolve_api_key,
    resolve_backend,
    resolve_model,
)
from .schema import AgeEstimate, AnalysisRecord, L6Result
from .age_evidence import compact_age_prompt
from .validation import ModelResponseError, validate_l6_response, require_completion

_LOG = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "l6_distinctness.md"


# ---------------------------------------------------------------------------
# Structured LLM response schema
# ---------------------------------------------------------------------------

class _L6LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sense_a_paraphrase: str
    sense_b_paraphrase: str
    suppresses_other: bool | None
    materially_different: bool | None
    distinctness_status: DistinctnessStatus
    ambiguity_ablation: AmbiguityAblation
    explanation: str
    age_assessment: dict[str, AgeEstimate] | None = None


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def _render_l6_prompt(
    text: str,
    genre: Genre,
    term: str,
    sense_a: str,
    anchor_a: str,
    sense_b: str,
    anchor_b: str,
) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    mapping = {
        "text": text,
        "genre": genre.value,
        "term": term,
        "sense_a": sense_a,
        "anchor_a": anchor_a,
        "sense_b": sense_b,
        "anchor_b": anchor_b,
    }
    return re.sub(r"\{(\w+)\}", lambda m: str(mapping.get(m.group(1), m.group(0))), template)


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

@dataclass
class _L6Call:
    parsed: dict[str, Any] | None
    model_used: str
    fallback_used: bool
    retries: int


def _call_anthropic_l6(
    prompt_text: str,
    model: str,
    client: anthropic.Anthropic | None = None,
    max_output_tokens: int = 4096,
) -> dict[str, Any] | None:
    if client is None:
        client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        messages=[{"role": "user", "content": prompt_text}],
    )
    require_completion(getattr(response, "stop_reason", None))
    raw = response.content[0].text
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError, IndexError):
        return None


def _call_gemini_l6_single(
    prompt_text: str,
    model: str,
    client: _genai.Client,
    max_output_tokens: int,
) -> tuple[dict[str, Any] | None, int, _GeminiClientError | None]:
    config = _genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_L6LLMResponse,
        temperature=0.0,
        max_output_tokens=max_output_tokens,
    )
    retries = 0
    delays = (2, 4, 8)
    for attempt in range(len(delays) + 1):
        if attempt > 0:
            time.sleep(delays[attempt - 1])
            retries += 1
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt_text, config=config
            )
            candidate = resp.candidates[0] if getattr(resp, "candidates", None) else None
            require_completion(getattr(candidate, "finish_reason", None))
            raw = resp.text
            try:
                return _extract_json(raw), retries, None
            except (json.JSONDecodeError, ValueError, IndexError):
                return None, retries, None
        except _GeminiServerError as e:
            if attempt == len(delays):
                return None, retries, e
        except _GeminiClientError:
            raise
    return None, retries, None


def _call_gemini_l6(
    prompt_text: str,
    settings: Settings,
    client: _genai.Client | None,
) -> _L6Call:
    if client is None:
        api_key, key_name = resolve_api_key("gemini", settings)
        if not api_key:
            raise ValueError(f"{key_name} not set")
        try:
            from google.genai import types
            client = _genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
        except Exception:
            client = _genai.Client(api_key=api_key)

    models = [settings.L6_MODEL_GEMINI, *settings.L6_MODEL_GEMINI_CHAIN]
    total_retries = 0
    for idx, model in enumerate(models):
        parsed, retries, err_5xx = _call_gemini_l6_single(
            prompt_text, model, client, settings.L6_MAX_OUTPUT_TOKENS
        )
        total_retries += retries
        if parsed is not None:
            return _L6Call(parsed, model, idx > 0, total_retries)
        if err_5xx is None:
            return _L6Call(None, model, idx > 0, total_retries)
        if idx < len(models) - 1:
            _LOG.warning("L6 Gemini fallback: %s -> %s", model, models[idx + 1])
        else:
            raise RuntimeError(f"L6 Gemini exhausted models, last HTTP {err_5xx.code}") from err_5xx

    return _L6Call(None, models[-1], True, total_retries)


def _call_openai_l6(
    prompt_text: str,
    backend: str,
    settings: Settings,
    client: Any | None = None,
) -> _L6Call:
    if client is None:
        client = create_client(backend, settings)
    model = resolve_model(backend, "L6", settings)
    parsed, retries, fallback_used = call_openai_compatible(
        client=client,
        model=model,
        prompt_text=prompt_text,
        max_output_tokens=settings.L6_MAX_OUTPUT_TOKENS,
        temperature=0.0,
        parse_attempts=1,
    )
    return _L6Call(parsed, model, fallback_used, retries)


def _complete_l6(
    prompt: str,
    settings: Settings,
    client: Any,
) -> _L6Call:
    backend = resolve_backend(settings.L6_BACKEND, settings)

    if backend == "gemini":
        return _call_gemini_l6(prompt, settings, client)
    if backend == "anthropic":
        parsed = _call_anthropic_l6(prompt, settings.L6_MODEL_ANTHROPIC, client, settings.L6_MAX_OUTPUT_TOKENS)
        return _L6Call(parsed, settings.L6_MODEL_ANTHROPIC, False, 0)
    if backend in PROVIDERS and PROVIDERS[backend].sdk_family == "openai":
        return _call_openai_l6(prompt, backend, settings, client)
    raise ValueError(f"Unknown L6_BACKEND: {settings.L6_BACKEND!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def distinctness_l6(
    record: AnalysisRecord,
    settings: Settings = DEFAULT_SETTINGS,
    *,
    client: Any = None,
) -> L6Result:
    """Compute the L6 sense-distinctness result for *record*."""
    # 1. Guard: L4 must have completed and passed anchoring
    if record.l4_result is None or record.l4_result.anchoring_status != AnchoringStatus.PASS:
        status_desc = record.l4_result.anchoring_status.value if record.l4_result else "None"
        return L6Result(
            distinctness_status=DistinctnessStatus.L6_SKIPPED_NO_PARAPHRASE,
            ambiguity_ablation=AmbiguityAblation.SKIPPED,
            explanation=f"L4 anchoring was not PASS ({status_desc}); distinctness check skipped.",
        )

    l4 = record.l4_result
    term = l4.target_term
    if not term:
        raise ModelResponseError("L6 requires L4's explicit assessed target")

    genre = record.l1_result.genre if record.l1_result else Genre.DECLARATIVE
    prompt = _render_l6_prompt(
        text=record.text,
        genre=genre,
        term=term,
        sense_a=l4.sense_a,
        anchor_a=l4.sense_a_anchor_quote,
        sense_b=l4.sense_b,
        anchor_b=l4.sense_b_anchor_quote,
    )
    prompt += compact_age_prompt(record)

    call = _complete_l6(prompt, settings, client)
    if call.parsed is None:
        raise ModelResponseError("L6 did not return a valid JSON response")
    parsed = validate_l6_response(call.parsed)
    return L6Result(**parsed, age_assessment=call.parsed.get("age_assessment"))
