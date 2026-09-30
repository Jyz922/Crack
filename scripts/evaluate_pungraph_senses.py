#!/usr/bin/env python3
"""Re-score saved CRACK sense explanations on SemEval Subtask 3.

This is an offline evaluation: it does not call a language model. It follows
PunGraph's published max-cosine rule, but the paper does not identify the
sentence encoder or the result-table threshold. The defaults here therefore
define an explicit local re-evaluation protocol, not a reproduction of the
paper's exact scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any

import numpy as np


SUBTASK2_GOLD = "semeval2017_task7/data/test/subtask2-homographic-test.gold"
SUBTASK3_GOLD = "semeval2017_task7/data/test/subtask3-homographic-test.gold"
DEFAULT_PREDICTIONS = Path("runs/semeval_results.jsonl")
DEFAULT_GOLD = Path("corpus/semeval_gold.jsonl")
DEFAULT_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


def _read_jsonl(path: Path, id_key: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            row_id = str(row[id_key])
            if row_id in records:
                raise ValueError(f"Duplicate {id_key}={row_id!r} in {path}:{line_number}")
            records[row_id] = row
    return records


def _official_subtask3_ids(archive_path: Path) -> list[str]:
    """Map official Subtask 3 target-word IDs back to Subtask 1 text IDs."""
    with tarfile.open(archive_path, mode="r:xz") as archive:
        g2_file = archive.extractfile(SUBTASK2_GOLD)
        g3_file = archive.extractfile(SUBTASK3_GOLD)
        if g2_file is None or g3_file is None:
            raise ValueError("Official Subtask 2/3 gold files are missing from the archive")
        text_by_target = {
            target_id: text_id
            for text_id, target_id in (
                line.split("\t") for line in g2_file.read().decode("utf-8").splitlines() if line.strip()
            )
        }
        target_ids = [
            line.split("\t", maxsplit=1)[0]
            for line in g3_file.read().decode("utf-8").splitlines()
            if line.strip()
        ]

    missing = [target_id for target_id in target_ids if target_id not in text_by_target]
    if missing:
        raise ValueError(f"{len(missing)} Subtask 3 target IDs are absent from Subtask 2 gold")
    text_ids = [text_by_target[target_id] for target_id in target_ids]
    if len(text_ids) != len(set(text_ids)):
        raise ValueError("Official Subtask 3 text IDs are not unique")
    return text_ids


def evaluate(
    archive_path: Path,
    predictions_path: Path,
    gold_path: Path,
    *,
    model_name: str,
    cache_dir: Path | None,
    thresholds: tuple[float, ...],
) -> dict[str, Any]:
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise SystemExit("Install the optional evaluator with: pip install -e '.[eval]'") from exc

    ids = _official_subtask3_ids(archive_path)
    predictions = _read_jsonl(predictions_path, "item_id")
    gold = _read_jsonl(gold_path, "id")
    missing_ids = [item_id for item_id in ids if item_id not in predictions or item_id not in gold]
    if missing_ids:
        raise ValueError(f"{len(missing_ids)} official items are missing from predictions or gold")

    pred_senses: list[tuple[str, str]] = []
    gold_senses: list[tuple[str, str]] = []
    missing_prediction_count = 0
    for item_id in ids:
        l4 = predictions[item_id].get("l4_result") or {}
        predicted_pair = (str(l4.get("sense_a") or ""), str(l4.get("sense_b") or ""))
        reference_pair = (str(gold[item_id].get("sense_a") or ""), str(gold[item_id].get("sense_b") or ""))
        if not all(reference_pair):
            raise ValueError(f"Official item {item_id} has an incomplete gold sense pair")
        if not all(predicted_pair):
            missing_prediction_count += 1
        pred_senses.append(predicted_pair)
        gold_senses.append(reference_pair)

    texts = [text for pred, ref in zip(pred_senses, gold_senses) for text in (*pred, *ref)]
    model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir) if cache_dir else None)
    vectors = np.asarray(list(model.embed(texts)), dtype=np.float32)
    if vectors.shape[0] != len(texts):
        raise ValueError("Encoder returned an unexpected number of embeddings")
    # Normalize explicitly so the dot product is cosine similarity even if a
    # different FastEmbed model changes its default normalization behavior.
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)
    sims = np.empty((len(ids), 2, 2), dtype=np.float32)
    for i in range(len(ids)):
        block = vectors[i * 4 : i * 4 + 4]
        sims[i] = block[:2] @ block[2:].T

    max_sim_per_prediction = sims.max(axis=2)
    metrics: dict[str, dict[str, Any]] = {}
    for threshold in thresholds:
        per_sense = max_sim_per_prediction >= threshold
        both = per_sense.all(axis=1)
        any_one = per_sense.any(axis=1)
        # Secondary stricter statistic: require a one-to-one match between the
        # two generated explanations and the two gold definitions.
        one_to_one = np.maximum(
            np.minimum(sims[:, 0, 0], sims[:, 1, 1]),
            np.minimum(sims[:, 0, 1], sims[:, 1, 0]),
        ) >= threshold
        metrics[f"{threshold:.2f}"] = {
            "homographic_sense_accuracy": int(both.sum()) / len(ids),
            "homographic_sense_accuracy_count": int(both.sum()),
            "partial_matching_accuracy": int(any_one.sum()) / len(ids),
            "partial_matching_accuracy_count": int(any_one.sum()),
            "one_to_one_two_sense_accuracy": int(one_to_one.sum()) / len(ids),
            "one_to_one_two_sense_accuracy_count": int(one_to_one.sum()),
        }

    return {
        "evaluation": "offline post-hoc re-scoring of saved CRACK outputs",
        "benchmark_subset": "SemEval-2017 Task 7 Subtask 3 (official homographic interpretation gold IDs)",
        "n": len(ids),
        "encoder": model_name,
        "similarity": "cosine over normalized sentence embeddings",
        "scoring_rule": (
            "For each generated sense, take max cosine against either of the two gold glosses; "
            "Acc requires both generated senses >= threshold; PMA requires at least one."
        ),
        "paper_protocol_note": (
            "PunGraph describes cosine matching and a predefined semantic threshold, but does not "
            "name the encoder or publish the result-table threshold. The reported threshold is an "
            "explicit local choice, not a claim to reproduce the paper's exact evaluator."
        ),
        "missing_prediction_pairs_counted_incorrect": missing_prediction_count,
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "threshold_metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Official SemEval Task 7 .tar.xz")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--model", default=DEFAULT_ENCODER)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--thresholds", default=",".join(f"{x:.2f}" for x in DEFAULT_THRESHOLDS))
    parser.add_argument("--output", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()
    thresholds = tuple(float(value) for value in args.thresholds.split(","))
    result = evaluate(
        args.archive,
        args.predictions,
        args.gold,
        model_name=args.model,
        cache_dir=args.cache_dir,
        thresholds=thresholds,
    )
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
