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

## Soundalike wordplay extension

Implemented in workstreams 01–03 (Project 2). It has offline and mocked
end-to-end tests; the 60-item project corpus has **not** been rerun live since
the L4 prompt changed, so the October 4 numbers above predate it. Design and
evidence: [docs/soundalike/design.md](docs/soundalike/design.md); work plan and
measured checks: [docs/soundalike/HANDOFF.md](docs/soundalike/HANDOFF.md).

### When a soundalike becomes wordplay

The rule above still holds: two soundalike spellings alone do not establish
wordplay. A soundalike becomes wordplay only when (1) L4 chooses a
`sound_substitution` (the written form evokes an absent similar-sounding word)
or `sound_pair` (both words occur and are juxtaposed) reading, (2) the
alternate is either supplied by the local finder or re-verifies phonetically at
the 99th percentile of random same-length CMUdict pairs
(`PHONETIC_VERIFY_PERCENTILE`), never on the model's word, (3) the two readings
are anchored to different source spans, and (4) L5 resolution and L6
distinctness pass. The result is `VALID_SOUNDALIKE_JOKE` with scope
`SOUNDALIKE` (detection status PUN). `OUT_OF_SCOPE_HOMOPHONE` remains for
soundalike mechanisms the phonetic module cannot represent.

### Stages

The phonetic modules are local libraries called from L2/L4; the runner's
registry order is unchanged.

| Stage | Soundalike responsibility | Implementation |
|---|---|---|
| P0 | Words and 1–3-token spans to phones via `nltk.corpus.cmudict` (stress stripped except AH0 → ə, ER0 → ə˞); hyphenated coinages looked up whole, then by parts; one explicit ARPAbet → IPA table checked against PanPhon at import. No g2p fallback: a miss is reported. | `phonetics/lexicon.py`, `phonetics/features.py` |
| P1 | Graded sound similarity and length calibration (formulas below). | `phonetics/similarity.py`, `phonetics/calibration.py` |
| P2 | Recall-only finder: content-word pairs in the text kept at the p95 random-pair similarity for their length (`PHONETIC_RETRIEVE_PERCENTILE`), word families skipped; hyphen merges that exactly match a real word. | `l3_soundalikes.py` |
| L1 | Also records hyphenated spans in `hyphen_groups`; `tokens` unchanged. | `l1_surface.py` |
| L2 | Whole-word and split senses for hyphen groups under their exact surface ("cat-nap"); senses for each alternate (source `soundalike:<alt>`); finder output in `L2Result.soundalikes`. L2 status still reflects the text's own senses. | `l2_senses.py`, `layers.run_l2` |
| L3 | Soundalike entries with a separate budget (`L3_SOUNDALIKE_TOP_K`): a term already in the homograph top-k only gains alternates, others are appended after it, so the homograph shortlist is unchanged. | `l3_candidates.py` |
| L4 | Alternates (form, relation, similarity, own senses) offered in the single shortlist request; 11-key response with `alternate_form`; hyphenated resegmentation accepted (parts join to the term without hyphens). | `l4_anchoring.py`, `prompts/l4_anchoring.md`, `validation.py` |
| L5/L6 | A soundalike note (`{mechanism_note}`) names the written form, alternate and relation; it is empty otherwise, so homograph and split prompts are byte-identical. | `l5_resolution.py`, `l6_distinctness.py`, prompts |
| L7/L8 | The alternate's words are added to the AoA lookup table (citable, not mandatory). | `age_evidence.age_inputs` |
| L0-post | Soundalike PASS → `SOUNDALIKE` / `VALID_SOUNDALIKE_JOKE`; label sites in `runner.py`, `serve.py` and `static/index.html` updated. | `runner._l0_post_layer`, `l0_scope.py`, `decisions.py`, `enums.py` |

Licence note: the lexicon uses NLTK's `cmudict` corpus (BSD-style CMU data)
rather than the PyPI `cmudict` package, which is GPL-3.0-or-later while CRACK
is MIT. PanPhon (MIT) is pinned at 0.22.2; its CSVs are read as UTF-8 by
`phonetics/features.py` because `panphon.FeatureTable` fails on Windows
without `PYTHONUTF8`.

### Similarity method

Phone distance δ(a, b) = Σ_f w_f·|a_f − b_f| / (2·Σ_f w_f) over PanPhon's
articulatory features (values −1/0/+1), with weights matched to features **by
name** (Σ w = 7.25). PanPhon's own weighted distance zips weights by position,
which misweights `tense`, so it is not used. Word distance is a weighted
Levenshtein with substitution cost δ and insertion/deletion 0.5;
sim = 1 − d / max(n, m), maximised over pronunciation pairs. Raw scores are
compressed (random pairs average about 0.72–0.75), so
sim_cal = (sim − μ_L) / (1 − μ_L), with μ_L and the p95/p99 thresholds from
`data/phonetic_calibration.json` (seeded random pairs; regenerate with
`scripts/fit_phonetic_calibration.py`).

### Call budget

Unchanged: L4, L5 and L6 each use at most one request and L7/L8 none. All
phonetic work (lookup, scoring, candidate search, alternate verification) is
local. A rejected alternate is an L4 validation failure; no corrective request
is made.

### Contract versions

`RESPONSE_CONTRACT_VERSION` is "7" and `CANDIDATE_SEARCH_VERSION` is "5", so
`--resume` refuses records written before the soundalike contract. The resume
source fingerprint hashes `src/crack/**/*.py` recursively, so changes under
`phonetics/` also invalidate resumed records. `heterographic_homophone` is now
an accepted mechanism in `config.py`.
