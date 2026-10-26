"""Regenerate data/phonetic_calibration.json (random-pair baselines for sim_cal).

For each segment length L, sample pairs of distinct CMUdict words whose first
pronunciation has exactly L IPA segments, score them with the same weighted
Levenshtein used by crack.phonetics, and store the mean and 95th/99th
percentiles. Deterministic for a fixed seed, dictionary revision and panphon
version.

    py -3.11 scripts/fit_phonetic_calibration.py [--seed 0] [--pairs 1500]
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict

from crack.phonetics import lexicon
from crack.phonetics.calibration import CALIBRATION_PATH
from crack.phonetics.similarity import DEFAULT_INDEL, weighted_levenshtein
from crack.lexical_resources import resource_manifest


def _percentile(sorted_values: list[float], q: float) -> float:
    index = min(len(sorted_values) - 1, max(0, round(q * (len(sorted_values) - 1))))
    return sorted_values[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pairs", type=int, default=1500)
    parser.add_argument("--min-length", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=10)
    args = parser.parse_args()

    by_length: dict[int, list[tuple[str, list]]] = defaultdict(list)
    for word in sorted(lexicon._cmu()):
        if not word.isalpha():
            continue
        prons = lexicon.pronunciations(word)
        if not prons:
            continue
        vectors = lexicon.to_feature_vectors(prons[0])
        by_length[len(vectors)].append((word, vectors))

    rng = random.Random(args.seed)
    lengths = {}
    for length in range(args.min_length, args.max_length + 1):
        pool = by_length.get(length, [])
        if len(pool) < 2:
            continue
        sims = []
        for _ in range(args.pairs):
            (_, p), (_, q) = rng.sample(pool, 2)
            distance, _ = weighted_levenshtein(p, q, DEFAULT_INDEL)
            sims.append(1 - distance / length)
        sims.sort()
        lengths[str(length)] = {
            "mean": round(statistics.fmean(sims), 4),
            "p95": round(_percentile(sims, 0.95), 4),
            "p99": round(_percentile(sims, 0.99), 4),
            "pairs": len(sims),
            "pool_words": len(pool),
        }

    table = {
        "method": "random pairs of distinct alphabetic CMUdict words with equal IPA segment length; "
                  "first pronunciation; weighted Levenshtein, name-aligned panphon weights",
        "lexicon": "cmusphinx/cmudict",
        "lexicon_version": resource_manifest()["resources"]["cmudict"]["version"],
        "lexicon_sha256": resource_manifest()["resources"]["cmudict"]["sha256"],
        "indel": DEFAULT_INDEL,
        "seed": args.seed,
        "pairs_per_length": args.pairs,
        "lengths": lengths,
    }
    CALIBRATION_PATH.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lengths, indent=2))


if __name__ == "__main__":
    main()
