# 06 — Optional extensions
Last updated: 2026-10-19 by soundalike docs-planning session (offline, no code written)

Status: **not started**. Back to [HANDOFF](../HANDOFF.md).

Build any of these **only if** [04](04_eval_data.md)'s results show L4 picking
wrong alternates or the finder missing gold targets.

## Checks this session

| Check | Command | Result |
|---|---|---|
| Any extension | none | **NOT run**; nothing implemented |
| Local LM availability | none | **NOT run**; no local LM dependency in `pyproject.toml` |

## Goal

Optional accuracy work after the core works:

- **LM noisy-channel re-ranking**: T* = argmax_T p(P|T)·p(T) over retrieved
  alternates (Jaech et al. 2016).
- **DP resegmentation** of 1–3-token windows into other word sequences, to
  reach multi-word targets (lettuce → let us, alleged → a ledge).
- **Curated similar-sounding list** unioned into retrieval (UWaterloo-style).
- **Dual-support diagnostic** (design.md § L5/L6 prompts): target support
  Δ = log p_LM(s[p→t]) − log p_LM(s); a supporter-set Jaccard below 0.5 between
  the context words that best support each reading; and
  S_ratio = S_local / S_global > 1 (He et al. 2019). This is the notes' own
  proposal, not a published method. It stays a **diagnostic, not a gate**,
  until validated.

## Files to create/modify

- Create `src/crack/phonetics/rerank.py` (LM re-ranking)
- Create `src/crack/phonetics/resegment.py` (DP over span phones)
- Create the curated list file and its loader (location: open decision;
  `data/` is gitignored)
- Create `src/crack/soundalike_diagnostic.py` (dual support). Its output goes in
  the record as diagnostic metadata, never into `detection_decision`.
- Modify `src/crack/l3_soundalikes.py` to add `source="resegmentation"` /
  `"curated_list"` alternates.
- Modify `pyproject.toml` (an LM dependency, if adopted).
- Tests per module.

## Interfaces

```python
def rerank(surface: str, alternates: list[Alternate], text: str) -> list[Alternate]
def resegment(tokens: list[str], max_words: int = 3) -> list[Alternate]   # source="resegmentation"
def dual_support(text: str, surface: str, alternate: str) -> dict[str, float]  # delta, jaccard, s_ratio
```

## Acceptance tests

1. Each extension shows a measured gain on 04's dev split (Recall@k or paired
   accuracy), with counts. Otherwise it is not merged.
2. Resegmentation finds `let us` for "Lettuce pray" and `a ledge` for
   "alleged" (sims pinned to 01's observed values).
3. The diagnostic never changes `main_classification`: a test asserts identical
   final labels with it on and off.
4. L4/L5/L6 provider request counts are unchanged (local work only).

## Depends on

[03](03_contract_l3_l4_l0post.md) (end-to-end path) and
[04](04_eval_data.md) results.

## Open decisions

- Local LM (team table: defer; none / distilgpt2 / masked-LM pseudo-likelihood).
- Whether resegmentation output is capped by the same 4 × 3 budget.

## Risks

- A local LM adds a heavy dependency and makes runtime nondeterministic unless
  pinned.
- Resegmentation multiplies candidates and noise.
- A curated list leaks evaluation targets if it is built from the test data.
