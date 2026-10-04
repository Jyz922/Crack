"""L4: Sense anchoring — evidence that two meanings are active in the text."""

from __future__ import annotations

import json
import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, NamedTuple

import anthropic
import google.genai as _genai
import google.genai.types as _genai_types
from google.genai.errors import ClientError as _GeminiClientError
from google.genai.errors import ServerError as _GeminiServerError
from pydantic import BaseModel, ConfigDict, ValidationError

from .config import DEFAULT_SETTINGS, Settings
from .enums import AnchorRelation, AnchoringStatus, DetectionStatus, Genre
from .schema import AnalysisRecord, CandidateAssessment, CandidateEntry, L4Attempt, L4CandidateFinding, L4Result, L4Search
from .validation import ModelResponseError, validate_l4_response, require_completion

_PROMPT_PATH = Path(__file__).parent / "prompts" / "l4_anchoring.md"
_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic response model — used as Gemini response_schema.
# ---------------------------------------------------------------------------

class _L4LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sense_a: str
    sense_a_anchor_quote: str
    sense_b: str
    sense_b_anchor_quote: str
    anchor_relation: AnchorRelation | None
    anchoring_status: AnchoringStatus
    resolving_sense: str | None
    reasoning: str
    target_term: str
    split_parts: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _align_substring(quote: str, text: str) -> str:
    """Optional alignment utility; live response validation uses exact raw quotes."""
    if not quote or not quote.strip():
        raise ModelResponseError("A source quote must not be empty")
    if quote in text:
        return quote
    for candidate in (quote, quote.strip(" \t\n\r\"'.,;:!?-")):
        if candidate and candidate.lower() in text.lower():
            index = text.lower().index(candidate.lower())
            return text[index:index + len(candidate)]
    raise ModelResponseError("Quote could not be aligned to the input")


def _render_l4_prompt(
    text: str,
    genre: Genre,
    candidate_term: str,
    candidate_details: str = "",
) -> str:
    variables = {
        "text": text,
        "genre": genre.value,
        "candidate_term": candidate_term,
        "candidate_details": candidate_details,
    }
    # Render the template once: placeholder-shaped text in an input must stay
    # literal, rather than being replaced by a later template variable.
    return re.sub(r"\{(\w+)\}", lambda m: variables.get(m.group(1), m.group(0)), _load_prompt())


def _extract_json(text: str) -> dict[str, Any]:
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        return json.loads(fence.group(1))
    return json.loads(text.strip())


# ---------------------------------------------------------------------------
# Backend round-trip calls
# ---------------------------------------------------------------------------

class _L4Call(NamedTuple):
    parsed: dict[str, Any] | None
    model_used: str
    fallback_used: bool
    retries: int


def _call_anthropic_l4(
    prompt_text: str,
    model: str,
    client: anthropic.Anthropic | None = None,
    response_log: list[str] | None = None,
    max_output_tokens: int = 4096,
) -> dict[str, Any] | None:
    if client is None:
        client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=max_output_tokens,
        messages=[{"role": "user", "content": prompt_text}],
    )
    raw = response.content[0].text
    if response_log is not None:
        response_log.append(raw)
    require_completion(getattr(response, "stop_reason", None))
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError, IndexError):
        return None


def _call_gemini_l4_single(
    prompt_text: str,
    model: str,
    client: _genai.Client,
    max_output_tokens: int,
    response_log: list[str] | None = None,
) -> tuple[dict[str, Any] | None, int, _GeminiClientError | None]:
    config = _genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_L4LLMResponse,
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
            raw = resp.text or ""
            if response_log is not None:
                response_log.append(raw)
            require_completion(getattr(candidate, "finish_reason", None))
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


