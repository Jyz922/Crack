# CRACK

[![Version: v1.0.0](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/Jyz922/Crack/releases/tag/v1.0.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CRACK** (Computational Resolution & Anchoring of Comedy & Knowledge) analyzes English wordplay by combining WordNet, SemCor, age-of-acquisition data, and configurable LLM judgments. It identifies candidate ambiguous words, records text spans supporting each reading, assesses joke resolution, and reports comprehension and appropriateness by requested age.

The pipeline targets homographic wordplay (one spelling with multiple meanings) and compound resegmentation. Contextual analysis can use any of the supported LLM providers.

### Try CRACK live

Curious how it works? [Try the live demo](https://crack-8s9j.onrender.com): enter an English joke and watch CRACK analyze its possible wordplay, meaning, and age-level comprehension.

<p align="center">
  <img src="assets/demo.gif" alt="CRACK interactive analysis interface" width="100%">
</p>

## Evaluation data and reported results

This version has two fresh project-corpus regression runs, reported below.
Earlier benchmark results belong to earlier designs and are archived separately.
Use [the fresh corpus command](#test-the-current-project-corpus) to repeat the
current evaluation.

### Current pipeline regression — October 4, 2026

A complete recovery pass and a fresh user rerun used the same source, 60 texts,
gold labels, requested ages and OpenAI `gpt-6-luna`. Strict response checks,
fail/unknown stopping and service retry/fallback remain enabled.

| Metric | Before recovery | Recovery pass | User rerun |
|---|---:|---:|---:|
| Exact classification, all items | 47/60 (78.3%) | **55/60 (91.7%)** | **55/60 (91.7%)** |
| Binary accuracy, all items | 49/60 (81.7%) | **56/60 (93.3%)** | **56/60 (93.3%)** |
| Decision coverage | 54/60 (90.0%) | **60/60 (100.0%)** | **60/60 (100.0%)** |
| Age agreement, all original labels | 42/180 (23.3%) | 51/180 (28.3%) | 53/180 (29.4%) |
| Age agreement, all gold-pun labels | 37/75 (49.3%) | 46/75 (61.3%) | 48/75 (64.0%) |
| Age assessment coverage, gold-pun labels | 53/75 (70.7%) | 67/75 (89.3%) | 67/75 (89.3%) |
| Age agreement, assessed gold-pun labels | 37/53 (69.8%) | 46/67 (68.7%) | 48/67 (71.6%) |

The recovery pass made **115 observed SDK calls** across the whole corpus
(60 L4, 28 L5, 27 L6); the user rerun's records imply 116 normal requests
(60 L4, 29 L5, 27 L6). Age estimates share L6; completed positive items use
three normal requests. Earlier records imply 358 normal requests. Inferred
counts exclude unrecorded transport retries. Average summed per-item trace
time was 16.12 seconds in recovery and 15.16 seconds in the rerun, versus
29.79 seconds before; these runs at different times do not constitute a
controlled latency benchmark.

This is an inspected regression corpus, not an unseen benchmark. Equal
aggregate classification scores do not mean identical predictions: three
items changed classification between the two recovery runs. Age agreement
improved mainly through recovered detection coverage; assessed gold-pun age
agreement ranged from 68.7% to 71.6% and remains a weakness. The original
all-age metric includes literal controls that this wordplay-age pipeline
does not assess. Both passes are retained in the
[complete comparison, remaining errors and audit](docs/corpus_recovery_20261004.md).

### Evaluation datasets and historical results

The project-curated corpus contains 60 items: 25 wordplay examples and 35
`ONE_SENSE_ONLY` controls. Its 180 age labels are curator annotations, not
observed child-comprehension measurements. See the
[annotation guidelines](corpus/annotation_guidelines.md).

The repository also includes the 2,250-item homographic SemEval-2017 Task 7
split. It has no human age annotations. The [task paper](https://aclanthology.org/S17-2005/)
describes its detection, location and interpretation tasks. This revision has
not been rerun on that full split. Earlier SemEval and September corpus scores
retain their original source versions in the [historical audit](docs/benchmark_audit.md);
they do not measure the current pipeline.

The [published October 4 evaluation records](docs/evaluations/README.md) retain
both current passes and the preceding regression. Their scores can be recomputed
without provider calls. Fresh-inference commands are below.

## How the pipeline works

The current design prioritizes a reliable, bounded pipeline: every required
stage must complete with usable evidence, uncertainty stays explicit, and
failure stops dependent work. Detection and age outputs are separate. The
historical benchmark results above predate this design. The October 4
regression run evaluates the current source; fresh corpus runs are needed
to assess subsequent changes and performance variation.

```text
Text + explicitly requested ages
  -> L0-pre: validate and normalize
  -> L1: tokenize and route genre
  -> L2: retrieve lexical evidence
  -> L3: rank the original candidate shortlist
  -> L4: choose target + anchor readings in context   [LLM, one shortlist request]
  -> L5: assess semantic resolution                 [LLM]
  -> L6: assess distinctness + compact age estimates [LLM, same request]
  -> L7: validate cached understanding estimates     [local, ages only]
  -> L8: derive content/inference verdicts           [local, passed ages only]
  -> L0-post: report detection, scope and age outcomes

FAIL / UNKNOWN / ERROR -> skip dependent work -> L0-post
Age failure            -> retain detection, leave affected age outputs unknown
```

![CRACK analysis pipeline from input validation through final classification](assets/crack-pipeline.svg)

### Layer responsibilities

| Layer | Input and responsibility | Result and stopping behavior | Model requests |
|---|---|---|---:|
| **L0-pre — input** | Normalize Unicode and whitespace; check length and character content. Defaults: 3–500 characters, non-ASCII ratio at most 0.15. | Valid normalized text, or ERROR; invalid input stops analysis. No joke judgment here. | 0 |
| **L1 — surface** | Use regex to tokenize and select dialogue, definitional, QA or declarative analysis. Record question, negation and speaker-turn flags. | `L1Result`; no invented lemmas or POS tags. | 0 |
| **L2 — lexical evidence** | Retrieve WordNet senses, multiword expressions and compound-split proposals; attach available SemCor counts and local AoA values with lookup methods. | `L2Result`; empty retrieval is UNKNOWN. A missing individual word rating remains null. Dictionary senses are proposals, not proof of contextual wordplay. | 0 |
| **L3 — ranking** | Rank terms using lexical contrast and frequency balance; preserve supported split options. Requested age does not affect ranking. | `L3Result`, default top 8 candidates; no candidates is UNKNOWN. The ranked tail is metadata only. | 0 |
| **L4 — selection and anchoring** | Compare the original shortlist against the whole text in one request; choose the target that best explains the wordplay and return two meanings, exact source anchors, relation and resolving sense. | PASS selects the target. Rejection, UNKNOWN or invalid output stops; no request for another candidate. The selected target must belong to the supplied shortlist. | At most 1 |
| **L5 — resolution** | Check that the selected readings form coherent wordplay in the supplied context using the genre-specific scoring branch. | RESOLUTION_PASS continues. RESOLUTION_FAIL, insufficient context or execution failure stops; no return to L4. | At most 1 |
| **L6 — distinctness** | Check materially different meanings and separate paraphrases. When ages are requested, include compact age estimates in this same response. | SENSES_DISTINCT continues; senses too close rejects; an unassessed result remains UNKNOWN. Age preparation/validation failures do not replace valid detection findings. | At most 1 |
| **L7 — comprehension** | Locally validate L6's cached age keys and estimate fields; attach AoA citations directly from lookup. Consider vocabulary, both readings, wordplay and necessary background knowledge. | Per-age comprehension, reason and estimated barrier. Only ages with FULLY_COMPREHENSIBLE proceed to L8. Missing/malformed age data fails age assessment. | 0 |
| **L8 — appropriateness** | Locally consume the same cached estimate for ages that passed L7. Keep surface content and inferential accessibility as separate true/false/null axes. | Derive per-age appropriateness; content rejection needs a source quote, inference rejection a named prerequisite. Unknown axes never become automatic passes. | 0 |
| **L0-post — finalization** | Combine completed detection evidence and available age results. Run even when earlier stages stop. | Final detection status, detailed classification, scope, review reason and per-age verdicts. | 0 |

The default L3 ranking score is `0.7 * contrast + 0.3 * balance`. Contrast
uses WordNet lexical categories; balance uses smoothed SemCor counts. Missing
counts do not establish observed balanced usage. The score orders proposals;
it is not a probability that a term is a pun. Definitional heads and repeated
eligible terms can receive priority in the shortlist.

### L5 resolution branches

Each branch uses its existing weighted subscores; this reliability revision
preserves those weights and thresholds.

| Branch | Assessed relationship | Pass threshold |
|---|---|---:|
| QA riddle | Polarity/event direction, answer relevance, causal fit, agent fit and tense/aspect fit | 0.46, with polarity/direction at least 0.05 |
| Definitional one-liner | Literal setup, exploitation of the split and contrast strength | 0.60 |
| Dialogue misunderstanding | Plausible misunderstanding, clear contrast and speaker intention | 0.60 |
| Declarative | Availability of both readings, unexpected resolving sense and incongruity | 0.25 |

A self-contained question without an answer turn uses the existing declarative
branch. An explicit contradiction in a relationship necessary for the claimed
wordplay rejects resolution regardless of the average score. Required scores
must be finite numbers in [0, 1]; inadequate evidence uses null scores and a
reason. The resulting resolution score is not calibrated confidence. See
[L5 calibration and its limitations](docs/L5_CALIBRATION.md).

L6 checks lexical granularity and paraphrases the meanings themselves. A
conventional reading can be evoked by context without a second event actually
happening or a second literal sentence being true. This does not permit invented
meanings or unsupported topic associations. L6 requires materially different
readings; it does not require them to exclude each other in the real world. `suppresses_other` and the historical
`ambiguity_ablation` field are diagnostics, not positive gates. No controlled
rewrite or separate rewritten-text request is required.

### Failure, uncertainty and final decisions

**Service recovery and semantic stopping are separate.** A service retry repeats
the same assessment after a provider error; model fallback means advancing a
configured Gemini model chain after exhausted server errors. A negative,
uncertain or invalid answer does not trigger either mechanism to obtain a pass.

| Layer state | Meaning | Action |
|---|---|---|
| PASS | Required positive assessment completed | Continue |
| FAIL | A completed assessment rejected the proposal | Stop dependent layers |
| UNKNOWN | A required fact or assessment is unavailable | Stop dependent layers; preserve uncertainty |
| ERROR | Execution failed, output was incomplete, or response validation rejected it | Stop dependent layers; record the error |
| SKIPPED | A dependency did not pass or the task was not requested | No judgment is claimed |

L0-post retains the compatibility trace status `OK` when finalization succeeds.
This means the verdict was produced; the verdict's `detection_status` determines
whether detection passed, rejected the proposal, stayed unknown or failed.

| Stage/backend | Retry or fallback definition |
|---|---|
| L0–L3 | Local work only. Empty evidence/candidates is UNKNOWN; execution errors stop. Missing individual AoA ratings stay null. No model fills missing lexical facts. |
| L4–L6, OpenAI-compatible | Same-model service retries: up to four application backoff iterations with 2/4/8-second waits for the helper's recognized rate-limit/server-error messages. No model/provider fallback. |
| L4/L6, Gemini | Four attempts per configured model after ServerError, with 2/4/8-second waits; then the layer's Gemini model chain. ClientError, including 429, stops here. |
| L5, Gemini | Five attempts per model for 500/502/503/504, with 2/4/8/16-second waits; then the configured chain. A transient 429 with a positive retry delay may retry once; quota failure, invalid JSON and truncation stop. |
| L4–L6, Anthropic | One application call; installed SDK retries may apply. No pipeline model fallback. |
| L7/L8 | No requests or fallback. Malformed shared age data fails the age stage; valid per-age uncertainty stays unknown. Completed detection survives age failures. |
| L0-post | Finalize available evidence even after stopping. A finalization error produces EXECUTION_FAILED. No replacement semantic assessment. |

The default Gemini chains use `gemini-3.6-flash` then `gemini-3.8-flash`;
settings can change them. OpenAI-compatible error recognition currently uses
message text, rather than a uniform typed HTTP policy. SDK-internal retries and
request-parameter compatibility retries can add calls beyond application
counters. There is no enforced whole-item wall-clock deadline. See the
[exact failure/retry/fallback policy and accounting limits](docs/provider_failure_policy.md)
for each trigger, stop condition and recording limitation.

L4 compares the default shortlist of up to eight terms in one response. It
locates the lexical interaction in the whole text before choosing a target;
it does not accept the first plausible dictionary contrast. The target must
explain the wordplay itself, not a contrast that belongs to a different word.
Deferred terms are never promoted, and L5/L6 rejection never resumes L4.
`--candidate-budget` limits terms offered in this one request; raising it above
8 does not expand the default L3 shortlist. `considered_terms` records the
supplied list, while `findings` contains only the chosen validated finding.
Other candidates do not receive fabricated individual verdicts. The old
`--no-candidate-continuation` flag is a compatibility no-op.

Missing fields, invented source quotes, invalid states, non-finite scores and
truncated/refused responses cannot become successful evidence. Invalid output
fails without corrective model requests. Failed/skipped stages discard partial
and downstream results. Required resolving senses, scores, acquisition ages
and appropriateness passes are not filled with defaults. Validation checks
structure and source substrings; semantic correctness still depends on the
model and requires corpus evaluation.

| Final detection status | Meaning |
|---|---|
| `PUN` | Valid L4 PASS + L5 RESOLUTION_PASS + L6 SENSES_DISTINCT |
| `NON_PUN` | A completed check rejected the wordplay in the bounded detector search |
| `INSUFFICIENT_EVIDENCE` | Required context or a completed assessment is missing |
| `EXECUTION_FAILED` | Execution or response validation failed |
| `OUT_OF_SCOPE` | An assessed mechanism falls outside the supported detector |

A negative result is the detector's finding, not proof that every dictionary
reading was exhausted. Unknown/error outputs remain separate from negatives.
Only a confirmed pun exposes dual readings and joke analysis in the interface.
The scope field describes the mechanism and is not itself proof of a pun; the
occurrence of soundalike spellings alone does not establish homophone wordplay.

### Age design and call budget

The age task is part of **L6's existing request**. Each requested age receives
one compact understanding judgment (`LIKELY`, `UNLIKELY` or `UNKNOWN`), an
estimated barrier when unlikely, separate content/inference findings
(`true`, `false` or `null`), a short reason and any required negative evidence.
L7/L8 validate and aggregate the cached answer locally, without new requests.

| Understanding estimate | L7 result |
|---|---|
| LIKELY | FULLY_COMPREHENSIBLE |
| UNLIKELY, sentence vocabulary or sense A barrier | PARTIALLY_COMPREHENSIBLE |
| UNLIKELY, sense B barrier | SENSE_B_TOO_ADVANCED |
| UNLIKELY, wordplay or background barrier | WORDPLAY_SKILL_TOO_ADVANCED; the summary names the actual barrier |
| UNKNOWN | AOA_UNKNOWN |

AoA citations describe word-level ratings and retain their lookup methods;
derived values are marked and missing values remain null. They are not measured
acquisition ages of each sense or individual child comprehension. New records
leave numeric sense/floor fields null: no default AoA of five, secondary-sense
plus-two rule or fixed genre age floor. A model can estimate contextual
familiarity without a word rating, but inadequate evidence must remain unknown.

L8 checks only ages that passed comprehension. Other ages retain unknown
appropriateness. In a multi-age batch, one age's uncertain understanding does
not stop local processing for other ages that passed. Missing/malformed shared
age data or age-resource preparation failure leaves age results unknown while
preserving completed detection. No requested ages means detection-only mode:
L6 omits age estimates and L7/L8 are skipped. The web interface requests only
the selected age; corpus runs retain each item's explicit age list.

With the default shortlist and successful provider responses:

- Completed positive: **3 requests total** — one L4 shortlist request, one L5
  request and one L6 request, including ages.
- Detection plus age assessment: **at most 3 requests** per item.
- L0–L3 and L7/L8: **0 model requests**. Rejection/uncertainty can stop earlier.

These bounds exclude transport/SDK retries, request-parameter compatibility
and configured Gemini model fallback for service errors. There are no retries to obtain a more favorable
semantic answer or repair invalid output. Adding ages adds tokens to L6 even
though it adds no request. The October 4 comparison reports observed call
counts, trace durations and age agreement; age discrimination remains limited.
`--concurrency` changes how many corpus items run together, not per-item call
budgets. Lexical-reader access is synchronized; provider requests can overlap.

Implementation details: [ARCHITECTURE.md](ARCHITECTURE.md),
[response validation](docs/response_validation.md) and
[failure recovery policy](docs/provider_failure_policy.md) and
[age evidence](docs/age_evidence.md). Current record versions are detection
contract `6`, candidate selection `4`, age contract `3` and age aggregation `4`.

## Installation

Use Python 3.11 or later:

```bash
git clone https://github.com/Jyz922/Crack.git
cd Crack
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

CRACK needs an API key for the selected LLM provider. Copy `.env.example` to `.env`, then set the provider key and, if needed, `DOUBLETAKE_BACKEND` (`openai`, `gemini`, `anthropic`, or `deepseek`). You can also pass a provider with `--backend`.

Analyze one text:

```bash
crack --text "Why don't skeletons fight? Because they have no guts." --age 8 --backend openai
```

The interactive web interface is optional:

```bash
pip install -e ".[web]"
crack --serve
```

## Reproduce a run

To rebuild the SemEval files from the official archive and evaluate a fresh run, configure a provider API key first:

```bash
python scripts/prepare_semeval.py
crack --input corpus/semeval_blind.jsonl \
  --eval corpus/semeval_gold.jsonl \
  --output runs/semeval_results.jsonl \
  --backend openai --concurrency 8 --candidate-budget 8
```

Optional meaning-interpretation evaluation has its own
[tasks, metrics and commands](docs/semeval_pungraph_evaluation.md).

To regenerate the project-curated blind and gold files from their annotation source:

```bash
python scripts/build_project_corpus.py
```

### Test the current project corpus

From the repository root, with the virtual environment installed and the
chosen provider key configured, run fresh inference on the 60-item corpus:

```bash
.venv/bin/python -m crack.runner \
  --input corpus/joke_corpus_blind.jsonl \
  --eval corpus/joke_corpus_gold.jsonl \
  --output runs/corpus_reliability \
  --backend openai --concurrency 8 --candidate-budget 8
```

Replace `openai` with your chosen backend. The input file supplies each item's
requested ages (the current corpus uses ages 6, 8, 10 and 12 across its items);
`--age` applies only to `--text`, not batch input. Gold labels are read for
scoring after inference and are not supplied to model prompts.

Each invocation creates a timestamped directory without overwriting the saved
benchmark records:

```text
runs/corpus_reliability/<UTC-timestamp>/
  records.jsonl    Per-item results, source evidence, stage states and durations
  evaluation.json Detection metrics, outcome counts and age-label agreement
  run_meta.json   Source/prompt/input hashes, nonsecret settings and run metadata
```

Compare detection **all-item accuracy**, **decision coverage**, decided-item
accuracy, binary precision/recall/F1 and outcome counts together. UNKNOWN and
ERROR must remain visible; improved decided-item accuracy alone can result
from more abstentions. `binary_detection` stores precision, recall and F1 as
`precision_on_decided`, `recall_on_decided` and `f1_on_decided`, with abstentions
reported separately. For age results, compare annotation agreement alongside
assessment coverage. `age_gold_puns` separately reports all 75 age labels for
the 25 annotated puns, keeping missed puns in that denominator. The original
180-label metrics remain unchanged and include literal-text controls that the
current wordplay-age pipeline does not assess. Inspect failing traces and L4 attempts before attributing
an error to detection quality; stage durations provide runtime evidence.

Use a fresh run for this revision. `--resume` reuses only compatible,
current-version decided records with matching text, ages, source/prompt hashes
and settings, and no ERROR/UNKNOWN traces. Older pipeline outputs cannot be
silently resumed as current results. The corpus command makes real provider
requests; offline tests below do not run the corpus or establish live accuracy.

These commands regenerate predictions and metrics from the selected corpus. New runs record their configured provider, model and source/prompt hashes. The CLI also prints age-label agreement; SemEval has no human age annotations, so its reported benchmark scores evaluate pun detection.

New evaluations report **decision coverage**, **accuracy over all items**, and
**accuracy over decided items** together. Unresolved and failed items remain
separate from negative predictions. The benchmark scores above describe their
saved runs; results under the current response contract require a fresh run.
Age-label agreement is reported with assessment coverage. See the
[response checks](docs/response_validation.md) and
[repair review and evaluation protocol](docs/repair_review.md).
Prompt changes can be compared with the
[controlled comparison procedure](docs/prompt_cleanup_comparison.md).

Run the current offline contract and pipeline regressions with:

```bash
pip install -e ".[test]"
pytest -q -m "not live"
```

## Repository layout

```text
src/crack/       Pipeline, provider clients, schemas, and CLI
src/crack/prompts/  LLM prompt templates
corpus/          Blind inputs, gold labels, and annotation guidelines
data/            AoA data file and local lexical resources
scripts/         Dataset preparation and analysis utilities
tests/           Unit and offline integration tests
runs/            Selected evaluation summaries and records
docs/            Architecture notes and benchmark audit
```

## License and citation

CRACK is distributed under the [MIT License](LICENSE).

If you use the SemEval-2017 Task 7 data, cite its task paper:

```bibtex
@inproceedings{miller-etal-2017-semeval,
  title = "{S}em{E}val-2017 Task 7: Detection and Interpretation of {E}nglish Puns",
  author = "Miller, Tristan and Hempelmann, Christian and Gurevych, Iryna",
  booktitle = "Proceedings of the 11th International Workshop on Semantic Evaluation ({S}em{E}val-2017)",
  year = "2017",
  pages = "58--68",
  doi = "10.18653/v1/S17-2005"
}
```
