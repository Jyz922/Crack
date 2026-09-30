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

### Project-curated corpus score: not valid for the current 60 items

The current corpus has 60 items: 25 positive wordplay examples and 35 `ONE_SENSE_ONLY` controls. The committed `runs/course_corpus_eval.json` reports 53/60 (88.33%). The records do not support treating that as a fresh evaluation of the current texts:

- `N07`–`N10` do not appear in the earlier 110-item result file. The local corpus-generation script filled them by copying `N02`'s record and changing the ID, text, tokens, and age fields.
- Eight other records have text that differs from the current blind input: `J21`, `J25`, and `D20`–`D25`. Their stage outputs still come from the earlier text.
- Only 48 rows are both non-copied and text-matched. Those rows score 43/48 against the current labels, but they are a selected subset and are not a full-corpus benchmark result.

The age labels are project judgments and the repository does not provide annotator identities, adjudication records, agreement statistics, or a child study. The README therefore reports no aggregate accuracy for this corpus.

### L5 calibration report: diagnostic, not benchmark performance

`docs/L5_CALIBRATION.md` records five repeated runs for a small hand-selected prompt fixture set. It reports both unstable verdicts and expected-case failures, so it is useful for prompt and threshold diagnosis but is not a general accuracy estimate. It is timestamped 2026-09-24; its displayed threshold (`0.6`) is historical and differs from the current QA threshold in `src/crack/config.py` (`0.46`).

### Comparison claims and citations

- The SemEval-2017 Task 7 paper is [S17-2005](https://aclanthology.org/S17-2005/). The README previously cited S17-2007, which is a different SemEval paper.
- Zou and Lu's pun detection/location paper is [N19-1217](https://aclanthology.org/N19-1217/), not N19-1218. Its reported setting is not directly comparable to the CRACK run on the official test split.
- The PunGraph paper's Table 1 reports pun reasoning and sense-explanation metrics. Its homographic-pun figures are not pun-detection accuracy/F1, so they do not support the README's former leaderboard ranking.

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
