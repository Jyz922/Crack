"""L8: independent content and inference checks with explicit unknown states."""
from __future__ import annotations

from typing import Any

from .age_evidence import ASSESSMENT_BASIS, require_ages, require_string_list
from .config import DEFAULT_SETTINGS, Settings
from .enums import AgeAppropriatenessVerdict as Verdict, ComprehensionStatus as Comp
from .schema import AgeComprehensionSummary, AnalysisRecord, ContentEvidence, L8Result
from .validation import ModelResponseError, require_fields, require_text, source_quote


def appropriateness_verdict(content: bool | None, inference: bool | None, comp: Comp,
                            summary: AgeComprehensionSummary | None = None) -> Verdict:
    if content is False:
        return Verdict.CONTENT_NOT_APPROPRIATE
    if content is None or inference is None:
        return Verdict.UNKNOWN
    if inference is False:
        return Verdict.CONTENT_OK_INFERENCE_TOO_ADVANCED
    if summary is not None:
        # A general partial-comprehension label alone cannot identify which
        # prerequisite is difficult. Use the retained dimensions instead.
        if set(summary.barrier_dimensions) & {"vocabulary", "sense_a", "sense_b"}:
            return Verdict.VOCABULARY_TOO_ADVANCED
        if set(summary.barrier_dimensions) & {"wordplay", "background_knowledge"}:
            return Verdict.CONTENT_OK_INFERENCE_TOO_ADVANCED
        if summary.unknown_dimensions:
            return Verdict.UNKNOWN
        return Verdict.FULLY_AGE_APPROPRIATE
    if comp == Comp.AOA_UNKNOWN:
        return Verdict.UNKNOWN
    if comp == Comp.WORDPLAY_SKILL_TOO_ADVANCED:
        return Verdict.CONTENT_OK_INFERENCE_TOO_ADVANCED
    if comp in {Comp.PARTIALLY_COMPREHENSIBLE, Comp.SENSE_B_TOO_ADVANCED}:
        return Verdict.VOCABULARY_TOO_ADVANCED
    return Verdict.FULLY_AGE_APPROPRIATE


def validate_l8(value: Any, payload: dict, record: AnalysisRecord) -> L8Result:
    data = require_fields(value, {"content_appropriate", "inference_appropriate", "per_age_reasons",
                                  "content_evidence", "inference_issues", "explanation"})
    axes = {}
    for name in ("content_appropriate", "inference_appropriate"):
        values = require_ages(data[name], payload["target_ages"], name)
        if any(v is not None and type(v) is not bool for v in values.values()):
            raise ModelResponseError("Appropriateness axes must be true, false, or null")
        axes[name] = {int(a): v for a, v in values.items()}
    reasons = require_ages(data["per_age_reasons"], payload["target_ages"], "per_age_reasons")
    for reason in reasons.values():
        require_text(reason, "age reasoning")
    if not isinstance(data["content_evidence"], list):
        raise ModelResponseError("content_evidence must be an array")
    evidence = []
    for entry in data["content_evidence"]:
        require_fields(entry, {"quote", "concern"})
        require_text(entry["quote"], "content quote")
        source_quote(entry["quote"], record.text, "content quote")
        require_text(entry["concern"], "content concern")
        evidence.append(ContentEvidence.model_validate(entry))
    issues = require_string_list(data["inference_issues"], "inference_issues")
    if False in axes["content_appropriate"].values() and not evidence:
        raise ModelResponseError("Content rejection requires a quoted concern")
    if False in axes["inference_appropriate"].values() and not issues:
        raise ModelResponseError("Inference rejection requires a named prerequisite")
    require_text(data["explanation"], "explanation")
    if record.l7_result is None:
        raise ModelResponseError("L8 requires a completed L7 assessment")
    verdicts = {age: appropriateness_verdict(axes["content_appropriate"][age],
                axes["inference_appropriate"][age], record.l7_result.per_age_comprehension.get(age, Comp.AOA_UNKNOWN),
                record.l7_result.per_age_summaries.get(age))
                for age in record.target_ages}
    return L8Result(**axes, per_age_verdict=verdicts, per_age_reasons={int(a): r for a, r in reasons.items()},
                    content_evidence=evidence, content_issues=[e.concern for e in evidence],
                    inference_issues=issues, explanation=data["explanation"], assessment_basis=ASSESSMENT_BASIS)


def assess_l8(record: AnalysisRecord, settings: Settings = DEFAULT_SETTINGS,
              client: Any = None) -> L8Result:
    if record.l7_result is None:
        raise ModelResponseError("L8 requires a completed L7 assessment")
    content, inference, verdicts, reasons = {}, {}, {}, {}
    evidence, issues = [], []
    for age in record.target_ages:
        # Each age is independent: a rejected or unknown L7 finding is terminal
        # for that age, while other requested ages may have passed.
        if record.l7_result.per_age_comprehension.get(age) != Comp.FULLY_COMPREHENSIBLE:
            content[age] = inference[age] = None
            verdicts[age] = Verdict.UNKNOWN
            reasons[age] = "L7 did not pass; appropriateness assessment stopped for this age."
            continue
        estimate = record.l7_result.per_age_estimates.get(age)
        if estimate is None:
            raise ModelResponseError("L8 is missing the validated shared age estimate")
        if estimate.content_quote:
            source_quote(estimate.content_quote, record.text, "content quote")
        if estimate.content_appropriate is False:
            require_text(estimate.content_quote, "content rejection quote")
            evidence.append(ContentEvidence(quote=estimate.content_quote, concern=estimate.reason))
        if estimate.inference_appropriate is False:
            require_text(estimate.prerequisite, "inference prerequisite")
            issues.append(estimate.prerequisite)
        content[age], inference[age] = estimate.content_appropriate, estimate.inference_appropriate
        reasons[age] = estimate.reason
        verdicts[age] = appropriateness_verdict(content[age], inference[age], Comp.FULLY_COMPREHENSIBLE)
    return L8Result(content_appropriate=content, inference_appropriate=inference,
                    per_age_verdict=verdicts, per_age_reasons=reasons,
                    content_evidence=evidence, content_issues=[e.concern for e in evidence],
                    inference_issues=list(dict.fromkeys(issues)),
                    explanation="Appropriateness reuses the L6 response; no additional model call.",
                    assessment_basis=ASSESSMENT_BASIS)
