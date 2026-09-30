# CRACK

[![Version: v1.0.0](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/Jyz922/Crack/releases/tag/v1.0.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CRACK** (Computational Resolution & Anchoring of Comedy & Knowledge) is a research prototype for analyzing English wordplay. It combines lexical resources such as WordNet and age-of-acquisition data with optional LLM judgments. For each input, it can identify a likely ambiguous word, record text spans supporting the readings, assess the joke's resolution, and estimate comprehension and appropriateness for requested ages.

CRACK focuses on homographic wordplay (one spelling with multiple meanings) and compound resegmentation. It does not aim to recognize every kind of humor. Its LLM judgments can vary by provider and model; age and safety outputs are estimates, not validated child-safety guarantees.

<p align="center">
  <img src="assets/demo.gif" alt="CRACK interactive analysis interface" width="100%">
</p>

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

These are local-run results. Counts and metric arithmetic match the available per-item run file. The run file and complete model configuration are not committed, so the exact model calls cannot be verified from a clean checkout. Location scores are omitted because the saved candidate lists do not reproduce the reported top-1 and top-3 counts; see [the benchmark audit](docs/benchmark_audit.md).

The comparison below covers binary homographic-pun detection; pun-sense interpretation scores measure a different task.

### SemEval-2017 Task 7 detection comparison

Ranked by reported F1, the table includes the task-paper systems and later SemEval evaluations. Fermi's result is omitted because it covers only 675 of 2,250 contexts. CRACK ranks **1st of 11 results**.

![SemEval-2017 Task 7 homographic pun detection ranking by reported F1](assets/semeval-detection-ranking.svg)

**Sources and settings:** Original task results are from [Miller et al. (2017), Table 2](https://aclanthology.org/S17-2005.pdf). N-Hance was an out-of-competition system; ECNU evaluated 2,237 items. Feng et al.'s second setting trains on self-collected data and evaluates on the official set. Diao et al. describe training on Pun of the Day and testing on SemEval; the three model variants report no per-model item counts, and the paper does not identify the data used for 5-fold tuning.

### Other reported results

[Diao et al. (2018), Table 3](https://aclanthology.org/D18-1272.pdf) reports these additional scores:

| Model | Paper-reported F1 |
|---|---:|
| WECA | 89.21%* |
| LSTM | 82.43%* |

Table 3's WECA precision and recall (89.19%, 90.64%) imply an F1 of about 89.91%, while the table reports 89.21% and the discussion gives 87.45%. The LSTM precision and recall (81.80%, 83.70%) imply about 82.74%, while the table reports 82.43%. Table 4's WECA result of 90.98% uses a 675-item subset.

Further cross-validation scores include Zhou et al. (2020) at 94.9% and Zou & Lu (2019) at 92.2% using 10-fold CV, and Feng et al.'s 93.0% first setting using 5-fold CV. See [Feng et al. (2020), Table 1 and notes](https://ceur-ws.org/Vol-2624/paper3.pdf).

### Project-curated corpus

`corpus/joke_corpus_blind.jsonl` and `corpus/joke_corpus_gold.jsonl` contain 60 project-curated items: 25 positive wordplay examples and 35 `ONE_SENSE_ONLY` controls (25 de-joked examples and 10 ordinary statements). The labels and age judgments are project annotations; the repository does not include an annotator agreement study.

The existing 53/60 result is **not a valid score for the current 60 texts**: four records were copied from another item's output, and eight saved predictions refer to different text than the current corpus. The README therefore does not report an overall accuracy for this corpus. See [the benchmark audit](docs/benchmark_audit.md) and [annotation guidelines](corpus/annotation_guidelines.md).

## How the pipeline works

CRACK processes each input through lexical analysis, LLM-assisted wordplay checks, and age-specific estimates. L0 validates the input before analysis and assigns the final classification after L1–L8.

![CRACK analysis pipeline from input validation through final classification](assets/crack-pipeline.svg)

Stages can stop or be skipped when required evidence is missing. See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details.

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
