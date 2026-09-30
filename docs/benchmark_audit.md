# Benchmark and claim audit

**Audit date:** 2026-09-30
**Scope:** README claims, the tracked score summaries, the locally available run records, corpus construction, and cited benchmark papers.

## Findings

### SemEval detection score: arithmetic checks out; provenance is incomplete

The local `runs/semeval_results.jsonl` contains 2,250 records. Re-running the repository's `evaluate_run()` against `corpus/semeval_gold.jsonl` gives 1,864 correct classifications (82.84%) and the same confusion counts as `runs/semeval_results_eval.json`:

- 1,391 of 1,607 positive homographic-pun items were classified as `VALID_HOMOGRAPH_JOKE`.
- 473 of 643 negative items were classified as `ONE_SENSE_ONLY`.
- Precision is 1,391 / 1,561 = 89.11%; recall is 1,391 / 1,607 = 86.56%; their harmonic mean is 87.82% F1.

This verifies the arithmetic on the locally available records. It does **not** independently verify that the saved records came from the claimed live model call. `runs/semeval_results.jsonl` and its timestamped run metadata are ignored by Git. The committed `runs/semeval_subtask_report.json` is only a summary. The local run metadata says the backend was OpenAI but does not save the model ID; individual L5 records say `gpt-6-luna`, but there are no provider response IDs or signed call receipts. Thus the reported detection result is plausible and internally consistent, but its execution provenance cannot be independently established from a clean clone.

The previously published location counts (1,227/1,607 top-1 and 1,390/1,607 top-3) are not reproducible from the locally available L3 candidate lists using normalized exact matching on the gold target term: that check yields 1,202/1,607 top-1 and 1,379/1,607 top-3. A separate scoring definition may explain the difference, but no implementation for it is committed. The README no longer reports the location numbers.

The SemEval converter assigns `{"8": "FULLY_AGE_APPROPRIATE"}` to every item rather than loading age annotations. Consequently, the reported 89.47% SemEval age-label match is not evidence of age-comprehension accuracy and should not be used as such.

### Project-curated corpus: full current run

On 2026-09-30, CRACK evaluated all 60 items in the current blind corpus with the OpenAI backend and configured `gpt-6-luna` model. The final per-item file has 60 unique IDs, exact text matches for all 60 current inputs, and no layer errors. The run used code commit `aba25110abcad2eaf04f43353b12ed82167becf1`.

Exact-label accuracy is 56/60 (93.33%). For binary pun detection, `VALID_HOMOGRAPH_JOKE` and `VALID_COMPOUND_SPLIT_JOKE` count as positive and `ONE_SENSE_ONLY` as negative: TP=25, FP=3, FN=0, TN=32; precision=89.29%, recall=100.00%, F1=94.34%. Age-comprehension outputs match 142/180 project annotations (78.89%). The full confusion matrix and run configuration are in [`../runs/course_corpus_eval.json`](../runs/course_corpus_eval.json), with item-level outputs in [`../runs/course_corpus_records.jsonl`](../runs/course_corpus_records.jsonl).

The first concurrent pass produced L2 WordNet errors for 12 items. Those 12 were rerun serially, and the 48 clean outputs from the first pass were retained. The final saved result replaces the earlier 53/60 summary, which included copied records for `N07`–`N10` and predictions for stale text in `J21`, `J25`, and `D20`–`D25`.

The age-comprehension labels are project annotations informed by AoA data and curator judgment; the reported age match rate is agreement with those labels.

### L5 calibration report: diagnostic, not benchmark performance

`docs/L5_CALIBRATION.md` records five repeated runs for a small hand-selected prompt fixture set. It reports both unstable verdicts and expected-case failures, so it is useful for prompt and threshold diagnosis but is not a general accuracy estimate. It is timestamped 2026-09-24; its displayed threshold (`0.6`) is historical and differs from the current QA threshold in `src/crack/config.py` (`0.46`).

### Comparison claims and citations

- The SemEval-2017 Task 7 paper is [S17-2005](https://aclanthology.org/S17-2005/). The README previously cited S17-2007, which is a different SemEval paper.
- Zou and Lu's pun detection/location paper is [N19-1217](https://aclanthology.org/N19-1217/), not N19-1218. Its reported setting is not directly comparable to the CRACK run on the official test split.
- The PunGraph paper's Table 1 reports pun reasoning and sense-explanation metrics. Its homographic-pun figures are not pun-detection accuracy/F1, so they do not support the README's former leaderboard ranking.

### PunGraph homographic sense re-score: saved outputs, local protocol

The ignored local `runs/semeval_results.jsonl` contains generated `sense_a`/`sense_b` text, so this comparison did not call a model or regenerate predictions. The official Subtask 3 IDs were recovered from the SemEval archive by joining its interpretation gold file to the Subtask 2 target-word IDs. All 1,298 official items joined to the local prediction and gold files. Seventeen did not have a complete generated sense pair and were counted incorrect.

The offline re-score uses `sentence-transformers/all-MiniLM-L6-v2` through FastEmbed and cosine similarity. For each generated explanation, it takes the maximum similarity to either official gold gloss. At threshold 0.50, Acc requires both generated explanations to pass; PMA requires at least one. This gives 446/1,298 (34.36%) Acc and 949/1,298 (73.11%) PMA. A stricter one-to-one matching variant gives 429/1,298 (33.05%) exact-pair accuracy.

F1 is not reported for CRACK because the paper does not provide enough detail to reconstruct that calculation from its outputs.

These values are an exploratory re-score, not an exact reproduction of PunGraph Table 1. The paper describes cosine similarity and a predefined semantic threshold but does not name its embedding encoder or give the Table 1 threshold. It mentions 0.50 for the initial error-filtering stage; this audit selected 0.50 as a transparent local threshold, not as a confirmed paper setting. No cross-paper ranking is reported from this re-score. Across thresholds 0.30–0.70, CRACK's Acc varies from 67.80% to 9.94%, so the score is too threshold-sensitive to support a stable placement. CRACK's inference run also has incomplete provider/model provenance and does not receive the pun word as a supplied input, unlike PunGraph's task setup.

The re-score can be rerun with `pip install -e '.[eval]'` and `python scripts/evaluate_pungraph_senses.py --archive /path/to/semeval2017_task7.tar.xz --cache-dir /path/to/embedding-cache`, provided the ignored local prediction file is available.

The external leaderboard and "SOTA" wording were removed. CRACK's reported detection score has not been independently reproduced against a literature-wide leaderboard.

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
