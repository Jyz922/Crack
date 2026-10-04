"""Local age evidence and compact L6 instructions; no extra model requests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .config import Settings
from .l2_senses import AOA_CSV, STOPWORDS, aoa_lookup
from .schema import AgeEstimate, AnalysisRecord
from .validation import ModelResponseError, require_fields, require_text

AGE_RESPONSE_CONTRACT_VERSION = "3"
AGE_AGGREGATION_VERSION = "4"
AOA_SOURCE = "Kuperman word-level AoA (shared frozen CSV)"
ASSESSMENT_BASIS = "Contextual model estimate; AoA citations are word-level ratings, not measured sense acquisition or child comprehension."


def age_inputs(record: AnalysisRecord) -> dict[str, Any]:
    if record.l4_result is None or not record.l4_result.sense_a or not record.l4_result.sense_b:
        raise ModelResponseError("Age assessment requires two validated readings")
    if not record.target_ages or len(set(record.target_ages)) != len(record.target_ages):
        raise ModelResponseError("Age assessment requires distinct explicit target ages")
    l4 = record.l4_result
    words = set(t.lower() for t in (record.l1_result.tokens if record.l1_result else []))
    # The input table covers the whole sentence, including non-target vocabulary.
    words.update(part.lower() for part in l4.split_parts)
    required = set(l4.target_term.lower().split()) | set(part.lower() for part in l4.split_parts)
    words.update(required)
    table = []
    for word in sorted(words):
        value, match = aoa_lookup(word)
        table.append({"word": word, "aoa": value, "match": match, "source": AOA_SOURCE})
    return {"text": record.text, "target": l4.target_term,
            "meanings": [{"definition": l4.sense_a, "quote": l4.sense_a_anchor_quote},
                         {"definition": l4.sense_b, "quote": l4.sense_b_anchor_quote}],
            "split_parts": l4.split_parts, "target_ages": record.target_ages,
            "mandatory_vocabulary": sorted(required), "aoa_lookup": table}


def resource_sha256() -> str:
    return hashlib.sha256(AOA_CSV.read_bytes()).hexdigest()


def compact_age_prompt(record: AnalysisRecord) -> str:
    """Add a small age task to L6; never start another model call."""
    if not record.target_ages:
        return "\nNo age assessment requested. Set age_assessment to null."
    try:
        payload = age_inputs(record)
    except Exception as exc:
        record.age_preparation_error = f"{type(exc).__name__}: {exc}"
        return "\nAge evidence preparation failed. Set age_assessment to null; complete the detection task."
    record.age_preparation_error = None
    ratings = [[e["word"], e["aoa"], e["match"]] for e in payload["aoa_lookup"]
               if e["word"] not in STOPWORDS or e["word"] in payload["mandatory_vocabulary"]]
    return ("\n\nAssess these ages in the SAME response only if the readings are SENSES_DISTINCT. "
            "Otherwise set age_assessment to null. Ratings are word-level AoA, not measured "
            "acquisition ages of the two senses. Null ratings stay unknown; ordinary contextual "
            "familiarity estimates are allowed. Do not invent numeric sense ages or prerequisites. "
            "Keep each age reason to one short sentence.\n"
            "age_assessment: object with exactly the requested age-string keys. Each value has "
            "understanding (LIKELY/UNLIKELY/UNKNOWN), barrier (vocabulary/sense_a/sense_b/wordplay/background_knowledge "
            "for UNLIKELY, otherwise null), content_appropriate and inference_appropriate "
            "(true/false/null), reason (nonempty string), content_quote (exact source substring "
            "for content false, otherwise empty), prerequisite (named concept for inference false, "
            "otherwise empty). Distinguish knowing a word from knowing its specific meaning. "
            "Use sense_a or sense_b when that contextual meaning is the barrier; vocabulary "
            "means wider sentence vocabulary. Short wording and familiar surface words alone "
            "do not establish understanding of figurative, idiomatic or specialist meanings. "
            "Consider the actual readings and whole text. Do not equate "
            "missing ratings with difficulty, or a topic word with inappropriate content. "
            "Use UNKNOWN/null when the evidence is inadequate.\n"
            + json.dumps({"target_ages": record.target_ages,
                          "word_ratings_word_aoa_match": ratings}, ensure_ascii=False))


def shared_age_estimates(record: AnalysisRecord) -> dict[int, AgeEstimate]:
    """Validate L6's cached age answer without repairing or calling a model."""
    if record.l6_result is None:
        raise ModelResponseError("Age assessment requires a completed L6 result")
    raw = require_ages(record.l6_result.age_assessment, record.target_ages, "age_assessment")
    estimates = {}
    for age, value in raw.items():
        estimate = AgeEstimate.model_validate(value)
        require_text(estimate.reason, "age reason")
        if (estimate.understanding == "UNLIKELY") != (estimate.barrier is not None):
            raise ModelResponseError("Only an UNLIKELY understanding finding requires a named barrier")
        estimates[int(age)] = estimate
    return estimates


def require_ages(value: Any, ages: list[int], field: str) -> dict[str, Any]:
    return require_fields(value, {str(a) for a in ages})


def require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise ModelResponseError(f"{field} must be an array")
    for entry in value:
        require_text(entry, field)
    return value


def call_age_model(record: AnalysisRecord, settings: Settings, layer: str,
                   payload: dict[str, Any], validator: Callable[[dict], Any], client: Any = None) -> Any:
    """Historical entry point; production age assessment never calls a model."""
    raise ModelResponseError("Standalone age calls are disabled; age layers reuse the L6 response")
