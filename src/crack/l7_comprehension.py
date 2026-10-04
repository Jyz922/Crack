"""L7: contextual comprehension estimates with checked word-level evidence."""
from __future__ import annotations

from typing import Any

from .age_evidence import (AGE_AGGREGATION_VERSION, AGE_RESPONSE_CONTRACT_VERSION, ASSESSMENT_BASIS, age_inputs,
                           shared_age_estimates, require_ages, require_string_list, resource_sha256)
from .config import DEFAULT_SETTINGS, Settings
from .enums import ComprehensionStatus
from .schema import AgeComprehensionEvidence, AgeComprehensionSummary, AnalysisRecord, AoAEvidence, L7Result
from .validation import ModelResponseError, require_fields, require_text

DIMENSIONS = ("vocabulary", "sense_a", "sense_b", "wordplay", "background_knowledge")


def comprehension_status(details: AgeComprehensionEvidence) -> ComprehensionStatus:
    """A reported barrier can block full understanding despite other unknowns.

    UNKNOWN alone never establishes a barrier. A negative summary identifies
    an estimated difficulty, not complete knowledge about the remaining axes.
    """
    values = [getattr(details, d) for d in DIMENSIONS]
    if all(v == "LIKELY" for v in values):
        return ComprehensionStatus.FULLY_COMPREHENSIBLE
    if "UNLIKELY" not in values:
        return ComprehensionStatus.AOA_UNKNOWN
    if details.vocabulary == details.sense_a == "LIKELY" and details.sense_b == "UNLIKELY":
        return ComprehensionStatus.SENSE_B_TOO_ADVANCED
    if details.vocabulary == details.sense_a == details.sense_b == "LIKELY":
        return ComprehensionStatus.WORDPLAY_SKILL_TOO_ADVANCED
    return ComprehensionStatus.PARTIALLY_COMPREHENSIBLE


def summarize_comprehension(details: AgeComprehensionEvidence) -> AgeComprehensionSummary:
    """Preserve both kinds of evidence; no age value or model finding is filled in."""
    unknowns = [d for d in DIMENSIONS if getattr(details, d) == "UNKNOWN"]
    return AgeComprehensionSummary(
        status=comprehension_status(details),
        barrier_dimensions=[d for d in DIMENSIONS if getattr(details, d) == "UNLIKELY"],
        unknown_dimensions=unknowns, fully_assessed=not unknowns)


def validate_l7(value: Any, payload: dict) -> L7Result:
    data = require_fields(value, {"required_vocabulary", "aoa_evidence", "per_age_details", "explanation"})
    required = require_string_list(data["required_vocabulary"], "required_vocabulary")
    if len(set(required)) != len(required) or not set(payload["mandatory_vocabulary"]).issubset(required):
        raise ModelResponseError("Required vocabulary must be unique and include the target and split parts")
    if not isinstance(data["aoa_evidence"], list):
        raise ModelResponseError("aoa_evidence must be an array")
    citations = []
    for entry in data["aoa_evidence"]:
        require_fields(entry, {"word", "aoa", "match", "source"})
        if isinstance(entry["aoa"], bool) or entry not in payload["aoa_lookup"]:
            raise ModelResponseError("AoA citation must exactly match a supplied table entry, including nulls")
        citations.append(AoAEvidence.model_validate(entry))
    if len(citations) != len(required) or {e.word for e in citations} != set(required):
        raise ModelResponseError("Every required word needs exactly one table citation")
    by_age = require_ages(data["per_age_details"], payload["target_ages"], "per_age_details")
    details = {}
    for age, entry in by_age.items():
        require_fields(entry, {*DIMENSIONS, "prerequisites", "reason"})
        require_string_list(entry["prerequisites"], "prerequisites")
        require_text(entry["reason"], "age reasoning")
        detail = AgeComprehensionEvidence.model_validate(entry)
        details[int(age)] = detail
    require_text(data["explanation"], "explanation")
    summaries = {age: summarize_comprehension(detail) for age, detail in details.items()}
    return L7Result(required_vocabulary=required, aoa_evidence=citations,
                    per_age_details=details,
                    per_age_summaries=summaries, aggregation_version=AGE_AGGREGATION_VERSION,
                    per_age_comprehension={a: summary.status for a, summary in summaries.items()},
                    explanation=data["explanation"], assessment_basis=ASSESSMENT_BASIS,
                    aoa_resource_sha256=resource_sha256())


def assess_l7(record: AnalysisRecord, settings: Settings = DEFAULT_SETTINGS,
              client: Any = None) -> L7Result:
    record.age_validation_version = AGE_RESPONSE_CONTRACT_VERSION
    record.age_aggregation_version = AGE_AGGREGATION_VERSION
    if record.age_preparation_error:
        raise ModelResponseError(record.age_preparation_error)
    payload = age_inputs(record)
    estimates = shared_age_estimates(record)
    statuses = {}
    summaries = {}
    for age, estimate in estimates.items():
        status = (ComprehensionStatus.FULLY_COMPREHENSIBLE if estimate.understanding == "LIKELY" else
                  ComprehensionStatus.AOA_UNKNOWN if estimate.understanding == "UNKNOWN" else
                  ComprehensionStatus.SENSE_B_TOO_ADVANCED if estimate.barrier == "sense_b" else
                  ComprehensionStatus.PARTIALLY_COMPREHENSIBLE if estimate.barrier in {"vocabulary", "sense_a"} else
                  ComprehensionStatus.WORDPLAY_SKILL_TOO_ADVANCED)
        statuses[age] = status
        summaries[age] = AgeComprehensionSummary(status=status,
            barrier_dimensions=[estimate.barrier] if estimate.barrier else [],
            unknown_dimensions=["understanding"] if estimate.understanding == "UNKNOWN" else [],
            fully_assessed=estimate.understanding != "UNKNOWN")
    # Citations are copied by code from the local lookup, never generated by
    # the model. No word rating is promoted into a measured sense age.
    return L7Result(per_age_comprehension=statuses, per_age_estimates=estimates,
                    per_age_summaries=summaries, aggregation_version=AGE_AGGREGATION_VERSION,
                    required_vocabulary=[e["word"] for e in payload["aoa_lookup"]],
                    aoa_evidence=[AoAEvidence.model_validate(e) for e in payload["aoa_lookup"]],
                    explanation="Age estimates reuse the L6 response; no additional model call.",
                    assessment_basis=ASSESSMENT_BASIS, aoa_resource_sha256=resource_sha256())
