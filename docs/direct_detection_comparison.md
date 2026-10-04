# Direct prompting versus CRACK

On 2 October 2026, a fixed direct-prompt baseline using `gpt-6-luna` reached **90.71% accuracy and 93.81% F1** on all 2,250 SemEval-2017 Task 7 homographic detection items. The saved CRACK run using the same requested model reached **81.33% accuracy and 87.27% F1**.

## Results

| System | Accuracy, all items | Precision | Recall, all gold puns | F1, full gold | Decision coverage |
|---|---:|---:|---:|---:|---:|
| Direct prompt, gpt-6-luna | 90.71% | 89.49% | 98.57% | 93.81% | 100.00% |
| CRACK, gpt-6-luna | 81.33% | 88.64% | 85.94% | 87.27% | 97.56% |
| Always predict PUN | 71.42% | 71.42% | 100.00% | 83.33% | 100.00% |

The direct baseline correctly classified **2,041 / 2,250** items; CRACK correctly classified **1,830 / 2,250**. The differences are **+9.38 percentage points in accuracy** and **+6.55 points in F1**.

| System | TP | FP | TN | FN, decided | Unresolved gold positives | Unresolved gold negatives |
|---|---:|---:|---:|---:|---:|---:|
| Direct prompt | 1,584 | 186 | 457 | 23 | 0 | 0 |
| CRACK | 1,381 | 177 | 449 | 188 | 38 | 17 |

Full-gold recall includes all 1,607 positive items. F1 uses `2 × TP / (2 × TP + FP + FN_decided + unresolved_positive)`. Unresolved negatives stay separate from false positives and remain in the accuracy denominator. CRACK's unresolved outcomes comprise 49 insufficient-evidence and six execution-failure records.

## Where the difference occurs

Both systems were correct on 1,739 items. The direct baseline alone was correct on 302, CRACK alone on 91, and neither on 118. There are 399 differing output statuses.

On the **2,195 items where both made a binary decision**, direct-prompt accuracy was **90.75% (1,992 / 2,195)** and CRACK accuracy was **83.37% (1,830 / 2,195)**. The gap therefore also occurs among completed decisions.

The direct baseline recovered **175** positives that CRACK classified as NON_PUN. Their saved traces ended at:

| Rejection stage | Recovered positives |
|---|---:|
| L4 anchoring | 91 |
| L5 resolution | 37 |
| L6 distinctness / ambiguity ablation | 47 |

All 47 L6 cases had `SENSES_TOO_CLOSE` and `UNSUPPORTED`. These are observed rejection locations; a controlled ablation is needed to identify the effect of each stage. Inspect candidate selection and L4 first, followed by L5 and L6, while retaining strict checks for original-text quotations and required fields. Develop changes on a separate fixed development set; keep this benchmark's gold labels and thresholds unchanged.

## Runtime

Both runs used eight item workers. The direct baseline completed in **11 minutes 30 seconds**, using **2,250 API calls**, with **zero retries and zero execution failures**. The API reported **601,626 total tokens**: 303,235 prompt tokens and 298,391 completion tokens, including 257,147 reasoning tokens.

| System | Mean item seconds | Median | P95 |
|---|---:|---:|---:|
| Direct prompt | 2.44 | 1.87 | 5.65 |
| CRACK detection traces | 27.80 | 25.72 | 51.20 |

The recorded mean item duration was about **11.4 times shorter** for direct prompting. CRACK durations sum its saved detection-layer traces and exclude L7/L8 age and safety processing. The API calls occurred at different times. CRACK's token usage and exact batch wall time were not recorded.

## Fixed experimental setup

- Exact input and gold copies from `runs/semeval_benchmark/20261002T201740.595224Z/inputs/`.
- One independent request per text, with the [79-word fixed prompt](../experiments/direct_detection/prompt.md); the model received only the instructions and original text.
- Zero-shot classification, without labeled examples, dictionary candidates, target words, age labels or earlier responses.
- Same requested model `gpt-6-luna`; the baseline API responses also reported that model name. Chat Completions JSON mode, 4,096 maximum completion tokens, provider-default temperature, 90-second request timeout.
- Prompt frozen before inference; no prompt tuning on the resulting predictions. Retries could repeat the identical request for transport or format failures. They were not needed.
- CRACK's saved predictions were compared without rerunning or modifying its pipeline. An independent count check reproduced all baseline counts and metrics, and CRACK counts reproduced its saved detection summary.

This experiment measures binary detection. The baseline's forced binary output does not measure uncertainty calibration or provide validated explanations. It is a fresh `gpt-6-luna` experiment; reproducing the ICIC 2026 GPT-4 Turbo 3-shot result requires that paper's experimental configuration.

## Reproduce and inspect

```bash
.venv/bin/python scripts/run_direct_detection_baseline.py \
  --suite runs/semeval_benchmark/20261002T201740.595224Z \
  --model gpt-6-luna \
  --concurrency 8
```

The runner loads the existing API configuration and creates a new timestamped result directory. Recalculate the existing run's metrics without API calls:

```bash
.venv/bin/python scripts/run_direct_detection_baseline.py \
  --suite runs/semeval_benchmark/20261002T201740.595224Z \
  --resume runs/direct_detection_baseline/20261002T231314.834548Z \
  --score-only
```

The [metric snapshot](direct_detection_baseline_20261002.json) includes counts, runtime, token usage and artifact hashes. Full local artifacts are under `runs/direct_detection_baseline/20261002T231314.834548Z/`: frozen prompt and runner, input/gold copies, manifest, raw API responses, per-item timing, evaluation and aligned disagreements. API credentials are excluded.
