"""Final detection decisions require completed, consistent stage evidence."""

from .enums import (
    AmbiguityAblation, AnchorRelation, AnchoringStatus, DistinctnessStatus,
    MainClassification, ResolutionStatus, ScopeLabel,
)
from .schema import AnalysisRecord
from .validation import ModelResponseError, validate_l4_response, validate_l6_response


DETECTION_LAYERS = frozenset({"L0-pre", "L1", "L2", "L3", "L4", "L5", "L6"})


def detection_decision(record: AnalysisRecord, scope: ScopeLabel) -> tuple[MainClassification, str]:
    errors = [t for t in record.trace if t.layer in DETECTION_LAYERS and t.status in {"ERROR", "REJECTED"}]
    if errors:
        return MainClassification.EXECUTION_FAILED, "; ".join(f"{t.layer}: {t.reason or t.status}" for t in errors)

    l4, l5, l6 = record.l4_result, record.l5_result, record.l6_result
    if l5 and l5.resolution_status in {ResolutionStatus.TRUNCATED_OUTPUT, ResolutionStatus.EXECUTION_FAILED}:
        return MainClassification.EXECUTION_FAILED, "L5 could not produce a complete validated response. Retry the analysis."
    if l4 is None:
        return MainClassification.INSUFFICIENT_EVIDENCE, "Sense anchoring has not been completed. Review the text and rerun analysis."
    if l4.anchoring_status == AnchoringStatus.INSUFFICIENT_EVIDENCE and not l4.target_term:
        if not record.l3_result or not record.l3_result.candidates:
            return MainClassification.INSUFFICIENT_EVIDENCE, l4.reasoning
    term = record.l3_result.candidates[0].term if record.l3_result and record.l3_result.candidates else ""
    is_split = bool(record.l3_result and any(
        c.term == term and c.score_components.get("compound_split") == 1.0
        for c in record.l3_result.candidates
    ))
    try:
        split_options = record.l3_result.candidates[0].split_options if record.l3_result and record.l3_result.candidates else []
        validate_l4_response(l4.model_dump(), record.text, term, is_split, split_options)
    except ModelResponseError as exc:
        return MainClassification.EXECUTION_FAILED, f"L4 evidence validation failed: {exc}"

    if l4.anchoring_status in {AnchoringStatus.FAIL, AnchoringStatus.INSUFFICIENT_EVIDENCE}:
        return MainClassification.INSUFFICIENT_EVIDENCE, l4.reasoning
    if scope in {ScopeLabel.OUT_OF_SCOPE_HOMOPHONE, ScopeLabel.OUT_OF_SCOPE_NONLEXICAL_JOKE}:
        label = MainClassification(scope.value)
        return label, "This text needs review under a different wordplay mechanism."
    if l4.anchoring_status == AnchoringStatus.ONE_SENSE_ONLY:
        if record.l4_search and record.l4_search.untested_terms:
            return MainClassification.INSUFFICIENT_EVIDENCE, (
                f"{record.l4_search.untested_terms} retrieved candidate terms remain unassessed. "
                "A candidate-level negative is not a completed text-level judgment."
            )
        return MainClassification.ONE_SENSE_ONLY, ""
    if l5 is None:
        return MainClassification.INSUFFICIENT_EVIDENCE, "Semantic resolution has not been completed."
    if l5.resolution_status == ResolutionStatus.INSUFFICIENT_CONTEXT:
        return MainClassification.INSUFFICIENT_EVIDENCE, l5.explanation or "L5 needs more context to assess the proposed readings."
    if l5.resolution_status == ResolutionStatus.RESOLUTION_FAIL:
        return MainClassification.RESOLUTION_FAIL, ""
    if l6 is None or l6.distinctness_status == DistinctnessStatus.L6_SKIPPED_NO_PARAPHRASE:
        return MainClassification.INSUFFICIENT_EVIDENCE, (l6.explanation if l6 else None) or "Sense distinctness has not been established."
    try:
        validate_l6_response(l6.model_dump())
    except ModelResponseError as exc:
        return MainClassification.EXECUTION_FAILED, f"L6 evidence validation failed: {exc}"
    if l6.distinctness_status == DistinctnessStatus.SENSES_TOO_CLOSE:
        return MainClassification.SENSES_TOO_CLOSE, ""
    if l6.ambiguity_ablation != AmbiguityAblation.SUPPORTED:
        return MainClassification.INSUFFICIENT_EVIDENCE, "The controlled rewrite did not establish that the ambiguity creates the wordplay. Review both readings."
    label = (MainClassification.VALID_COMPOUND_SPLIT_JOKE
             if l4.anchor_relation == AnchorRelation.RESEGMENTATION
             else MainClassification.VALID_HOMOGRAPH_JOKE)
    return label, ""
