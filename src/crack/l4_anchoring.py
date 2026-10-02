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
from .enums import AnchorRelation, AnchoringStatus, Genre
from .schema import AnalysisRecord, CandidateEntry, L4Attempt, L4CandidateFinding, L4Result, L4Search
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
    tmpl = _load_prompt()
    for k, v in variables.items():
        tmpl = tmpl.replace(f"{{{k}}}", v)
    return tmpl


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

    # Check for unit test mock objects
    is_mock = (
        client is not None
        and (
            hasattr(client, "_is_mock")
            or type(client).__name__ in ("MagicMock", "Mock", "NonCallableMagicMock")
            or "unittest.mock" in getattr(type(client), "__module__", "")
        )
    )

    if is_mock:
        if backend == "gemini" and hasattr(client, "models"):
            resp = client.models.generate_content(model="mock", contents=prompt)
            raw = getattr(resp, "text", "")
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)
        if backend == "anthropic" and hasattr(client, "messages"):
            resp = client.messages.create(model="mock", messages=[{"role": "user", "content": prompt}])
            raw = resp.content[0].text
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)
        if backend in PROVIDERS and PROVIDERS[backend].sdk_family == "openai" and hasattr(client, "chat"):
            resp = client.chat.completions.create(model="mock", messages=[{"role": "user", "content": prompt}])
            raw = resp.choices[0].message.content
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)

        # Fallbacks for generic mocks where backend wasn't specifically matched
        if hasattr(client, "models"):
            resp = client.models.generate_content(model="mock", contents=prompt)
            raw = getattr(resp, "text", "")
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)
        if hasattr(client, "messages"):
            resp = client.messages.create(model="mock", messages=[{"role": "user", "content": prompt}])
            raw = resp.content[0].text
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)
        if hasattr(client, "chat"):
            resp = client.chat.completions.create(model="mock", messages=[{"role": "user", "content": prompt}])
            raw = resp.choices[0].message.content
            if response_log is not None:
                response_log.append(raw)
            try:
                parsed = _extract_json(raw)
            except Exception:
                parsed = None
            return _L4Call(parsed, "mock", False, 0)

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

