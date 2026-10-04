"""Pydantic v2 models for the shared analysis record.

Invariant enforced by model_validator on AnalysisRecord:
    Detection fields (scope, ambiguous_term, senses, anchors, resolution)
    MUST NOT be nested under per_age.  Detection is computed once for the
    whole text and is age-independent.  Per-age slots hold only
    comprehension and appropriateness assessments.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    AgeAppropriatenessVerdict,
    AmbiguityAblation,
    AnchorRelation,
    AnchoringStatus,
    ComprehensionStatus,
    DistinctnessStatus,
    DetectionStatus,
    detection_status_for,
    Genre,
    MainClassification,
    ResolutionStatus,
    ScopeLabel,
)


# ---------------------------------------------------------------------------
# Sense and candidate sub-models (used by L2 and L3 results)
# ---------------------------------------------------------------------------

class SenseEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    lemma: str
    pos: str
    sense_id: str
    definition: str
    example: Optional[str] = None
    sense_frequency: Optional[float] = None
    aoa_estimate: Optional[float] = None
    source: str
    lexname: Optional[str] = None          # WordNet lexicographer file, e.g. noun.body
    semcor_count: Optional[int] = None     # WordNet Lemma.count() (SemCor tag count)
    # Which AoA fallback stage matched: exact | lowercase | lemmatized | miss.
    aoa_match: Optional[str] = None


class CandidateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    score: float
    score_components: dict[str, float] = Field(default_factory=dict)
    sense_a_id: Optional[str] = None
    sense_b_id: Optional[str] = None
    # Keep alternative segmentations even when another reading ranks first.
    # These are lexical proposals, not positive detection findings.
    split_options: list[tuple[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-layer result models (typed stubs; populated when layers run)
# ---------------------------------------------------------------------------

class L1Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genre: Genre
    tokens: list[str]
    lemmas: list[str]
    pos_tags: list[str]
    compound_splits: list[str] = Field(default_factory=list)
    multiword_expressions: list[str] = Field(default_factory=list)
    has_question: bool = False
    has_negation: bool = False
    has_speaker_turns: bool = False


class L2Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    senses: list[SenseEntry] = Field(default_factory=list)


class L3Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[CandidateEntry] = Field(default_factory=list)
    # Historical search metadata only; the runtime never promotes this tail
    # or treats unassessed terms as evidence.
    deferred_candidates: list[CandidateEntry] = Field(default_factory=list)
    total_terms: Optional[int] = None


class L4CandidateFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str
    status: AnchoringStatus


class L4Search(BaseModel):
    """Search accounting separate from the model's candidate-level response."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["automatic", "target_only"] = "automatic"
    candidate_budget: int = Field(ge=1)
    retrieved_terms: int = Field(ge=0)
    available_terms: int = Field(ge=0)
    findings: list[L4CandidateFinding] = Field(default_factory=list)
    considered_terms: list[str] = Field(default_factory=list)
    untested_terms: int = Field(ge=0)
    stop_reason: Literal[
        "IN_PROGRESS", "PASS_FOUND", "ALL_RETRIEVED_ASSESSED",
        "BUDGET_EXHAUSTED", "CANDIDATES_UNAVAILABLE", "NO_CANDIDATES",
        "EXECUTION_FAILED", "TARGET_ONLY",
        "INSUFFICIENT_EVIDENCE", "CANDIDATES_REJECTED",
    ] = "IN_PROGRESS"


