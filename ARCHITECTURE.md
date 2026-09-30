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
| L5 | Assess whether the joke's setup and punchline resolve coherently. | `l5_resolution.py` |
| L6 | Check whether the two readings are distinct enough to support wordplay. | `l6_distinctness.py` |
| L7 | Estimate comprehension by requested age using AoA data and heuristic rules. | `l7_comprehension.py` |
| L8 | Assess surface-content and inferential appropriateness separately. | `l8_appropriateness.py` |
| L0-post | Combine evidence into a final class and scope label. | `l0_scope.py` |

The runner records a `LayerTrace` for each stage. If a stage's result removes the evidence required downstream, later stages can return a skipped or insufficient-context status. The individual layer functions are also called directly in tests and tools.

## Lexical evidence and candidate ranking

L2 uses NLTK WordNet and WordNet lemma counts associated with SemCor. Age estimates come from the Kuperman AoA data in `data/aoa_kuperman.csv`. Data lookup and candidate ranking are deterministic for a fixed local resource version. AoA values are word-level estimates; they do not establish that a particular child knows a word or understands a joke.

L3 ranks candidate terms without using the requested target age. Age-dependent judgments are handled later by L7, so the candidate list is intended to stay the same when only the requested age changes.

L4 prompts for quotes that support each proposed reading. The implementation can verify that a returned quote occurs in the input text. This checks textual grounding, but it does not prove that the interpretation is correct or funny.

## Model-assisted stages

L4–L8 use provider clients from `providers.py`. The configured provider and model can vary by layer; API keys and settings can be supplied through the environment. Model output is parsed into typed Pydantic schemas. Parsing and schema checks constrain output shape, not semantic correctness.

L5 uses genre-specific result schemas. QA riddles use weighted subscores for polarity or event direction, answer relevance, causal fit, agent compatibility, and tense/aspect fit. Other genres use their own subscores. Thresholds are stored in `config.py`; their calibration evidence and known weaknesses are described in `docs/L5_CALIBRATION.md`.

## Evaluation notes

The README reports the SemEval comparison and a full run on the current 60-item project-curated corpus. The curated-corpus predictions match the current input texts; its item-level records and summary are tracked under `runs/`. The historical SemEval prediction file is not tracked, so its published score is supported by the saved summary and audit. See [`docs/benchmark_audit.md`](docs/benchmark_audit.md) for the verification details and run provenance.

No token-saving rate, hallucination-elimination rate, child-safety guarantee, or state-of-the-art ranking is established by the current evaluation artifacts.
