#!/usr/bin/env python3
"""Score saved CRACK interpretations without LLM calls.

This evaluator resolves all official WordNet 3.1 sense-key alternatives. Its
encoder and thresholds are an explicit local protocol; PunGraph has not
published enough evaluator settings for an exact Table 1 reproduction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crack.semeval_benchmark import (
    DEFAULT_ENCODER, DEFAULT_THRESHOLDS, evaluate_senses,
    prepare_references, validate_thresholds, write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--wordnet31", type=Path, default=ROOT / "data/semeval_benchmark/wordnet31.zip")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--input-mode", choices=("end_to_end", "given_target"), default="end_to_end")
    parser.add_argument("--model", default=DEFAULT_ENCODER)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/embedding_cache")
    parser.add_argument("--thresholds", default=",".join(f"{t:.2f}" for t in DEFAULT_THRESHOLDS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        thresholds = tuple(float(value) for value in args.thresholds.split(","))
        validate_thresholds(thresholds)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.wordnet31.is_file():
        parser.error("Prepare official resources first: .venv/bin/python scripts/run_semeval_benchmarks.py --prepare-only")
    from fastembed import TextEmbedding
    references = args.output.parent / "official_references"
    manifest = prepare_references(args.archive, args.wordnet31, references)
    encoder = TextEmbedding(model_name=args.model, cache_dir=str(args.cache_dir))
    result = evaluate_senses(
        args.predictions, references / "interpretation_gold.jsonl", input_mode=args.input_mode,
        encoder=encoder, model_name=args.model, thresholds=thresholds,
        details_path=args.output.with_suffix(".per_item.jsonl"),
    )
    result["official_references"] = manifest
    write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
