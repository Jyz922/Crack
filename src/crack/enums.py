"""All pipeline status enums.

Every status string that appears in the README is defined here as a StrEnum
member.  No bare string literals for statuses are permitted elsewhere in the
codebase.
"""

from enum import StrEnum


class ScopeLabel(StrEnum):
    HOMOGRAPH = "HOMOGRAPH"
    COMPOUND_SPLIT = "COMPOUND_SPLIT"
    OUT_OF_SCOPE_HOMOPHONE = "OUT_OF_SCOPE_HOMOPHONE"
    OUT_OF_SCOPE_NONLEXICAL_JOKE = "OUT_OF_SCOPE_NONLEXICAL_JOKE"
    NO_SCOPE_MECHANISM = "NO_SCOPE_MECHANISM"


class Genre(StrEnum):
    QA_RIDDLE = "QA_RIDDLE"
    DEFINITIONAL_ONELINER = "DEFINITIONAL_ONELINER"
    DIALOGUE_MISUNDERSTANDING = "DIALOGUE_MISUNDERSTANDING"
    DECLARATIVE = "DECLARATIVE"


class AnchoringStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ONE_SENSE_ONLY = "ONE_SENSE_ONLY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AnchorRelation(StrEnum):
    SEPARATE_CONTEXTS = "separate_contexts"
    RESEGMENTATION = "resegmentation"
    SPEAKER_MISMATCH = "speaker_mismatch"


class ResolutionStatus(StrEnum):
    RESOLUTION_PASS = "RESOLUTION_PASS"
    RESOLUTION_FAIL = "RESOLUTION_FAIL"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    # Model hit max_output_tokens before emitting complete JSON (thinking
    # consumed the budget). A truncation, NOT a model verdict — surfaced
    # distinctly so it can never be mistaken for RESOLUTION_FAIL or
    # INSUFFICIENT_CONTEXT.
    TRUNCATED_OUTPUT = "TRUNCATED_OUTPUT"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class DistinctnessStatus(StrEnum):
    SENSES_DISTINCT = "SENSES_DISTINCT"
    SENSES_TOO_CLOSE = "SENSES_TOO_CLOSE"
    L6_SKIPPED_NO_PARAPHRASE = "L6_SKIPPED_NO_PARAPHRASE"


class AmbiguityAblation(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    SKIPPED = "SKIPPED"


class ComprehensionStatus(StrEnum):
    FULLY_COMPREHENSIBLE = "FULLY_COMPREHENSIBLE"
    PARTIALLY_COMPREHENSIBLE = "PARTIALLY_COMPREHENSIBLE"
    SENSE_B_TOO_ADVANCED = "SENSE_B_TOO_ADVANCED"
    WORDPLAY_SKILL_TOO_ADVANCED = "WORDPLAY_SKILL_TOO_ADVANCED"
    AOA_UNKNOWN = "AOA_UNKNOWN"


class AgeAppropriatenessVerdict(StrEnum):
    FULLY_AGE_APPROPRIATE = "FULLY_AGE_APPROPRIATE"
    CONTENT_OK_INFERENCE_TOO_ADVANCED = "CONTENT_OK_INFERENCE_TOO_ADVANCED"
    VOCABULARY_TOO_ADVANCED = "VOCABULARY_TOO_ADVANCED"
    CONTENT_NOT_APPROPRIATE = "CONTENT_NOT_APPROPRIATE"


class MainClassification(StrEnum):
    VALID_HOMOGRAPH_JOKE = "VALID_HOMOGRAPH_JOKE"
    VALID_COMPOUND_SPLIT_JOKE = "VALID_COMPOUND_SPLIT_JOKE"
    NO_AMBIGUITY_FOUND = "NO_AMBIGUITY_FOUND"
    ONE_SENSE_ONLY = "ONE_SENSE_ONLY"
    ANCHORING_FAIL = "ANCHORING_FAIL"
    RESOLUTION_FAIL = "RESOLUTION_FAIL"
    SENSES_TOO_CLOSE = "SENSES_TOO_CLOSE"
    OUT_OF_SCOPE_HOMOPHONE = "OUT_OF_SCOPE_HOMOPHONE"
    OUT_OF_SCOPE_NONLEXICAL_JOKE = "OUT_OF_SCOPE_NONLEXICAL_JOKE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class DetectionStatus(StrEnum):
    PUN = "PUN"
    NON_PUN = "NON_PUN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


def detection_status_for(label: str | MainClassification | None) -> DetectionStatus:
    """Map explicit decisions only; missing/legacy ambiguous labels abstain."""
    if label in {MainClassification.VALID_HOMOGRAPH_JOKE, MainClassification.VALID_COMPOUND_SPLIT_JOKE}:
        return DetectionStatus.PUN
    if label in {MainClassification.ONE_SENSE_ONLY, MainClassification.RESOLUTION_FAIL, MainClassification.SENSES_TOO_CLOSE}:
        return DetectionStatus.NON_PUN
    if label == MainClassification.EXECUTION_FAILED:
        return DetectionStatus.EXECUTION_FAILED
    if label in {MainClassification.OUT_OF_SCOPE_HOMOPHONE, MainClassification.OUT_OF_SCOPE_NONLEXICAL_JOKE}:
        return DetectionStatus.OUT_OF_SCOPE
    return DetectionStatus.INSUFFICIENT_EVIDENCE
