"""Evaluate the soundalike extension (workstream 04). Offline: no provider calls.

  py -3.11 scripts/evaluate_soundalike.py metric      # P1: graded vs binary sound similarity
  py -3.11 scripts/evaluate_soundalike.py finder      # P2: does the finder supply the target?
  py -3.11 scripts/evaluate_soundalike.py baselines   # shortcut baselines on SemEval heterographic
  py -3.11 scripts/evaluate_soundalike.py detection runs/<run>/records.jsonl [--gold FILE] [--all]
      # rescoring a saved live run; by default only items kept by blind labelling

Every rate is printed with its counts: with ~25 positives, one item is ~4 points.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
SIX_PAIRS = [("knight", "night"), ("cat", "cad"), ("bat", "pat"), ("pat", "pit"), ("cat", "cash"), ("drum", "drama")]
TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")  # the same tokenisation as L1 (l1_surface._TOKEN)


def rate(num: int, den: int) -> str:
    return f"{num}/{den} ({num / den:.1%})" if den else "0/0 (n/a)"


def items() -> list[dict]:
    return [json.loads(l) for l in (CORPUS / "soundalike_items.jsonl").read_text(encoding="utf-8").splitlines() if l]


# --- P1 -------------------------------------------------------------------

def binary_similarity(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """The forbidden baseline: phones are either identical (cost 0) or not (cost 1)."""
    from crack.phonetics.lexicon import to_feature_vectors
    p, q = to_feature_vectors(a), to_feature_vectors(b)
    d = [[float(i + j) if 0 in (i, j) else 0.0 for j in range(len(q) + 1)] for i in range(len(p) + 1)]
    for i in range(1, len(p) + 1):
        for j in range(1, len(q) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (p[i - 1] != q[j - 1]))
    return 1 - d[len(p)][len(q)] / max(len(p), len(q), 1)


def auc(pos: list[float], neg: list[float]) -> float:
    wins = sum((x > y) + 0.5 * (x == y) for x in pos for y in neg)
    return wins / (len(pos) * len(neg))


def cmd_metric(args) -> None:
    from crack.phonetics import sound_similarity
    from crack.phonetics.lexicon import _cmu, pronunciations, to_feature_vectors

    print("## P1: sound similarity\n\n| Pair | Graded sim | sim_cal | Binary sim |\n|---|---:|---:|---:|")
    binary_values = []
    for x, y in SIX_PAIRS:
        s = sound_similarity(x, y)
        bvalue = binary_similarity(*s.pron_pair)
        binary_values.append(round(bvalue, 3))
        print(f"| {x}/{y} | {s.sim:.3f} | {s.sim_cal:.3f} | {bvalue:.3f} |")
    print(f"\nDistinct values over the six pairs: graded {len({round(sound_similarity(x, y).sim, 3) for x, y in SIX_PAIRS})}, "
          f"binary {len(set(binary_values))} (binary scoring ties pairs it cannot rank).\n")

    by_len: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    for word in _cmu():
        if word.isalpha():
            prons = pronunciations(word)
            if prons:
                by_len[len(to_feature_vectors(prons[0]))].append(prons[0])
    rng = random.Random(args.seed)
    graded_pos, binary_pos, graded_neg, binary_neg, imperfect = [], [], [], [], []
    for r in items():
        if r["neg_type"] or r["mechanism"] == "resegmentation":
            continue
        target = r["target_word"].split()
        s = sound_similarity(r["pun_word"], target if len(target) > 1 else target[0])
        graded_pos.append(s.sim)
        binary_pos.append(binary_similarity(*s.pron_pair))
        imperfect.append(s.pron_pair[0] != s.pron_pair[1])
        length = len(to_feature_vectors(s.pron_pair[0]))
        pool = by_len.get(length) or by_len[min(by_len, key=lambda k: abs(k - length))]
        for _ in range(args.random_per_pair):
            a, b = rng.sample(pool, 2)
            graded_neg.append(sound_similarity_phones(a, b))
            binary_neg.append(binary_similarity(a, b))
    print(f"Soundalike pairs from the corpus (pun word vs target): {len(graded_pos)}; "
          f"random same-length CMUdict pairs: {len(graded_neg)} (seed {args.seed})\n")
    print("| Scoring | ROC-AUC soundalike vs random |\n|---|---:|")
    print(f"| Graded (PanPhon features) | {auc(graded_pos, graded_neg):.3f} |")
    print(f"| Binary (identical or not) | {auc(binary_pos, binary_neg):.3f} |")
    gi = [x for x, keep in zip(graded_pos, imperfect) if keep]
    bi = [x for x, keep in zip(binary_pos, imperfect) if keep]
    if gi:
        print(f"| Graded, imperfect pairs only ({len(gi)}) | {auc(gi, graded_neg):.3f} |")
        print(f"| Binary, imperfect pairs only ({len(bi)}) | {auc(bi, binary_neg):.3f} |")
    print("\nThe AUC rows measure separation from random words, where an all-or-nothing phone "
          "match is already strong. The graded metric's distinct contribution is ordering close "
          "pairs (the six-pair table), which binary costs collapse into ties.\n")


def sound_similarity_phones(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    from crack.phonetics.similarity import score_pronunciations
    return score_pronunciations(a, b).sim


# --- P2 -------------------------------------------------------------------

def cmd_finder(args) -> None:
    from crack.config import DEFAULT_SETTINGS
    from crack.l0_scope import preprocess_input
    from crack.l1_surface import analyze
    from crack.l3_soundalikes import find_soundalikes

    def found(text: str) -> tuple[set[str], set[str]]:
        text = preprocess_input(text)
        cands = find_soundalikes(analyze(text), text, DEFAULT_SETTINGS)
        return ({c.surface.lower() for c in cands},
                {a.form.lower() for c in cands for a in c.alternates})

    print("## P2: finder\n")
    rows = [r for r in items() if not r["neg_type"] and r["mechanism"] != "resegmentation"]
    hits = sum(r["target_word"].lower() in found(r["text"])[1] for r in rows)
    located = sum(r["pun_word"].lower() in found(r["text"])[0] for r in rows)
    neg_fired = sum(bool(found(r["text"])[0]) for r in items() if r["neg_type"])
    print(f"Soundalike corpus positives: target supplied {rate(hits, len(rows))}; "
          f"pun word flagged {rate(located, len(rows))}")
    print(f"Soundalike corpus negatives where the finder fires anyway: "
          f"{rate(neg_fired, sum(1 for r in items() if r['neg_type']))}\n")
    path = CORPUS / "semeval_heterographic_targets.jsonl"
    if path.exists():
        texts = {json.loads(l)["id"]: json.loads(l)["text"]
                 for l in (CORPUS / "semeval_heterographic_blind.jsonl").read_text(encoding="utf-8").splitlines() if l}
        targets = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]
        sem_hits = sum(bool(set(t.lower() for t in r["target_lemmas"]) & found(texts[r["id"]])[1]) for r in targets)
        print(f"SemEval heterographic (subtask 3, {len(targets)} puns with gold targets): "
              f"target supplied {rate(sem_hits, len(targets))}\n")


# --- Baselines --------------------------------------------------------------

def prf(pred: list[bool], gold: list[bool]) -> str:
    tp = sum(p and g for p, g in zip(pred, gold))
    fp = sum(p and not g for p, g in zip(pred, gold))
    fn = sum(g and not p for p, g in zip(pred, gold))
    tn = len(gold) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    bal = (recall + (tn / (tn + fp) if tn + fp else 0.0)) / 2
    return f"P {precision:.3f} | R {recall:.3f} | F1 {f1:.3f} | balanced acc {bal:.3f} | TP {tp} FP {fp} FN {fn} TN {tn}"


def cmd_baselines(args) -> None:
    gold_path = CORPUS / "semeval_heterographic_gold.jsonl"
    if not gold_path.exists():
        raise SystemExit("Run scripts/prepare_semeval.py --heterographic first")
    texts = {json.loads(l)["id"]: json.loads(l)["text"]
             for l in (CORPUS / "semeval_heterographic_blind.jsonl").read_text(encoding="utf-8").splitlines() if l}
    gold = {json.loads(l)["id"]: json.loads(l)["gold_label"] != "ONE_SENSE_ONLY"
            for l in gold_path.read_text(encoding="utf-8").splitlines() if l}
    ids = sorted(gold)
    g = [gold[i] for i in ids]
    print(f"## Shortcut baselines, SemEval-2017 heterographic ({sum(g)} puns / {len(g)} contexts)\n")
    print(f"- Always 'pun': {prf([True] * len(g), g)}")
    rule = [len(TOKEN.findall(texts[i])) >= 9 or "Tom" in TOKEN.findall(texts[i]) for i in ids]
    print(f"- '>= 9 tokens OR contains Tom' (L1 tokenisation): {prf(rule, g)}")
    tom = sum("Tom" in TOKEN.findall(texts[i]) for i in ids if gold[i]), sum("Tom" in TOKEN.findall(texts[i]) for i in ids if not gold[i])
    print(f"- 'Tom' appears in {tom[0]} puns and {tom[1]} non-puns\n")


# --- Detection rescoring ------------------------------------------------------

def cmd_detection(args) -> None:
    from crack.enums import DetectionStatus, detection_status_for

    meta = {r["id"]: r for r in items()}
    gold = {json.loads(l)["id"]: json.loads(l) for l in Path(args.gold).read_text(encoding="utf-8").splitlines() if l}
    records = {}
    for line in Path(args.records).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            records[rec["item_id"]] = (rec.get("final") or {}).get("main_classification", "EXECUTION_FAILED")
    keep = set(gold)
    validated = CORPUS / "soundalike_validated.json"
    if not args.all and validated.exists():
        keep &= set(json.loads(validated.read_text(encoding="utf-8"))["kept"])
        print(f"Scoring only the {len(keep)} items kept by blind labelling (--all to score every item).\n")
    elif not args.all:
        print("WARNING: no corpus/soundalike_validated.json yet; scoring authored labels.\n")
    missing = sorted(keep - set(records))
    if missing:
        print(f"WARNING: {len(missing)} items have no record: {', '.join(missing[:10])}\n")

    def status(i: str) -> DetectionStatus:
        return detection_status_for(records.get(i, "EXECUTION_FAILED"))

    for slc in ("seed", "known", "test_text", None):
        ids = sorted(i for i in keep if i in records and (slc is None or meta.get(i, {}).get("slice") == slc))
        if not ids:
            continue
        decided = [i for i in ids if status(i) in {DetectionStatus.PUN, DetectionStatus.NON_PUN}]
        print(f"### Slice: {slc or 'all'} ({len(ids)} items; decided {rate(len(decided), len(ids))})\n")
        g = [gold[i]["gold_label"] != "ONE_SENSE_ONLY" for i in ids]
        p = [status(i) == DetectionStatus.PUN for i in ids]
        print(f"- Detection (undecided counted as not-pun): {prf(p, g)}")
        exact = sum(records[i] == gold[i]["gold_label"] for i in ids if gold[i]["gold_label"] != "ONE_SENSE_ONLY")
        print(f"- Exact label on positives (mechanism right): {rate(exact, sum(g))}")
        by_type = defaultdict(lambda: [0, 0])
        for i in ids:
            if meta.get(i, {}).get("neg_type"):
                by_type[meta[i]["neg_type"]][1] += 1
                by_type[meta[i]["neg_type"]][0] += status(i) == DetectionStatus.NON_PUN
        if by_type:
            print("- True-negative rate by negative type: " + "; ".join(
                f"{t} {rate(*by_type[t])}" for t in sorted(by_type)))
        pairs = defaultdict(list)
        for i in ids:
            pairs[meta.get(i, {}).get("pair_id") or i].append(i)
        complete = [m for k, m in pairs.items() if k in m and len(m) > 1]
        ok = sum(all((status(i) == DetectionStatus.PUN) == (gold[i]["gold_label"] != "ONE_SENSE_ONLY") for i in m)
                 for m in complete)
        print(f"- Paired accuracy (a positive and all its negatives right): {rate(ok, len(complete))}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("metric"); m.add_argument("--seed", type=int, default=0); m.add_argument("--random-per-pair", type=int, default=20)
    sub.add_parser("finder"); sub.add_parser("baselines")
    d = sub.add_parser("detection"); d.add_argument("records")
    d.add_argument("--gold", default=str(CORPUS / "soundalike_gold.jsonl")); d.add_argument("--all", action="store_true")
    args = parser.parse_args()
    {"metric": cmd_metric, "finder": cmd_finder, "baselines": cmd_baselines, "detection": cmd_detection}[args.cmd](args)


if __name__ == "__main__":
    main()