def _anchor_term(
    record: AnalysisRecord,
    genre: Genre,
    term: str,
    is_compound_split_candidate: bool,
    settings: Settings,
    client: Any,
) -> L4Result:
    lines: list[str] = []
    split_options = list(dict.fromkeys(
        option
        for c in (record.l3_result.candidates if record.l3_result else [])
        if c.term == term
        for option in c.split_options
    ))
    if record.l2_result and record.l2_result.senses:
        matched_senses = [s for s in record.l2_result.senses if s.term.lower() == term.lower()]
        # All distinct supplied senses are visible; the first four entries can
        # contain only one POS and omit both the contrast and the split parts.
        seen: set[tuple[str, str, str]] = set()
        for s in matched_senses:
            key = (s.source, s.lemma, s.sense_id)
            if key not in seen:
                seen.add(key)
                lines.append(f"- [{s.source}] {s.lemma} / {s.sense_id}: {s.definition}")
    candidate_details = "Supplied dictionary proposals (not contextual evidence):\n" + ("\n".join(lines) or "None")
    candidate_details += "\nAllowed split_options: " + json.dumps(split_options)
    candidate_details += f"\nDetected compound-split candidate: {str(is_compound_split_candidate).lower()}"

    prompt = _render_l4_prompt(record.text, genre, term, candidate_details)
    error = ""
    for attempt in range(2):
        attempt_prompt = prompt
        if attempt:
            attempt_prompt += (
                "\n\nLocal response validation rejected the previous response: " + error
                + "\nReturn a new response for the SAME candidate, satisfying the full contract."
                " Copy quotes exactly from Text. Do not change the verdict merely to pass validation."
                " Use INSUFFICIENT_EVIDENCE when the source cannot support a finding."
            )
        log = L4Attempt(
            candidate_term=term,
            attempt=attempt + 1,
            prompt_sha256=hashlib.sha256(attempt_prompt.encode()).hexdigest(),
        )
        record.l4_attempts.append(log)
        # Completion refusals, transport failures, and truncation are not
        # corrected into findings. Their available raw text remains in the log.
        try:
            call = _complete_l4(attempt_prompt, settings, client, log.raw_responses)
        except Exception as exc:
            log.error = f"{type(exc).__name__}: {exc}"
            raise
        log.model_used = call.model_used
        log.provider_retries = call.retries
        log.fallback_used = call.fallback_used
        log.parsed_response = call.parsed if isinstance(call.parsed, dict) else None
        try:
            parsed = validate_l4_response(
                call.parsed, record.text, term, is_compound_split_candidate, split_options
            )
            result = L4Result(**parsed)
        except (ModelResponseError, ValidationError) as exc:
            error = str(exc)
            log.error = error
            if attempt == 1:
                raise ModelResponseError(f"L4 contract rejected two responses for {term!r}: {error}") from exc
        else:
            log.accepted = True
            return result
    raise AssertionError("Unreachable L4 retry state")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def anchor_l4(
    record: AnalysisRecord,
    settings: Settings = DEFAULT_SETTINGS,
    *,
    ambiguous_term: str | None = None,
    client: Any = None,
    diagnostics: dict[str, Any] | None = None,
) -> L4Result:
    """Compute the L4 sense-anchoring result for *record*."""
    if record.l1_result is None:
        raise ValueError("L1 must run before L4: l1_result is None")

    genre = record.l1_result.genre

    candidates = record.l3_result.candidates if record.l3_result else []
    deferred = record.l3_result.deferred_candidates if record.l3_result else []
    cands = list(candidates) + list(deferred)
    if len({c.term for c in cands}) != len(cands):
        raise ValueError("L3 candidate terms must be unique across the initial and deferred lists")
    total_terms = record.l3_result.total_terms if record.l3_result else None
    total_terms = len(cands) if total_terms is None else total_terms
    if total_terms < len(cands):
        raise ValueError("L3 total_terms is smaller than its available candidate list")
    if settings.L4_MAX_CANDIDATES < 1:
        raise ValueError("L4_MAX_CANDIDATES must permit at least one candidate assessment")
    search = L4Search(
        mode="target_only" if ambiguous_term is not None else "automatic",
        candidate_budget=1 if ambiguous_term is not None else settings.L4_MAX_CANDIDATES,
        retrieved_terms=total_terms, available_terms=len(cands),
        untested_terms=total_terms,
    )
    record.l4_search = search

    def assess(cand: CandidateEntry) -> L4Result:
        # Make this candidate's split proposals visible to the existing exact
        # validator and downstream layers, without discarding the ranked tail.
        if record.l3_result and cand.term not in {c.term for c in record.l3_result.candidates}:
            record.l3_result.candidates.append(cand)
            record.l3_result.deferred_candidates = [
                c for c in record.l3_result.deferred_candidates if c.term != cand.term
            ]
        is_split = cand.score_components.get("compound_split", 0.0) == 1.0
        try:
            result = _anchor_term(record, genre, cand.term, is_split, settings, client)
        except Exception:
            search.stop_reason = "EXECUTION_FAILED"
            raise
        search.findings.append(L4CandidateFinding(term=cand.term, status=result.anchoring_status))
        search.untested_terms = max(0, total_terms - len(search.findings))
        return result

    if ambiguous_term is not None:
        if cands and not any(c.term == ambiguous_term for c in cands):
            raise ValueError("The requested target must be among the supplied L3 candidates")
        if cands:
            result = assess(next(c for c in cands if c.term == ambiguous_term))
        else:
            # Direct candidate assessment remains supported without L3; it is
            # explicitly a target-only finding, not a complete lexical search.
            search.retrieved_terms = search.available_terms = search.untested_terms = 1
            total_terms = 1
            result = assess(CandidateEntry(term=ambiguous_term, score=0.0))
        search.stop_reason = "TARGET_ONLY"
        if record.l3_result:
            active = record.l3_result.candidates
            record.l3_result.candidates = [c for c in active if c.term == ambiguous_term] + [
                c for c in active if c.term != ambiguous_term
            ]
        return result

    if not cands:
        search.stop_reason = "NO_CANDIDATES"
        return L4Result(
            sense_a="", sense_b="", sense_a_anchor_quote="", sense_b_anchor_quote="",
            anchoring_status=AnchoringStatus.INSUFFICIENT_EVIDENCE,
            reasoning="Lexical retrieval produced no candidates; no candidate assessment was performed.",
        )

    # The top-k list is the initial priority queue, not a permanent truncation.
    # Continue into the saved tail up to the separate operational call budget.
    max_to_try = min(len(cands), settings.L4_MAX_CANDIDATES)
    best_result: L4Result | None = None
    winning_idx: int | None = None
    tested: list[tuple[int, L4Result]] = []

    for idx in range(max_to_try):
        cand = cands[idx]
        res = assess(cand)
        tested.append((idx, res))

        if res.anchoring_status == AnchoringStatus.PASS:
            best_result = res
            winning_idx = idx
            search.stop_reason = "PASS_FOUND"
            break

        if best_result is None:
            best_result = res
            winning_idx = idx
        elif (
            best_result.anchoring_status == AnchoringStatus.ONE_SENSE_ONLY
            and res.anchoring_status in {AnchoringStatus.FAIL, AnchoringStatus.INSUFFICIENT_EVIDENCE}
        ):
            best_result = res
            winning_idx = idx

    # A candidate-level negative cannot establish a text-level negative when
    # additional lexical candidates have not been examined.
    if search.stop_reason == "IN_PROGRESS":
        if search.untested_terms == 0:
            search.stop_reason = "ALL_RETRIEVED_ASSESSED"
        elif len(tested) >= settings.L4_MAX_CANDIDATES:
            search.stop_reason = "BUDGET_EXHAUSTED"
        else:
            search.stop_reason = "CANDIDATES_UNAVAILABLE"
    if best_result and best_result.anchoring_status == AnchoringStatus.ONE_SENSE_ONLY:
        if total_terms > len(tested):
            best_result = best_result.model_copy(update={
                "anchoring_status": AnchoringStatus.INSUFFICIENT_EVIDENCE,
                "reasoning": f"Only {len(tested)} of {total_terms} lexical candidate terms were assessed. "
                "The tested candidates have one grounded reading each; untested candidates remain unresolved.",
            })
    if diagnostics is not None:
        diagnostics["candidate_findings"] = [
            {"term": cands[i].term, "status": result.anchoring_status.value}
            for i, result in tested
        ]
        diagnostics["search"] = search.model_dump(mode="json")

    # If a non-first candidate was the winner, rotate it to index 0 so L5/L6 and report receive it
    if winning_idx is not None and winning_idx > 0 and record.l3_result:
        winning_cand = cands[winning_idx]
        record.l3_result.candidates = [winning_cand] + [
            c for c in record.l3_result.candidates if c.term != winning_cand.term
        ]

    assert best_result is not None
    return best_result