class L4Attempt(BaseModel):
    """A locally accepted or rejected response, before selecting a candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_term: str
    candidate_terms: list[str] = Field(default_factory=list)
    attempt: int
    prompt_sha256: str
    model_used: str = ""
    provider_retries: int = 0
    fallback_used: bool = False
    raw_responses: list[str] = Field(default_factory=list)
    parsed_response: Optional[dict[str, Any]] = None
    accepted: bool = False
    error: str = ""


class L4Result(BaseModel):
    """L4 anchoring result.

    sense_a_anchor_quote and sense_b_anchor_quote are CONTEXT SPANS: exact
    substrings of the item text that establish each sense of the ambiguous term,
    not the ambiguous term itself.  They must be distinct unless
    anchor_relation is RESEGMENTATION (compound-split: both senses anchor to
    the compound word, so identical spans are correct and expected).

    resolving_sense names which of sense_a / sense_b the punchline resolves
    to.  a/b order carries NO meaning: prompts must read the punchline sense
    through this field, never by position.  Required when anchoring_status is
    PASS (L5 runs only then).
    """

    model_config = ConfigDict(extra="forbid")

    sense_a: str
    sense_a_anchor_quote: str
    sense_b: str
    sense_b_anchor_quote: str
    anchor_relation: Optional[AnchorRelation] = None
    anchoring_status: AnchoringStatus
    resolving_sense: Optional[Literal["sense_a", "sense_b"]] = None
    reasoning: str = ""
    target_term: str = ""  # Historical records remain readable.
    split_parts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _pass_requires_resolving_sense(self) -> "L4Result":
        if self.anchoring_status == AnchoringStatus.PASS:
            if self.resolving_sense is None or self.anchor_relation is None:
                raise ValueError("PASS requires resolving_sense and anchor_relation")
            if not all(s.strip() for s in (self.sense_a, self.sense_b, self.sense_a_anchor_quote, self.sense_b_anchor_quote)):
                raise ValueError("PASS requires two nonempty meanings and anchors")
            if self.sense_a.strip().casefold() == self.sense_b.strip().casefold():
                raise ValueError("PASS cannot use identical meaning descriptions")
            if self.anchor_relation != AnchorRelation.RESEGMENTATION and self.sense_a_anchor_quote.casefold() == self.sense_b_anchor_quote.casefold():
                raise ValueError("Non-split PASS requires different context anchors")
        elif self.resolving_sense is not None or self.anchor_relation is not None:
            raise ValueError("Non-PASS anchoring must not claim a resolving sense or relation")
        return self


class L5QAResult(BaseModel):
    """Resolution result for QA_RIDDLE jokes.

    Subscores map the five keys from L5_QA_WEIGHTS: polarity_or_direction,
    answer_relevance, causal, agent, tense_aspect.
    resolution_score is None for INSUFFICIENT_CONTEXT (incomplete LLM response).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    genre: Literal[Genre.QA_RIDDLE]
    resolution_status: ResolutionStatus
    # None keeps historical records readable; new assessed responses provide a boolean.
    context_consistent: Optional[bool] = None
    resolution_score: Optional[float] = None
    subscores: dict[str, float]
    model_used: str = ""
    fallback_used: bool = False
    retries: int = 0
    explanation: str = ""


class L5DefinitionalResult(BaseModel):
    """Resolution result for DEFINITIONAL_ONELINER jokes.

    Subscores: setup_invites_literal, punchline_exploits_split, contrast_strength.
    Note: same-span anchors are permitted when anchor_relation == RESEGMENTATION.
    See ARCHITECTURE.md § L5 Decision 2.
    resolution_score is None for INSUFFICIENT_CONTEXT (incomplete LLM response).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    genre: Literal[Genre.DEFINITIONAL_ONELINER]
    resolution_status: ResolutionStatus
    # None keeps historical records readable; new assessed responses provide a boolean.
    context_consistent: Optional[bool] = None
    resolution_score: Optional[float] = None
    subscores: dict[str, float]
    model_used: str = ""
    fallback_used: bool = False
    retries: int = 0
    explanation: str = ""


class L5DialogueResult(BaseModel):
    """Resolution result for DIALOGUE_MISUNDERSTANDING jokes.

    Subscores: misunderstanding_plausible, contrast_clear, speaker_intention_clear.
    resolution_score is None for INSUFFICIENT_CONTEXT (incomplete LLM response).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    genre: Literal[Genre.DIALOGUE_MISUNDERSTANDING]
    resolution_status: ResolutionStatus
    # None keeps historical records readable; new assessed responses provide a boolean.
    context_consistent: Optional[bool] = None
    resolution_score: Optional[float] = None
    subscores: dict[str, float]
    model_used: str = ""
    fallback_used: bool = False
    retries: int = 0
    explanation: str = ""