def _call_gemini_l4(
    prompt_text: str,
    settings: Settings,
    client: _genai.Client | None,
    response_log: list[str] | None = None,
) -> _L4Call:
    if client is None:
        api_key, key_name = resolve_api_key("gemini", settings)
        if not api_key:
            raise ValueError(f"{key_name} not set")
        try:
            from google.genai import types
            client = _genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30000))
        except Exception:
            client = _genai.Client(api_key=api_key)

    models = [settings.L4_MODEL_GEMINI, *settings.L4_MODEL_GEMINI_CHAIN]
    total_retries = 0
    for idx, model in enumerate(models):
        parsed, retries, err_5xx = _call_gemini_l4_single(
            prompt_text, model, client, settings.L4_MAX_OUTPUT_TOKENS, response_log
        )
        total_retries += retries
        if parsed is not None:
            return _L4Call(parsed, model, idx > 0, total_retries)
        if err_5xx is None:
            return _L4Call(None, model, idx > 0, total_retries)
    return _L4Call(None, models[-1], True, total_retries)


from .providers import (
    PROVIDERS,
    call_openai_compatible,
    create_client,
    resolve_api_key,
    resolve_backend,
    resolve_model,
)


def _call_openai_l4(
    prompt_text: str,
    backend: str,
    settings: Settings,
    client: Any | None = None,
    response_log: list[str] | None = None,
) -> _L4Call:
    if client is None:
        client = create_client(backend, settings)
    model = resolve_model(backend, "L4", settings)
    parsed, retries, fallback_used = call_openai_compatible(
        client=client,
        model=model,
        prompt_text=prompt_text,
        max_output_tokens=settings.L4_MAX_OUTPUT_TOKENS,
        temperature=0.0,
        parse_attempts=1,
        response_observer=response_log.append if response_log is not None else None,
    )
    return _L4Call(parsed, model, fallback_used, retries)


def _complete_l4(
    prompt: str,
    settings: Settings,
    client: Any,
    response_log: list[str] | None = None,
) -> _L4Call:
    backend = resolve_backend(settings.L4_BACKEND, settings)

    if backend == "gemini":
        return _call_gemini_l4(prompt, settings, client, response_log)
    if backend == "anthropic":
        parsed = _call_anthropic_l4(
            prompt, settings.L4_MODEL_ANTHROPIC, client, response_log,
            max_output_tokens=settings.L4_MAX_OUTPUT_TOKENS,
        )
        return _L4Call(parsed, settings.L4_MODEL_ANTHROPIC, False, 0)
    if backend in PROVIDERS and PROVIDERS[backend].sdk_family == "openai":
        return _call_openai_l4(prompt, backend, settings, client, response_log)
    raise ValueError(f"Unknown L4_BACKEND: {settings.L4_BACKEND!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _anchor_shortlist(
    record: AnalysisRecord, genre: Genre, candidates: list[CandidateEntry],
    settings: Settings, client: Any,
) -> L4Result:
    """Compare the supplied shortlist in one request, then validate its target."""
    proposals = []
    for candidate in candidates:
        senses = []
        seen = set()
        for sense in record.l2_result.senses if record.l2_result else []:
            if sense.term.casefold() != candidate.term.casefold():
                continue
            key = (sense.source, sense.lemma, sense.sense_id)
            if key not in seen:
                seen.add(key)
                senses.append([sense.sense_id, sense.definition])
        proposals.append({"term": candidate.term,
                          "split_options": candidate.split_options,
                          "compound_split": candidate.score_components.get("compound_split") == 1.0,
                          "dictionary_proposals": senses})
    terms = [c.term for c in candidates]
    details = "Dictionary proposals are possibilities, not contextual evidence.\n" + json.dumps(proposals, ensure_ascii=False)
    prompt = _render_l4_prompt(record.text, genre, json.dumps(terms, ensure_ascii=False), details)
    log = L4Attempt(candidate_term=terms[0] if len(terms) == 1 else "", candidate_terms=terms,
                    attempt=1, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest())
    record.l4_attempts.append(log)
    try:
        call = _complete_l4(prompt, settings, client, log.raw_responses)
        log.model_used, log.provider_retries = call.model_used, call.retries
        log.fallback_used = call.fallback_used
        log.parsed_response = call.parsed if isinstance(call.parsed, dict) else None
        target = call.parsed.get("target_term") if isinstance(call.parsed, dict) else None
        candidate = next((c for c in candidates if isinstance(target, str)
                          and c.term.strip().casefold() == target.strip().casefold()), None)
        if candidate is None:
            raise ModelResponseError("L4 target_term must name a supplied shortlisted candidate")
        parsed = validate_l4_response(call.parsed, record.text, candidate.term,
            candidate.score_components.get("compound_split") == 1.0, candidate.split_options)
        result = L4Result(**parsed)
    except Exception as exc:
        log.error = f"{type(exc).__name__}: {exc}"
        raise
    log.candidate_term = result.target_term
    log.accepted = True
    return result


