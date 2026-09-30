# CRACK

[![Version: v1.0.0](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/Jyz922/Crack/releases/tag/v1.0.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CRACK** (Computational Resolution & Anchoring of Comedy & Knowledge) is a research prototype for analyzing English wordplay. It combines lexical resources such as WordNet and age-of-acquisition data with optional LLM judgments. For each input, it can identify a likely ambiguous word, record text spans supporting the readings, assess the joke's resolution, and estimate comprehension and appropriateness for requested ages.

CRACK focuses on homographic wordplay (one spelling with multiple meanings) and compound resegmentation. It does not aim to recognize every kind of humor. Its LLM judgments can vary by provider and model; age and safety outputs are estimates, not validated child-safety guarantees.

<p align="center">
  <img src="assets/demo.gif" alt="CRACK interactive analysis interface" width="100%">
</p>

## How the pipeline works

The pipeline is named L0–L8. L0 runs before and after the analysis stages: it validates the input and assigns the final classification.

| Stage | What it does |
|---|---|
| L0 | Checks input and supported wordplay scope; assigns the final class. |
| L1 | Tokenizes the text and selects a genre branch. |
| L2 | Retrieves WordNet senses, SemCor frequency data, and available AoA values. |
| L3 | Ranks ambiguous-word and compound-split candidates. |
| L4 | Uses an LLM to assess whether distinct readings are supported by text spans. |
| L5 | Assesses whether the setup and punchline form a coherent resolution. |
| L6 | Checks whether the proposed senses are meaningfully distinct. |
| L7 | Estimates comprehension for each requested age using AoA data and heuristics. |
| L8 | Separately estimates surface-content and inference-related appropriateness. |

Stages may stop early when a required condition fails. Typed output schemas make results easier to inspect, but do not guarantee that a model judgment is correct.

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details.

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

## Evaluation data and reported results

### SemEval-2017 Task 7

The repository includes the homographic test split: 2,250 items, comprising 1,607 annotated puns and 643 non-puns. The conversion script downloads the official task archive and creates separate blind-input and gold-label files. See the [task paper](https://aclanthology.org/S17-2005/) and the [official results and data page](https://alt.qcri.org/semeval2017/task7/index.php?id=results).

The committed summary reports the following detection results:

| Metric | Reported value | Count |
|---|---:|---:|
| Accuracy | 82.84% | 1,864 / 2,250 |
| Precision | 89.11% | 1,391 / 1,561 predicted puns |
| Recall | 86.56% | 1,391 / 1,607 annotated puns |
| F1 | 87.82% | Derived from the precision and recall above |
| Correctly rejected non-puns (`ONE_SENSE_ONLY`) | 73.56% | 473 / 643 |

These are **reported local-run results, not an independently verified leaderboard claim**. The classification counts and metric arithmetic match the locally available per-item run file. That roughly 50 MB file and its run metadata are ignored by Git, so a clean checkout contains only the summary, not the records needed to verify the model calls. The saved metadata identifies the OpenAI backend but does not pin every model/configuration field. The previous location scores are omitted because the reported top-1 and top-3 counts do not reproduce from the saved L3 candidate lists with the documented ranking. See [the benchmark audit](docs/benchmark_audit.md) for details.

No state-of-the-art claim is made. Results from other papers are not directly comparable unless the task, split, labels, and metric are the same. In particular, pun-sense interpretation scores should not be presented as pun-detection scores.

### Historical SemEval comparison (unofficial)

The table compares homographic-pun detection F1 scores on the SemEval-2017 Task 7 benchmark. It includes the task-paper results and later evaluations on the official dataset. Excluding Fermi's partial-set result, CRACK ranks **1st of 11 scored results**. It is 1st among the **7 results with explicitly reported full coverage**; if Diao et al.'s three variants are assumed to cover the full SemEval test set, it is 1st of 10 full-set results. Other published scores found in later papers are listed separately below when their evaluation setup or reported metrics prevent a clean rank.

| Rank | System | F1 | Evaluated items | Evaluation setting |
|---:|---|---:|---:|---|
| 1 | CRACK (local run) | 87.82% | 2,250 / 2,250 | Local run; provider/model provenance incomplete |
| 2 | [Feng et al. (2020), second setting](https://ceur-ws.org/Vol-2624/paper3.pdf) | 87.50% | 2,250 / 2,250 | Trained on self-collected data; evaluated on the official dataset |
| 3 | [Diao et al. (2018), Bi-LSTM-E](https://aclanthology.org/D18-1272.pdf) | 85.46% | 2,250* | Pun of the Day training; SemEval test |
| 4 | [Diao et al. (2018), Bi-LSTM-Attention](https://aclanthology.org/D18-1272.pdf) | 85.26% | 2,250* | Pun of the Day training; SemEval test |
| 5 | [Diao et al. (2018), Bi-LSTM](https://aclanthology.org/D18-1272.pdf) | 84.51% | 2,250* | Pun of the Day training; SemEval test |
| 6 | N-Hance (out of competition) | 83.50% | 2,250 / 2,250 | SemEval result |
| 7 | Duluth | 82.54% | 2,250 / 2,250 | SemEval result |
| 8 | JU_CSE_NLP | 80.63% | 2,250 / 2,250 | SemEval result |
| 9 | PunFields | 76.51% | 2,250 / 2,250 | SemEval result |
| 10 | ECNU | 67.85% | 2,237 / 2,250 | Partial coverage |
| 11 | UWAV | 55.87% | 2,250 / 2,250 | SemEval result |

**Note:** This is an illustrative comparison, not an official leaderboard rank. CRACK's score comes from a local run whose provider/model provenance is incomplete. N-Hance was submitted after the official evaluation period, and ECNU's score covers 2,237 items. The original task scores and coverage are from [Miller et al. (2017), Table 2](https://aclanthology.org/S17-2005.pdf). Feng et al.'s 87.50% is the paper's external-training “second setting”; its 93.0% “first setting” uses 5-fold cross-validation and is not included in this ranking. Diao et al. describe training on Pun of the Day and testing on SemEval; the `2,250*` coverage for its three ranked variants is inferred from that test-set description, not explicitly reported per model. The same paper mentions 5-fold tuning but does not specify which data were used for that tuning, so those rows have an additional protocol uncertainty.

### Additional published results (not included in the rank)

[Diao et al. (2018), Table 3](https://aclanthology.org/D18-1272.pdf) also reports WECA and LSTM results, but their reported F1 values do not agree with their precision and recall. They are shown here for completeness but are not ranked:

| Model | Paper-reported F1 |
|---|---:|
| WECA | 89.21%* |
| LSTM | 82.43%* |

The asterisks flag reporting inconsistencies in the paper. For WECA, Table 3 reports precision 89.19%, recall 90.64%, and F1 89.21%; those precision and recall values imply an F1 of about 89.91%, while the discussion gives 87.45%. The LSTM row's precision and recall (81.80% and 83.70%) imply an F1 of about 82.74%, not the reported 82.43%. The three Diao et al. rows in the ranked table have F1 values consistent with their reported precision and recall. The paper's separate Table 4 WECA result (90.98%) uses 675 SemEval examples and is excluded because it is a partial-set result.

Later papers also report higher cross-validation scores on the same benchmark: Zhou et al. (2020) 94.9% and Zou & Lu (2019) 92.2% with 10-fold cross-validation, and Feng et al.'s first setting at 93.0% with 5-fold cross-validation. These are not ranked with the full-test results above because their train/test folds overlap the benchmark set. The cross-validation settings and scores are summarized in [Feng et al. (2020), Table 1 and notes](https://ceur-ws.org/Vol-2624/paper3.pdf).

### PunGraph paper: related reasoning results

[PunGraph (arXiv, 2026)](https://arxiv.org/abs/2609.16557) reports two **pun-reasoning** tasks on SemEval: predicting the alternative word for heterographic puns, and explaining the two senses of homographic puns. Its homographic scores assess generated sense explanations, not binary pun detection. The following values are copied from PunGraph's Table 1 and are shown as a paper-reported reference; CRACK is not ranked in this table.

| Model | Heterographic reasoning F1 | Homographic sense Acc. / PMA / F1 |
|---|---:|---:|
| GPT-4o | 79.45% | 76.27% / 98.54% / 87.35% |
| Gemini 2.0 Flash | 77.36% | 71.08% / 98.69% / 84.56% |
| DeepSeek-V3.2 | 80.31% | 66.26% / 98.15% / 82.12% |
| MiniCPM-8.7B | 37.86% | 40.71% / 93.07% / 66.64% |
| Qwen-2.5-7B | 37.47% | 34.65% / 90.80% / 62.42% |
| Qwen-3.5-27B | 74.06% | 68.95% / 97.61% / 83.20% |
| Llama 4 Maverick | 73.77% | 66.26% / 97.84% / 82.00% |
| PunIntended | 16.65% | 26.35% / 85.25% / 50.98% |
| GCR | 51.19% | 43.04% / 93.12% / 37.19% |
| ReKG-MCTS | 68.97% | 22.11% / 78.04% / 48.41% |
| PunGraph-Qwen-2.5-7B | 59.18% | 45.71% / 93.38% / 65.11% |
| PunGraph-Qwen-3.5-27B | 79.86% | 76.18% / 98.84% / 85.71% |
| PunGraph-Llama 4 Maverick | 83.41% | 71.80% / 97.46% / 83.43% |

These values are from PunGraph's [Table 1](https://arxiv.org/html/2609.16557v1#S5.T1). They are a separate task reference, not a CRACK ranking or pun-detection leaderboard.

### Project-curated corpus

`corpus/joke_corpus_blind.jsonl` and `corpus/joke_corpus_gold.jsonl` contain 60 project-curated items: 25 positive wordplay examples and 35 `ONE_SENSE_ONLY` controls (25 de-joked examples and 10 ordinary statements). The labels and age judgments are project annotations; the repository does not include an annotator agreement study.

The existing 53/60 result is **not a valid score for the current 60 texts**: four records were copied from another item's output, and eight saved predictions refer to different text than the current corpus. The README therefore does not report an overall accuracy for this corpus. See [the benchmark audit](docs/benchmark_audit.md) and [annotation guidelines](corpus/annotation_guidelines.md).

## Reproduce a run

To rebuild the SemEval files from the official archive and evaluate a fresh run, configure a provider API key first:

```bash
python scripts/prepare_semeval.py
crack --input corpus/semeval_blind.jsonl \
  --eval corpus/semeval_gold.jsonl \
  --output runs/semeval_results.jsonl \
  --backend openai --concurrency 10
```

The model, provider version, and response may change between runs. The command produces a new run; it is not expected to recreate the saved scores exactly. The CLI's evaluator reports classification and age-label agreement. The SemEval age labels are assigned by the conversion script for compatibility and are not human annotations, so that age-agreement number should not be interpreted as evidence of developmental accuracy.

Run the test suite with:

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
