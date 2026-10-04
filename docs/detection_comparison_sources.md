# Detection evaluation references

These sources describe different evaluation datasets, tasks and prompting
conditions. They do not establish performance for the current CRACK revision.

- [Miller et al., SemEval-2017 Task 7](https://aclanthology.org/S17-2005/):
  distinguishes homographic/heterographic detection, location and interpretation.
- [Xiao et al., ICIC 2026](https://link.springer.com/chapter/10.1007/978-981-92-3520-9_1):
  describes a three-example LLM detection setting and a separate heterographic
  consensus analysis. Its prompt setting differs from CRACK's pipeline.
- [Zangari et al., EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1419/):
  uses PunEval, JOKER and NAP, mixing homographic and heterographic examples,
  rather than the original full homographic SemEval split.
- [Xu et al., EMNLP 2024](https://aclanthology.org/2024.emnlp-main.657/):
  analyzes recognition, prompt bias and agreement under its own task setup.

Use matching texts, gold labels, supplied information and scoring policies for
an experiment. CRACK's current results and their limitations are documented
in the [October 4 regression comparison](corpus_recovery_20261004.md).