def anchor_l4(
    record: AnalysisRecord,
    settings: Settings = DEFAULT_SETTINGS,
    *,
    ambiguous_term: str | None = None,
    client: Any = None,
    diagnostics: dict[str, Any] | None = None,
    continue_search: bool = False,
) -> L4Result:
    """Choose and anchor the strongest target in one bounded shortlist request."""
    if record.l1_result is None:
        raise ValueError("L1 must run before L4: l1_result is None")
    if continue_search:
        raise ValueError("Candidate continuation is disabled; failed or unknown layers terminate the item")
    candidates = list(record.l3_result.candidates if record.l3_result else [])
    total = record.l3_result.total_terms if record.l3_result else None
    total = len(candidates) if total is None else total
    if len({c.term.casefold() for c in candidates}) != len(candidates):
        raise ValueError("L3 candidate terms must be unique")
    if total < len(candidates):
        raise ValueError("L3 total_terms is smaller than its available candidate list")
    budget = min(settings.L3_TOP_K, settings.L4_MAX_CANDIDATES)
    if ambiguous_term is not None:
        if candidates and not any(c.term == ambiguous_term for c in candidates):
            raise ValueError("The requested target must be among the supplied L3 candidates")
        candidates = [next((c for c in candidates if c.term == ambiguous_term),
                           CandidateEntry(term=ambiguous_term, score=0.0))]
        total, budget = 1, 1
    shortlist = candidates[:budget]
    search = L4Search(mode="target_only" if ambiguous_term is not None else "automatic",
                      candidate_budget=budget, retrieved_terms=total,
                      available_terms=len(candidates), untested_terms=total,
                      considered_terms=[c.term for c in shortlist])
    record.l4_search = search
    if not shortlist:
        search.stop_reason = "NO_CANDIDATES"
        return L4Result(sense_a="", sense_b="", sense_a_anchor_quote="", sense_b_anchor_quote="",
                        anchoring_status=AnchoringStatus.INSUFFICIENT_EVIDENCE,
                        reasoning="Lexical retrieval produced no candidates; no assessment was performed.")
    try:
        result = _anchor_shortlist(record, record.l1_result.genre, shortlist, settings, client)
    except Exception:
        search.stop_reason = "EXECUTION_FAILED"
        raise
    assessment = CandidateAssessment(term=result.target_term, l4_result=result.model_copy(deep=True),
                                     reason=result.reasoning)
    record.candidate_assessments.append(assessment)
    search.findings.append(L4CandidateFinding(term=result.target_term, status=result.anchoring_status))
    # Only the chosen finding has separately validated evidence. Other terms
    # were offered for comparison, not given manufactured individual verdicts.
    search.untested_terms = max(0, total - 1)
    if result.anchoring_status == AnchoringStatus.PASS:
        search.stop_reason = "PASS_FOUND"
    elif result.anchoring_status == AnchoringStatus.INSUFFICIENT_EVIDENCE:
        assessment.outcome = DetectionStatus.INSUFFICIENT_EVIDENCE
        search.stop_reason = "INSUFFICIENT_EVIDENCE"
    else:
        assessment.outcome = DetectionStatus.NON_PUN
        search.stop_reason = "CANDIDATES_REJECTED"
    if record.l3_result:
        record.l3_result.candidates = [c for c in candidates if c.term == result.target_term] + [
            c for c in candidates if c.term != result.target_term]
    if ambiguous_term is not None:
        search.stop_reason = "TARGET_ONLY"
    if diagnostics is not None:
        diagnostics["candidate_findings"] = [f.model_dump(mode="json") for f in search.findings]
        diagnostics["search"] = search.model_dump(mode="json")
    return result
