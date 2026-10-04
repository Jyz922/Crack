"""Executable contracts for model responses. No semantic verdict is inferred here."""

from __future__ import annotations

import math
from typing import Any

from .enums import AnchorRelation, AnchoringStatus, DistinctnessStatus, AmbiguityAblation


RESPONSE_CONTRACT_VERSION = "6"

L4_RESPONSE_FIELDS = frozenset({
    "sense_a", "sense_b", "sense_a_anchor_quote", "sense_b_anchor_quote",
    "anchor_relation", "anchoring_status", "resolving_sense", "reasoning",
    "target_term", "split_parts",
})


class ModelResponseError(ValueError):
    """A model response cannot safely be used as a stage result."""


def require_completion(reason: Any) -> None:
    """Reject truncation, refusal, and other incomplete terminal states."""
    if reason is None:
        return  # Some compatible endpoints omit completion metadata.
    name = getattr(reason, "value", reason)
    if str(name).lower() not in {"stop", "end_turn"}:
        raise ModelResponseError(f"Model response did not complete normally: {name}")


def require_fields(value: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelResponseError("Expected a JSON object")
    missing = fields - value.keys()
    extra = value.keys() - fields
    if missing or extra:
        raise ModelResponseError(f"Response fields: missing={sorted(missing)}, unexpected={sorted(extra)}")
    return value


def require_text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ModelResponseError(f"{field} must be a {'string' if allow_empty else 'nonempty string'}")
    return value


def source_quote(value: Any, text: str, field: str) -> str:
    """Accept only an actual source substring; never substitute guessed evidence."""
    quote = require_text(value, field, allow_empty=True)
    if quote and (not quote.strip() or quote not in text):
        raise ModelResponseError(f"{field} is not a nonblank verbatim substring of the input")
    return quote


def validate_l4_response(
    value: Any, text: str, term: str, is_split: bool,
    split_options: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    p = require_fields(value, set(L4_RESPONSE_FIELDS))
    target = require_text(p["target_term"], "target_term")
    if target.strip().casefold() != term.strip().casefold():
        raise ModelResponseError(
            f"target_term must equal the supplied candidate {term!r} "
            "apart from letter case and surrounding whitespace"
        )
    parts = p["split_parts"]
    if not isinstance(parts, list) or any(not isinstance(part, str) or not part for part in parts):
        raise ModelResponseError("split_parts must be a JSON array of nonempty strings")
    try:
        status = AnchoringStatus(p["anchoring_status"])
        relation = AnchorRelation(p["anchor_relation"]) if p["anchor_relation"] is not None else None
    except (ValueError, TypeError) as exc:
        raise ModelResponseError("Unknown L4 status or anchor relation") from exc
    require_text(p["reasoning"], "reasoning")
    a = require_text(p["sense_a"], "sense_a", allow_empty=True)
    b = require_text(p["sense_b"], "sense_b", allow_empty=True)
    qa = source_quote(p["sense_a_anchor_quote"], text, "sense_a_anchor_quote")
    qb = source_quote(p["sense_b_anchor_quote"], text, "sense_b_anchor_quote")
    if status == AnchoringStatus.PASS:
        if not all(s.strip() for s in (a, b, qa, qb)):
            raise ModelResponseError("L4 PASS requires two meanings and two source anchors")
        if a.strip().casefold() == b.strip().casefold():
            raise ModelResponseError("L4 PASS cannot claim identical meanings")
        if p["resolving_sense"] not in ("sense_a", "sense_b") or relation is None:
            raise ModelResponseError("L4 PASS requires an explicit resolving sense and relation")
        if relation == AnchorRelation.RESEGMENTATION:
            if not is_split or qa.casefold() != term.casefold() or qb.casefold() != term.casefold():
                raise ModelResponseError("Split anchors must name a detected compound-split candidate")
            if tuple(parts) not in (split_options or []) or "".join(parts).casefold() != term.casefold():
                raise ModelResponseError("split_parts must equal a supplied segmentation of the candidate")
        elif qa.casefold() == qb.casefold() or any(q.strip().casefold() == term.casefold() for q in (qa, qb)):
            raise ModelResponseError("Non-split anchors must be different context spans, not just the candidate word")
        if relation != AnchorRelation.RESEGMENTATION and parts:
            raise ModelResponseError("Non-split findings require empty split_parts")
    else:
        if relation is not None or p["resolving_sense"] is not None or parts:
            raise ModelResponseError("Non-PASS status contradicts a claimed resolving sense or relation")
        if status == AnchoringStatus.ONE_SENSE_ONLY and not ((a.strip() and qa) or (b.strip() and qb)):
            raise ModelResponseError("ONE_SENSE_ONLY requires an identified meaning with source evidence")
    # Canonicalize only a verified candidate identifier. Leave the caller's
    # raw/parsed response and every source quote unchanged for auditing.
    return {**p, "target_term": term}


def validate_l5_response(value: Any, score_keys: set[str]) -> dict[str, Any]:
    p = require_fields(value, score_keys | {"evidence_sufficient", "context_consistent", "reasoning"})
    if type(p["evidence_sufficient"]) is not bool:
        raise ModelResponseError("evidence_sufficient must be a JSON boolean")
    require_text(p["reasoning"], "reasoning")
    if p["evidence_sufficient"]:
        if type(p["context_consistent"]) is not bool:
            raise ModelResponseError("An assessed L5 response requires a boolean context_consistent")
    elif p["context_consistent"] is not None:
        raise ModelResponseError("Insufficient evidence requires null context_consistent")
    for key in score_keys:
        score = p[key]
        if not p["evidence_sufficient"]:
            if score is not None:
                raise ModelResponseError("Insufficient evidence requires null scores")
        elif type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ModelResponseError(f"{key} must be a finite number between 0 and 1")
    return p


def validate_l6_response(value: Any) -> dict[str, Any]:
    # Age evidence is checked separately by the age layers. Its absence or
    # malformed content must not become a detection failure.
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "age_assessment"}
    p = require_fields(value, {
        "sense_a_paraphrase", "sense_b_paraphrase", "suppresses_other", "materially_different",
        "distinctness_status", "ambiguity_ablation", "explanation",
    })
    require_text(p["explanation"], "explanation")
    a = require_text(p["sense_a_paraphrase"], "sense_a_paraphrase", allow_empty=True)
    b = require_text(p["sense_b_paraphrase"], "sense_b_paraphrase", allow_empty=True)
    try:
        status = DistinctnessStatus(p["distinctness_status"])
        ablation = AmbiguityAblation(p["ambiguity_ablation"])
    except (ValueError, TypeError) as exc:
        raise ModelResponseError("Unknown L6 status or ablation result") from exc
    flags = (p["suppresses_other"], p["materially_different"])
    if p["suppresses_other"] is not None and type(p["suppresses_other"]) is not bool:
        raise ModelResponseError("suppresses_other must be a boolean or null diagnostic")
    if status == DistinctnessStatus.L6_SKIPPED_NO_PARAPHRASE:
        if flags != (None, None) or ablation != AmbiguityAblation.SKIPPED:
            raise ModelResponseError("An unassessed L6 result requires null flags and SKIPPED ablation")
    else:
        if not a.strip() or not b.strip() or type(p["materially_different"]) is not bool:
            raise ModelResponseError("An assessed L6 result requires paraphrases and a material-difference finding")
        if status == DistinctnessStatus.SENSES_DISTINCT:
            if not p["materially_different"] or a.strip().casefold() == b.strip().casefold():
                raise ModelResponseError("SENSES_DISTINCT contradicts the paraphrases or material difference")
        elif p["materially_different"] or ablation == AmbiguityAblation.SUPPORTED:
            raise ModelResponseError("SENSES_TOO_CLOSE contradicts distinctness or supported ablation")
    return p
