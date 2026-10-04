# Benchmark and claim audit

**Audit date:** 2026-09-30
**Detection comparison updated:** 2026-10-02
**Scope:** README claims, the tracked score summaries, the locally available run records, corpus construction, and cited benchmark papers.

The current design and two October 4 regression passes are described in the
[recovery comparison](corpus_recovery_20261004.md). Scores below belong to their
dated historical configurations.

## Findings

### SemEval detection: separate exact-label accuracy from binary F1

The local `runs/semeval_results.jsonl` contains 2,250 records. Re-running the repository's `evaluate_run()` against `corpus/semeval_gold.jsonl` gives 1,864 correct classifications (82.84%) and the same confusion counts as `runs/semeval_results_eval.json`:

- 1,391 of 1,607 positive homographic-pun items were classified as `VALID_HOMOGRAPH_JOKE`.
- 473 of 643 negative items were classified as `ONE_SENSE_ONLY`.
- Those exact-label counts were previously used to report 89.11% precision, 86.56% recall and 87.82% F1. They are not the standard binary detection counts: compound-split detections and several negative output labels were handled inconsistently.

Mapping both `VALID_*_JOKE` labels to positive and the remaining legacy labels to negative gives TP=1,399, FP=146, TN=497, FN=208. The corrected historical binary metrics are **84.27% accuracy, 90.55% precision, 87.06% recall and 88.77% F1**. The 82.84% result remains exact-label accuracy. The old `runs/semeval_subtask_report.json` retains the earlier calculation and is superseded for binary comparisons.

The historical record file and timestamped metadata are ignored by Git. Its metadata records OpenAI but no model ID; individual L5 records name `gpt-6-luna`. Execution provenance remains incomplete for that historical run.

The archived **October 2, 2026** detection run records (`runs/semeval_benchmark/20261002T201740.595224Z/detection/20261002T201740Z/records.jsonl`): TP=1,381, FP=177, TN=449, and 188 decided false negatives. A further 38 gold puns and 17 gold non-puns were unresolved. Full-gold recall includes all 1,607 positives, yielding **81.33% binary accuracy, 88.64% precision, 85.94% recall and 87.27% F1**. Decision coverage is **2,195/2,250 (97.56%)**; outcomes include 49 insufficient-evidence items and six execution failures. The [saved summary](semeval_detection_20261002.json) includes configuration, source hashes and the prediction-file hash.

The previously published location counts (1,227/1,607 top-1 and 1,390/1,607 top-3) are not reproducible from the locally available L3 candidate lists using normalized exact matching on the gold target term: that check yields 1,202/1,607 top-1 and 1,379/1,607 top-3. A separate scoring definition may explain the difference, but no implementation for it is committed. The README no longer reports the location numbers.

The SemEval converter assigns `{"8": "FULLY_AGE_APPROPRIATE"}` to every item rather than loading age annotations. Consequently, the reported 89.47% SemEval age-label match is not evidence of age-comprehension accuracy and should not be used as such.

### Project-curated corpus: full current run

On 2026-09-30, CRACK evaluated all 60 items in the current blind corpus with the OpenAI backend and configured `gpt-6-luna` model. The final per-item file has 60 unique IDs, exact text matches for all 60 current inputs, and no layer errors. The run used code commit `aba25110abcad2eaf04f43353b12ed82167becf1`.

Exact-label accuracy is 56/60 (93.33%). For binary pun detection, `VALID_HOMOGRAPH_JOKE` and `VALID_COMPOUND_SPLIT_JOKE` count as positive and `ONE_SENSE_ONLY` as negative: TP=25, FP=3, FN=0, TN=32; precision=89.29%, recall=100.00%, F1=94.34%. Age-comprehension outputs match 142/180 project annotations (78.89%). The full confusion matrix and run configuration are in [`../runs/course_corpus_eval.json`](../runs/course_corpus_eval.json), with item-level outputs in [`../runs/course_corpus_records.jsonl`](../runs/course_corpus_records.jsonl).

The first concurrent pass produced L2 WordNet errors for 12 items. Those 12 were rerun serially, and the 48 clean outputs from the first pass were retained. The final saved result replaces the earlier 53/60 summary, which included copied records for `N07`–`N10` and predictions for stale text in `J21`, `J25`, and `D20`–`D25`.

The age-comprehension labels are project annotations informed by AoA data and curator judgment; the reported age match rate is agreement with those labels.

An additional source check on 2026-10-02 found evaluation examples in the prompt
files at the recorded September 30 commit, `aba25110abcad2eaf04f43353b12ed82167becf1`.
After case/punctuation normalization, the complete inputs for J01, J05, J24 and
D24 occur in `l4_anchoring.md`, and J23 occurs in `l5_declarative.md`. J24 also
matches verbatim. These examples include word/meaning demonstrations. The 56/60
count is reproducible from the saved predictions, but this inspected corpus is
not an independent unseen evaluation. The overlap does not quantify how much
it affected the score; the later controlled cleanup comparison did not establish
that removing examples alone caused the overall score changes.

