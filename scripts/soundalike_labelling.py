"""Blind double labelling for the soundalike corpus (workstream 04).

  py -3.11 scripts/soundalike_labelling.py sheets
      Writes docs/soundalike/labelling/sheet_A.csv and sheet_B.csv: every item in
      the same shuffled order, with no labels, pairs or slices. Give one sheet to
      each labeller; they fill the "wordplay" column independently (Y or N).

  py -3.11 scripts/soundalike_labelling.py agree FILLED_A.csv FILLED_B.csv
      Computes Cohen's kappa on Y/N, keeps a positive only if both labellers said
      Y and a negative only if both said N, and writes
      corpus/soundalike_validated.json and docs/soundalike/labelling/agreement.md.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "corpus" / "soundalike_items.jsonl"
OUT_DIR = ROOT / "docs" / "soundalike" / "labelling"
VALIDATED = ROOT / "corpus" / "soundalike_validated.json"
SEED = 7
COLUMNS = ["id", "text", "wordplay", "second_reading", "notes"]


def items() -> list[dict]:
    return [json.loads(l) for l in ITEMS.read_text(encoding="utf-8").splitlines() if l.strip()]


def make_sheets() -> None:
    rows = items()
    order = list(range(len(rows)))
    random.Random(SEED).shuffle(order)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("A", "B"):
        # utf-8-sig so Excel on Windows shows curly quotes and dashes correctly
        with (OUT_DIR / f"sheet_{name}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(COLUMNS)
            for i in order:
                writer.writerow([rows[i]["id"], rows[i]["text"], "", "", ""])
    print(f"Wrote {len(rows)} items to sheet_A.csv and sheet_B.csv in {OUT_DIR}")


def read_sheet(path: Path) -> dict[str, str]:
    out = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mark = (row.get("wordplay") or "").strip().upper()[:1]
            if mark not in {"Y", "N"}:
                raise SystemExit(f"{path.name}: item {row['id']} needs Y or N in 'wordplay', got {row.get('wordplay')!r}")
            out[row["id"]] = mark
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in ("Y", "N")) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def agree(path_a: Path, path_b: Path) -> None:
    rows = {r["id"]: r for r in items()}
    a, b = read_sheet(path_a), read_sheet(path_b)
    if set(a) != set(rows) or set(b) != set(rows):
        raise SystemExit("Both sheets must label exactly the items in corpus/soundalike_items.jsonl")
    ids = sorted(rows)
    kappa = cohen_kappa([a[i] for i in ids], [b[i] for i in ids])
    kept, dropped = [], {}
    for i in ids:
        want = "N" if rows[i]["neg_type"] else "Y"
        if a[i] == b[i] == want:
            kept.append(i)
        else:
            dropped[i] = f"A={a[i]} B={b[i]} expected={want}"
    VALIDATED.write_text(json.dumps({"kappa": round(kappa, 3), "kept": kept, "dropped": dropped},
                                    indent=1) + "\n", encoding="utf-8")
    counts = Counter((rows[i]["slice"], "neg" if rows[i]["neg_type"] else "pos") for i in kept)
    lines = [
        "# Soundalike corpus labelling agreement", "",
        f"Cohen's kappa (Y/N, {len(ids)} items): **{kappa:.3f}**", "",
        "| Slice | Positives kept | Negatives kept |", "|---|---:|---:|",
        *[f"| {s} | {counts[(s, 'pos')]} | {counts[(s, 'neg')]} |" for s in ("seed", "known", "test_text")],
        "", f"Dropped ({len(dropped)}):", "",
        *[f"- {i}: {rows[i]['text']} ({why})" for i, why in dropped.items()], "",
    ]
    (OUT_DIR / "agreement.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    if counts[("seed", "pos")] < 20 or counts[("seed", "neg")] < 20:
        print("WARNING: the seed slice is below 20 positives or 20 negatives after labelling.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "sheets":
        make_sheets()
    elif len(sys.argv) == 4 and sys.argv[1] == "agree":
        agree(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit(__doc__)
