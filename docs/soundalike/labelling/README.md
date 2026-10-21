# Labelling the soundalike corpus

The instructor requires at least 20 soundalike jokes and 20 negatives. The
labels in `corpus/soundalike_items.jsonl` are the author's; they count only
after two people agree with them independently.

## For each labeller (about 15 minutes)

1. Open your own sheet: `sheet_A.csv` (labeller A) or `sheet_B.csv` (labeller B).
   Do not look at the other sheet, the items file or design.md.
2. For every row, put **Y** in `wordplay` if the sentence contains a deliberate
   play on a similar-sounding word (a word read as another word that sounds
   alike, with both readings supported by the sentence). Otherwise put **N**.
   Ordinary sentences that just contain a word with a homophone are **N**.
3. Optionally write the second reading you heard in `second_reading`
   (for example "way" for "whey").
4. Save as CSV and return the file.

## Then

```powershell
py -3.11 scripts/soundalike_labelling.py agree path\to\filled_A.csv path\to\filled_B.csv
```

This prints Cohen's kappa, keeps a positive only if both labellers said Y and a
negative only if both said N, and writes `corpus/soundalike_validated.json` and
`agreement.md` here. Report the kept counts, not the authored counts.

Regenerate the blank sheets after editing the corpus:
`py -3.11 scripts/build_soundalike_corpus.py` then
`py -3.11 scripts/soundalike_labelling.py sheets`.
