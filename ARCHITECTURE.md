# CRACK architecture

CRACK runs input checks, lexical analysis, model-assisted semantic checks, and a final classification. The layer implementations are in `src/crack/`; the order is registered in `src/crack/runner.py`.

## Pipeline

| Stage | Responsibility | Main implementation |
|---|---|---|
| L0-pre | Normalize and validate input length and character content. | `l0_scope.py` |
| L1 | Tokenize the text and route it to a genre branch. | `l1_surface.py` |
| L2 | Retrieve WordNet senses and add available SemCor counts and AoA estimates. | `l2_senses.py` |
| L3 | Rank ambiguous terms, multiword expressions, and compound splits. | `l3_candidates.py` |
| L4 | Ask an LLM to assess candidate readings and anchor quotes in the input text. | `l4_anchoring.py` |
| L5 | Assess whether the proposed wordplay resolves coherently in the supplied text. | `l5_resolution.py` |
| L6 | Check materially different readings and, when requested, return compact age estimates in the same request. | `l6_distinctness.py`, `age_evidence.py` |
| L7 | Locally validate cached understanding estimates and attach word-level AoA citations. | `l7_comprehension.py` |
| L8 | Locally derive separate content and inference verdicts for ages that passed L7. | `l8_appropriateness.py` |
| L0-post | Combine validated evidence into a final class and scope label. | `runner.py`, `decisions.py` |

The runner records PASS, FAIL, UNKNOWN or ERROR in each stage's `LayerTrace`.
FAIL is a completed check that rejected the analysis; UNKNOWN lacks evidence;
ERROR is an execution or response-validation failure. Dependent stages are
SKIPPED after any of these states. Failed/skipped stages discard their partial
and downstream results. The finalizer always runs to report the actual outcome.
An age failure preserves completed detection and leaves age verdicts unknown.

## Lexical evidence and candidate ranking

L2 uses NLTK WordNet and WordNet lemma counts associated with SemCor. Age estimates come from the Kuperman AoA data in `data/aoa_kuperman.csv`. Data lookup and candidate ranking are deterministic for a fixed local resource version. AoA values are word-level estimates; they do not establish that a particular child knows a word or understands a joke.

L2 keeps a multiword proposal only when its surface phrase actually occurs in
the source text; punctuation must not join separate sentences into an expression.

L3 ranks candidate terms without using the requested target age. Age-dependent judgments are handled later by L7, so the candidate list is intended to stay the same when only the requested age changes.

L4 compares the original shortlist of up to eight terms in one request. It
first locates the whole-text lexical interaction, then chooses and anchors the
target that explains it. Local checks require the target to be in the supplied
list and validate its source quotes and split options. Rejection, UNKNOWN or
invalid output stops; no candidate retry follows. Deferred terms are metadata
only and L5/L6 never restart L4. `considered_terms` records the supplied list;
only the chosen finding has individually validated evidence. Other terms do
not receive manufactured verdicts. A negative is a bounded detector finding,
not proof that every dictionary reading was examined.

L4 requires quotes that support each proposed reading. `validation.py` rejects nonempty quotes absent from the input, missing fields, unknown states, and contradictory findings. Positive final decisions require completed L4, L5, and L6 evidence; unresolved stages request review. See [response validation and evaluation denominators](docs/response_validation.md).

## Model-assisted stages

L4–L6 use provider clients from `providers.py`. Required fields, score types,
completion metadata and source quotes are checked locally. Invalid responses
are not repaired with another request. Existing transport retries for transient
provider failures remain separate from semantic assessment.
The [failure/retry/fallback policy](docs/provider_failure_policy.md) specifies
the different OpenAI-compatible, Gemini and Anthropic recovery paths, including
SDK retries, request-option compatibility and accounting limitations.

L7/L8 make no provider calls: their compact estimates arrive in L6's existing
response. Exact age keys, field types and quoted concerns are checked locally;
citations come directly from the local AoA resource. Missing or malformed age
data stops age assessment without changing detection. See [age evidence](docs/age_evidence.md).
Structural validation does not establish semantic correctness.

For successful provider responses, L4, L5 and L6 each use at most one request,
and L7/L8 use zero. A completed positive uses three requests for detection plus
age assessment. These bounds exclude transport
retries, SDK retries, compatibility retries and configured Gemini fallback.
The compact age answer still adds tokens to L6. Two October 4 corpus passes
measure this detection/age design; their results and limits are documented in
[the recovery comparison](docs/corpus_recovery_20261004.md).

L5 uses genre-specific result schemas. QA riddles use weighted subscores for polarity or event direction, answer relevance, causal fit, agent compatibility, and tense/aspect fit. Other genres use their own subscores. A self-contained question uses the existing general wordplay branch when no
answer turn is supplied. L5 also records whether a relationship necessary for
the proposed wordplay contradicts the text; this finding cannot be overridden by
averaging other high scores. A cause, shared agent or speaker intention is not
required for every text. Thresholds are stored in `config.py`; their calibration evidence and known weaknesses are described in `docs/L5_CALIBRATION.md`.

L6 paraphrases meanings rather than constructing a second literal event. A
conventional frame evoked by context is assessable without being asserted as
fact; invented meanings and unsupported topic links remain invalid. Materially
different readings may coexist. Mutual suppression and the historical ablation field are
diagnostics; neither is a positive gate and no controlled rewrite is required.

Final scope follows assessed wordplay evidence. The occurrence of two soundalike
spellings alone does not establish homophone wordplay or override a validated
homographic target. The interface uses the assessed L4 target directly.

No requested ages means L7/L8 are skipped. It is a valid detection-only run.

## Run provenance and resume

Each new batch saves input and source/prompt hashes and nonsecret model/settings
before inference. Resume checks source/prompt hashes and settings before reusing
current-version, error-free decisions with matching text and ages. A different
input file may add items; changed texts are rerun. Missing or incompatible run
metadata stops resume before any new calls.

## Evaluation notes

The README reports both October 4 project-corpus passes for this detection/age
pipeline. [Published evidence](docs/evaluations/README.md) includes compact
per-item records, summaries and provenance that can be rescored offline.
Historical SemEval scores retain their original source and task definitions
in [the historical audit](docs/benchmark_audit.md); this revision has not been
rerun on all 2,250 SemEval items.

The [layer and prompt review](docs/layer_prompt_review.md) records how each stage
handles missing evidence and which unsupported prompt/output defaults were removed.

No token-saving rate, hallucination-elimination rate or child-safety guarantee
is established by the current evaluation artifacts.

The [system design review](docs/system_design_review.md) documents the targeted
reliability and usability revisions, preserved thresholds and offline verification.