### Direct-prompt baseline and attribution

The fresh October 2 direct-prompt baseline used the same 2,250 frozen detection
inputs, gold labels and requested `gpt-6-luna` model. A fixed 79-word zero-shot
prompt produced TP=1,584, FP=186, TN=457 and FN=23, with no unresolved items,
retries or execution failures: 90.71% accuracy and 93.81% F1. The independent
count check reproduced the metrics from the raw responses. See the
[direct-prompt comparison](direct_detection_comparison.md).

Historical CRACK scores describe the combined pipeline, including its LLM
judgments. They did not establish an improvement over directly prompting that
LLM. The current matched-input comparison shows lower detection performance for
the saved CRACK configuration. Stage-level causal attribution still requires
controlled ablations. The historical SemEval run, current SemEval run and direct
baseline must retain their own code versions and scoring policies.

### L5 calibration report: diagnostic, not benchmark performance

`docs/L5_CALIBRATION.md` records five repeated runs for a small hand-selected prompt fixture set. It reports both unstable verdicts and expected-case failures, so it is useful for prompt and threshold diagnosis but is not a general accuracy estimate. It is timestamped 2026-09-24; its displayed threshold (`0.6`) is historical and differs from the current QA threshold in `src/crack/config.py` (`0.46`).

### Comparison claims and citations

- The SemEval-2017 Task 7 paper is [S17-2005](https://aclanthology.org/S17-2005/). The README previously cited S17-2007, which is a different SemEval paper.
- Zou and Lu's pun detection/location paper is [N19-1217](https://aclanthology.org/N19-1217/), not N19-1218. Its reported setting is not directly comparable to the CRACK run on the official test split.
- The PunGraph paper's Table 1 reports pun reasoning and sense-explanation metrics. Its homographic-pun figures are not pun-detection accuracy/F1.
- Xiao et al. (ICIC 2026) supply four new LLM detection results on the 2,250-item homographic set, using three labeled examples. Their headline 96.3% consensus result is heterographic and is excluded. Zangari et al. (EMNLP 2025) report detection F1 on different test sets and are documented separately. See the [evaluation reference notes](detection_comparison_sources.md).

### PunGraph homographic sense re-score: saved outputs, local protocol

The ignored local `runs/semeval_results.jsonl` contains generated `sense_a`/`sense_b` text, so this comparison did not call a model or regenerate predictions. The official Subtask 3 IDs were recovered from the SemEval archive by joining its interpretation gold file to the Subtask 2 target-word IDs. All 1,298 official items joined to the local prediction and gold files. Seventeen did not have a complete generated sense pair and were counted incorrect.

The offline re-score uses `sentence-transformers/all-MiniLM-L6-v2` through FastEmbed and cosine similarity. For each generated explanation, it takes the maximum similarity to either official gold gloss. At threshold 0.50, Acc requires both generated explanations to pass; PMA requires at least one. This gives 446/1,298 (34.36%) Acc and 949/1,298 (73.11%) PMA. A stricter one-to-one matching variant gives 429/1,298 (33.05%) exact-pair accuracy.

F1 is not reported for CRACK because the paper does not provide enough detail to reconstruct that calculation from its outputs.

These values are an exploratory re-score, not an exact reproduction of PunGraph Table 1. The paper describes cosine similarity and a predefined semantic threshold but does not name its embedding encoder or give the Table 1 threshold. It mentions 0.50 for the initial error-filtering stage; this audit selected 0.50 as a transparent local threshold, not as a confirmed paper setting. Across thresholds 0.30–0.70, CRACK's Acc varies from 67.80% to 9.94%, so the score is strongly dependent on the chosen threshold. CRACK's inference run also has incomplete provider/model provenance and does not receive the pun word as a supplied input, unlike PunGraph's task setup.

This is the historical v1 exploratory re-score. The current evaluator uses all
official WordNet 3.1 sense-key alternatives and accepts only validated outputs;
its v2 protocol does not reproduce the old converted-gloss score. See the
[current detection and interpretation workflow](semeval_pungraph_evaluation.md)
for fresh inference, supplied-target evaluation and offline scoring commands.

### Other overclaims removed

- Quote anchoring may reduce unsupported readings; it does not guarantee a correct humor judgment or eliminate hallucinations.
- The repository contains no token-count experiment supporting the former claim of 65–70% token savings.
- The static "332 tests passed" badge was removed because this audit did not run the test suite or establish a current pass count.

## Rechecking the saved SemEval classification arithmetic

On a checkout that has the ignored local record file and installed dependencies:

```bash
python - <<'PY'
from crack.corpus import evaluate_run

print(evaluate_run(
    "runs/semeval_results.jsonl",
    "corpus/semeval_gold.jsonl",
))
PY
```

This recomputes classification and age-label agreement from saved records. It does not verify API provenance, and the age labels should be disregarded for developmental claims as described above.