class L5DeclarativeResult(BaseModel):
    """Resolution result for DECLARATIVE one-liners.

    Subscores: both_readings_available, punchline_sense_is_unexpected,
    incongruity_present.
    resolution_score is None for INSUFFICIENT_CONTEXT (incomplete LLM response).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    genre: Literal[Genre.DECLARATIVE]
    resolution_status: ResolutionStatus
    # None keeps historical records readable; new assessed responses provide a boolean.
    context_consistent: Optional[bool] = None
    resolution_score: Optional[float] = None
    subscores: dict[str, float]
    model_used: str = ""
    fallback_used: bool = False
    retries: int = 0
    explanation: str = ""


L5Result = Annotated[
    Union[L5QAResult, L5DefinitionalResult, L5DialogueResult, L5DeclarativeResult],
    Field(discriminator="genre"),
]


class L6Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distinctness_status: DistinctnessStatus
    ambiguity_ablation: Optional[AmbiguityAblation] = None
    sense_a_paraphrase: Optional[str] = None
    sense_b_paraphrase: Optional[str] = None
    explanation: Optional[str] = None
    suppresses_other: Optional[bool] = None
    materially_different: Optional[bool] = None
    # Kept raw so a malformed age answer cannot invalidate detection. L7/L8
    # validate their own dependent outputs without making additional calls.
    age_assessment: Any = None


class CandidateAssessment(BaseModel):
    """Preserved candidate findings; a later candidate never overwrites these."""

    model_config = ConfigDict(extra="forbid")

    term: str
    l4_result: Optional[L4Result] = None
    l5_result: Optional[L5Result] = None
    l6_result: Optional[L6Result] = None
    outcome: Optional[DetectionStatus] = None
    reason: str = ""


class AoAEvidence(BaseModel):
    """A verbatim citation from the supplied word-level ratings table."""

    model_config = ConfigDict(extra="forbid")
    word: str
    aoa: Optional[float]
    match: str
    source: str


class AgeComprehensionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vocabulary: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    sense_a: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    sense_b: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    wordplay: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    background_knowledge: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    prerequisites: list[str]
    reason: str


class AgeEstimate(BaseModel):
    """Compact contextual judgments from the existing L6 model response."""

    model_config = ConfigDict(extra="forbid", strict=True)
    understanding: Literal["LIKELY", "UNLIKELY", "UNKNOWN"]
    barrier: Literal["vocabulary", "sense_a", "sense_b", "wordplay", "background_knowledge"] | None
    content_appropriate: bool | None
    inference_appropriate: bool | None
    reason: str
    content_quote: str
    prerequisite: str


AgeDimension = Literal["vocabulary", "sense_a", "sense_b", "wordplay", "background_knowledge", "understanding"]


class AgeComprehensionSummary(BaseModel):
    """Program-derived decision; unresolved axes stay explicit."""

    model_config = ConfigDict(extra="forbid")
    status: ComprehensionStatus
    barrier_dimensions: list[AgeDimension]
    unknown_dimensions: list[AgeDimension]
    fully_assessed: bool


class ContentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quote: str
    concern: str


class AgeModelAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    layer: Literal["L7", "L8"]
    attempt: int
    backend: str
    model: str
    prompt_sha256: str
    raw_responses: list[str] = Field(default_factory=list)
    parsed_response: Optional[dict[str, Any]] = None
    accepted: bool = False
    error: Optional[str] = None


class L7Result(BaseModel):
    """Comprehension assessment — results are per target age."""

    model_config = ConfigDict(extra="forbid")

    per_age_comprehension: dict[int, ComprehensionStatus] = Field(default_factory=dict)
    required_vocabulary: list[str] = Field(default_factory=list)
    aoa_evidence: list[AoAEvidence] = Field(default_factory=list)
    per_age_details: dict[int, AgeComprehensionEvidence] = Field(default_factory=dict)
    per_age_estimates: dict[int, AgeEstimate] = Field(default_factory=dict)
    per_age_summaries: dict[int, AgeComprehensionSummary] = Field(default_factory=dict)
    aggregation_version: Optional[str] = None
    assessment_basis: Optional[str] = None
    aoa_resource_sha256: Optional[str] = None
    # Legacy fields remain readable; new assessments never invent sense ages.
    sense_a_aoa: Optional[float] = None
    sense_b_aoa: Optional[float] = None
    compound_split_aoa: Optional[float] = None
    metalinguistic_floor: Optional[float] = None
    explanation: Optional[str] = None


class L8Result(BaseModel):
    """Two-axis appropriateness assessment — results are per target age."""

    model_config = ConfigDict(extra="forbid")

    per_age_verdict: dict[int, AgeAppropriatenessVerdict] = Field(default_factory=dict)
    content_appropriate: dict[int, Optional[bool]] = Field(default_factory=dict)
    inference_appropriate: dict[int, Optional[bool]] = Field(default_factory=dict)
    per_age_reasons: dict[int, str] = Field(default_factory=dict)
    content_evidence: list[ContentEvidence] = Field(default_factory=list)
    assessment_basis: Optional[str] = None
    content_issues: list[str] = Field(default_factory=list)
    inference_issues: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None


# ---------------------------------------------------------------------------
# Trace and verdict models
# ---------------------------------------------------------------------------

class LayerTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str
    status: str
    reason: Optional[str] = None
    duration_ms: float
    hints_used: int = 0
    candidate_term: Optional[str] = None


class AgeVerdict(BaseModel):
    """Per-age assessment holding ONLY age-dependent outputs.

    Detection fields (scope_label, ambiguous_term, sense_a, sense_b,
    anchoring_status, resolution_status, etc.) must NEVER appear here.
    They are age-independent and live at the AnalysisRecord or layer-result
    level.  extra="forbid" enforces this at instantiation time; the
    model_validator on AnalysisRecord provides an explicit, readable error
    for programmatic misuse.
    """

    model_config = ConfigDict(extra="forbid")

    comprehension: ComprehensionStatus
    appropriateness: AgeAppropriatenessVerdict


class FinalVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    main_classification: MainClassification
    scope_label: ScopeLabel
    per_age: dict[int, AgeVerdict] = Field(default_factory=dict)
    detection_status: Optional[DetectionStatus] = None
    review_required: bool = False
    review_reason: str = ""

    @model_validator(mode="after")
    def _decision_state(self) -> "FinalVerdict":
        expected = detection_status_for(self.main_classification)
        if self.detection_status is not None and self.detection_status != expected:
            raise ValueError("detection_status contradicts main_classification")
        self.detection_status = expected
        self.review_required = expected not in {DetectionStatus.PUN, DetectionStatus.NON_PUN}
        return self


# ---------------------------------------------------------------------------
# Top-level analysis record
# ---------------------------------------------------------------------------

_DETECTION_FIELD_NAMES: frozenset[str] = frozenset({
    "scope_label",
    "ambiguous_term",
    "sense_a",
    "sense_b",
    "sense_a_anchor_quote",
    "sense_b_anchor_quote",
    "anchoring_status",
    "resolution_status",
    "anchor_relation",
    "resolution_score",
})


class AnalysisRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    validation_version: Optional[str] = None
    candidate_search_version: Optional[str] = None
    age_validation_version: Optional[str] = None
    age_aggregation_version: Optional[str] = None
    text: str
    target_ages: list[int]

    l1_result: Optional[L1Result] = None
    l2_result: Optional[L2Result] = None
    l3_result: Optional[L3Result] = None
    l4_result: Optional[L4Result] = None
    l4_attempts: list[L4Attempt] = Field(default_factory=list)
    l4_search: Optional[L4Search] = None
    candidate_assessments: list[CandidateAssessment] = Field(default_factory=list)
    l5_result: Optional[L5Result] = None
    l6_result: Optional[L6Result] = None
    l7_result: Optional[L7Result] = None
    l8_result: Optional[L8Result] = None
    age_attempts: list[AgeModelAttempt] = Field(default_factory=list)
    age_preparation_error: Optional[str] = None

    trace: list[LayerTrace] = Field(default_factory=list)
    final: Optional[FinalVerdict] = None
    confidence: Optional[float] = None

    @model_validator(mode="after")
    def _no_detection_fields_in_per_age(self) -> "AnalysisRecord":
        """Fail loudly if any detection field is placed inside per_age.

        AgeVerdict already carries extra="forbid", so pydantic catches unknown
        fields at construction.  This validator adds a human-readable error
        message for cases where detection data is present as valid AgeVerdict
        fields set — which cannot happen with the current typed schema but
        makes the invariant explicit and self-documenting.
        """
        if self.final is None:
            return self
        for age, verdict in self.final.per_age.items():
            leaking = _DETECTION_FIELD_NAMES & verdict.model_fields_set
            if leaking:
                raise ValueError(
                    f"Detection fields {sorted(leaking)} found in per_age[{age}]. "
                    "Detection is age-independent; store these at the record or "
                    "layer-result level, not inside AgeVerdict."
                )
        return self
