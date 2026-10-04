"""Official SemEval references and explicit local interpretation scoring.

Gold glosses are used only by the offline evaluator. Inference inputs contain
either just the text, or the text and the marked target for the interpretation
task. The latter is a separate experiment, never a detection prediction.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_URL = "https://alt.qcri.org/semeval2017/task7/data/uploads/semeval2017_task7.tar.xz"
WORDNET31_URL = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet31.zip"
ARCHIVE_SHA256 = "70e82d89a102fced7dd1b1db90daa4ead55357d399d23f4d99e888634b4f4d0a"
WORDNET31_SHA256 = "2a9e7da7d0c17ad875e4171a4d28ae17ab6969c7d67f1cf0f59d65c66d0fdd37"
DEFAULT_ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70)
PRIMARY_THRESHOLD = 0.50
PROTOCOL_VERSION = "crack-semeval-interpretation-v2"
REFERENCES_PATH = REPO_ROOT / "docs" / "benchmark_references.json"
_DATA_PREFIX = "semeval2017_task7/data/test/"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path, id_key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        key = str(row[id_key])
        if key in rows:
            raise ValueError(f"Duplicate {id_key}={key!r} in {path}:{i}")
        rows[key] = row
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def download_if_missing(url: str, path: Path) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "CRACK benchmark preparation"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read()
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(path)


def _clean_text(tokens: list[str]) -> str:
    # Same text conversion as scripts/prepare_semeval.py, with no gold hints.
    from nltk.tokenize.treebank import TreebankWordDetokenizer
    text = TreebankWordDetokenizer().detokenize(tokens)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([A-Za-z]+)\s+-\s+([A-Za-z]+)", r"\1-\2", text)
    return re.sub(r"([A-Za-z]+)'\s+([A-Za-z]+)", r"\1'\2", text).strip()


def _official_records(archive_path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    with tarfile.open(archive_path, "r:xz") as archive:
        def read(name: str) -> bytes:
            handle = archive.extractfile(_DATA_PREFIX + name)
            if handle is None:
                raise ValueError(f"Missing official file: {name}")
            return handle.read()

        detection: dict[str, int] = {}
        for line in read("subtask1-homographic-test.gold").decode().splitlines():
            item_id, label = line.split()
            if item_id in detection or label not in {"0", "1"}:
                raise ValueError("Invalid official detection key")
            detection[item_id] = int(label)
        items: dict[str, dict[str, Any]] = {}
        words: dict[str, tuple[str, str]] = {}
        for element in ET.fromstring(read("subtask1-homographic-test.xml")).findall("text"):
            item_id = element.attrib["id"]
            if item_id in items:
                raise ValueError(f"Duplicate official text ID: {item_id}")
            tokens = []
            for word in element.findall("word"):
                token = word.text or ""
                tokens.append(token)
                word_id = word.attrib["id"]
                if word_id in words:
                    raise ValueError(f"Duplicate official word ID: {word_id}")
                words[word_id] = (item_id, token)
            items[item_id] = {"id": item_id, "text": _clean_text(tokens), "is_pun": detection[item_id]}
        if set(items) != set(detection):
            raise ValueError("Official detection XML/key IDs disagree")
        targets = {}
        for line in read("subtask2-homographic-test.gold").decode().splitlines():
            item_id, word_id = line.split()
            if word_id in targets or word_id not in words or words[word_id][0] != item_id:
                raise ValueError(f"Invalid official target: {word_id}")
            targets[word_id] = item_id
        interpretation = []
        seen: set[str] = set()
        for line in read("subtask3-homographic-test.gold").decode().splitlines():
            word_id, first, second = line.split()
            item_id = targets[word_id]
            if item_id in seen or not items[item_id]["is_pun"]:
                raise ValueError(f"Invalid interpretation ID: {item_id}")
            seen.add(item_id)
            interpretation.append({
                "id": item_id, "text": items[item_id]["text"],
                "target_word_id": word_id, "given_target": words[word_id][1],
                "sense_key_groups": [first.split(";"), second.split(";")],
            })
    if len(items) != 2250 or sum(row["is_pun"] for row in items.values()) != 1607 or len(interpretation) != 1298:
        raise ValueError("Unexpected official homographic split counts")
    return items, interpretation


def _wordnet31_glosses(path: Path) -> dict[str, str]:
    # Read the exact 3.1 index, avoiding 3.0 offset mapping and lemma fallbacks.
    with zipfile.ZipFile(path) as archive:
        index_name = next(n for n in archive.namelist() if n.endswith("/index.sense"))
        prefix = index_name.rsplit("/", 1)[0] + "/"
        gloss_by_offset: dict[tuple[str, str], str] = {}
        for name, pos in (("noun", "n"), ("verb", "v"), ("adj", "a"), ("adv", "r")):
            for line in archive.read(prefix + "data." + name).decode().splitlines():
                offset = line[:8]
                if offset.isdigit() and "|" in line:
                    gloss = line.split("|", 1)[1].strip()
                    gloss_by_offset[(pos, offset)] = re.split(r';\s*"', gloss, maxsplit=1)[0].strip()
        positions = {"1": "n", "2": "v", "3": "a", "4": "r", "5": "a"}
        result = {}
        for line in archive.read(index_name).decode().splitlines():
            key, offset, *_ = line.split()
            pos = positions[key.split("%", 1)[1][0]]
            result[key] = gloss_by_offset[(pos, offset)]
        return result


def prepare_references(archive_path: Path, wordnet31_path: Path, output: Path) -> dict[str, Any]:
    for path, expected in ((archive_path, ARCHIVE_SHA256), (wordnet31_path, WORDNET31_SHA256)):
        if sha256(path) != expected:
            raise ValueError(f"Reference resource checksum mismatch: {path}")
    items, interpretation = _official_records(archive_path)
    dictionary = _wordnet31_glosses(wordnet31_path)
    unresolved = sorted({key for row in interpretation for group in row["sense_key_groups"] for key in group if key not in dictionary})
    if unresolved:
        raise ValueError(f"Unresolved official WordNet 3.1 keys; no fallback applied: {unresolved}")
    output.mkdir(parents=True, exist_ok=True)
    inputs_path = output / "interpretation_input.jsonl"
    gold_path = output / "interpretation_gold.jsonl"
    with inputs_path.open("w", encoding="utf-8") as inputs, gold_path.open("w", encoding="utf-8") as gold:
        for row in interpretation:
            inputs.write(json.dumps({k: row[k] for k in ("id", "text", "given_target", "target_word_id")}, ensure_ascii=False) + "\n")
            groups = [[dictionary[key] for key in group] for group in row["sense_key_groups"]]
            gold.write(json.dumps({**row, "gloss_groups": groups}, ensure_ascii=False) + "\n")
    manifest = {
        "protocol_version": PROTOCOL_VERSION, "detection_items": len(items),
        "positive_items": 1607, "negative_items": 643, "interpretation_items": len(interpretation),
        "multiple_key_items": sum(any(len(g) > 1 for g in r["sense_key_groups"]) for r in interpretation),
        "wordnet_version": "3.1", "unresolved_gold_keys": [],
        "archive_source": ARCHIVE_URL, "archive_sha256": sha256(archive_path),
        "wordnet_source": WORDNET31_URL, "wordnet_sha256": sha256(wordnet31_path),
        "interpretation_input_sha256": sha256(inputs_path), "interpretation_gold_sha256": sha256(gold_path),
    }
    write_json(output / "reference_manifest.json", manifest)
    return manifest


def verify_detection_inputs(archive: Path, blind: Path, gold: Path) -> None:
    official, _ = _official_records(archive)
    inputs = read_jsonl(blind, "id")
    labels = read_jsonl(gold, "id")
    if set(inputs) != set(official) or set(labels) != set(official):
        raise ValueError("Detection inputs/gold must cover exactly the official 2,250 IDs")
    for item_id, row in official.items():
        expected = "VALID_HOMOGRAPH_JOKE" if row["is_pun"] else "ONE_SENSE_ONLY"
        if inputs[item_id]["text"] != row["text"] or labels[item_id]["gold_label"] != expected:
            raise ValueError(f"Detection data differs from the official split: {item_id}")


def detection_report(evaluation: dict[str, Any]) -> dict[str, Any]:
    binary = evaluation["binary_detection"]
    tp, fp, tn, fn = (binary[k] for k in ("tp", "fp", "tn", "fn"))
    missed = binary["abstentions_by_gold_class"]["positive"]
    positives = tp + fn + missed
    n = binary["eligible_items"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / positives if positives else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn + missed) if 2 * tp + fp + fn + missed else 0.0
    return {
        "task": "homographic pun detection", "items": n,
        "accuracy_all_items": (tp + tn) / n if n else None,
        "precision": precision, "recall_full_gold": recall, "f1_full_gold": f1,
        "tp": tp, "fp": fp, "tn": tn, "fn_decided": fn,
        "unresolved_by_gold_class": binary["abstentions_by_gold_class"],
        "decision_coverage": binary["decided_items"] / n if n else None,
        "outcomes": evaluation["outcome_counts"],
        "metric_policy": "Recall includes all gold puns; unresolved items remain separate and count against full-set accuracy and F1.",
    }


def _accepted_pair(row: dict[str, Any], input_mode: str) -> tuple[str, str] | None:
    from .enums import DetectionStatus
    from .schema import AnalysisRecord
    from .validation import RESPONSE_CONTRACT_VERSION, validate_l4_response
    try:
        if row.get("validation_version") != RESPONSE_CONTRACT_VERSION:
            return None
        record = AnalysisRecord.model_validate({k: v for k, v in row.items() if k != "benchmark_input"})
        if record.l4_result is None or record.l4_result.anchoring_status.value != "PASS":
            return None
        if any(t.layer in {"L0-pre", "L1", "L2", "L3", "L4"} and t.status in {"ERROR", "REJECTED"} for t in record.trace):
            return None
        if input_mode == "end_to_end":
            from .decisions import detection_decision
            from .enums import detection_status_for
            if record.final is None:
                return None
            decision, _ = detection_decision(record, record.final.scope_label)
            if decision != record.final.main_classification or detection_status_for(decision) != DetectionStatus.PUN:
                return None
            if not record.l4_search or record.l4_search.mode != "automatic":
                return None
        else:
            if not record.l4_search or record.l4_search.mode != "target_only":
                return None
            if record.l4_result.target_term != (row.get("benchmark_input") or {}).get("given_target"):
                return None
        result = record.l4_result
        candidates = record.l3_result.candidates if record.l3_result else []
        candidate = next(c for c in candidates if c.term == result.target_term)
        accepted = next(a for a in reversed(record.l4_attempts) if a.accepted and a.candidate_term == candidate.term)
        checked = validate_l4_response(
            accepted.parsed_response, record.text, candidate.term,
            candidate.score_components.get("compound_split", 0.0) == 1.0, candidate.split_options,
        )
        if checked != result.model_dump(mode="json"):
            return None
        return result.sense_a, result.sense_b
    except (ValueError, TypeError, AttributeError, StopIteration):
        return None


def validate_thresholds(thresholds: tuple[float, ...]) -> None:
    if not thresholds or len(set(thresholds)) != len(thresholds) or len({f"{x:.2f}" for x in thresholds}) != len(thresholds):
        raise ValueError("Provide distinct thresholds with at most two decimal places")
    if any(not math.isfinite(t) or not 0 < t <= 1 or round(t, 2) != t for t in thresholds):
        raise ValueError("Semantic thresholds must be finite, in (0, 1], and have at most two decimals")


def encoder_fingerprint(encoder: Any) -> dict[str, Any]:
    directory = getattr(getattr(encoder, "model", None), "_model_dir", None)
    if directory is None:
        raise ValueError("Cannot identify the loaded encoder artifacts for this protocol")
    root = Path(directory)
    artifacts = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    if not artifacts:
        raise ValueError("Loaded encoder artifact directory is empty")
    return {
        "artifact_sha256": artifacts,
        "package_versions": {name: importlib.metadata.version(name) for name in ("fastembed", "onnxruntime", "numpy")},
    }


def evaluate_senses(
    predictions_path: Path, references_path: Path, *, input_mode: str,
    encoder: Any, model_name: str, thresholds: tuple[float, ...], details_path: Path,
) -> dict[str, Any]:
    import numpy as np
    if input_mode not in {"end_to_end", "given_target"}:
        raise ValueError("Unknown interpretation input mode")
    validate_thresholds(thresholds)
    references = read_jsonl(references_path, "id")
    predictions = read_jsonl(predictions_path, "item_id")
    if len(references) != 1298:
        raise ValueError("Interpretation scoring requires all 1,298 official items")
    if input_mode == "given_target" and set(predictions) - set(references):
        raise ValueError("Given-target predictions contain IDs outside the interpretation split")
    pair_by_id = {}
    target_matches = {}
    texts: set[str] = set()
    reasons = {}
    for item_id, ref in references.items():
        row = predictions.get(item_id)
        if row is not None and row["text"] != ref["text"]:
            raise ValueError(f"Prediction text mismatch: {item_id}")
        if row is not None:
            mode = (row.get("l4_search") or {}).get("mode")
            expected_mode = "automatic" if input_mode == "end_to_end" else "target_only"
            if mode is not None and mode != expected_mode:
                raise ValueError(f"Prediction input mode mismatch: {item_id}")
            if input_mode == "end_to_end" and row.get("benchmark_input"):
                raise ValueError(f"End-to-end predictions must not contain supplied targets: {item_id}")
        if row is not None and input_mode == "given_target":
            supplied = row.get("benchmark_input") or {}
            if supplied.get("given_target") != ref["given_target"] or supplied.get("target_word_id") != ref["target_word_id"]:
                raise ValueError(f"Provided target mismatch: {item_id}")
        pair = _accepted_pair(row, input_mode) if row else None
        selected_target = ((row or {}).get("l4_result") or {}).get("target_term", "")
        target_matches[item_id] = selected_target.strip().casefold() == ref["given_target"].strip().casefold()
        reason = "accepted_pair" if pair else "missing_or_unaccepted_pair"
        if pair and not target_matches[item_id]:
            pair, reason = None, "different_target"
        pair_by_id[item_id] = pair
        reasons[item_id] = reason
        texts.update(gloss for group in ref["gloss_groups"] for gloss in group)
        if pair:
            texts.update(pair)
    ordered_texts = sorted(texts)
    vectors = np.asarray(list(encoder.embed(ordered_texts)), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(ordered_texts) or not np.isfinite(vectors).all():
        raise ValueError("Invalid embeddings returned by encoder")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if (norms <= 0).any():
        raise ValueError("Encoder returned a zero-length embedding")
    vectors /= norms
    embedding = dict(zip(ordered_texts, vectors))
    details_path.parent.mkdir(parents=True, exist_ok=True)
    embedding_path = details_path.with_suffix(".embeddings.npz")
    np.savez_compressed(embedding_path, texts=np.asarray(ordered_texts), vectors=vectors)
    counts = {f"{t:.2f}": {"acc_count": 0, "pma_count": 0, "one_to_one_count": 0} for t in thresholds}
    details_path.parent.mkdir(parents=True, exist_ok=True)
    with details_path.open("w", encoding="utf-8") as details:
        for item_id, ref in references.items():
            pair = pair_by_id[item_id]
            scores = None
            flags = {}
            if pair:
                # Each slot may contain several official acceptable senses.
                # Never collapse alternatives or fill a missing prediction.
                scores = np.array([
                    [max(float(embedding[s] @ embedding[g]) for g in group) for group in ref["gloss_groups"]]
                    for s in pair
                ])
            for threshold in thresholds:
                key = f"{threshold:.2f}"
                if scores is None:
                    both = any_one = unique_pair = False
                else:
                    matched = scores.max(axis=1) >= threshold
                    both, any_one = bool(matched.all()), bool(matched.any())
                    unique_pair = bool(max(min(scores[0, 0], scores[1, 1]), min(scores[0, 1], scores[1, 0])) >= threshold)
                flags[key] = {"acc": both, "pma": any_one, "one_to_one": unique_pair}
                for field, value in (("acc_count", both), ("pma_count", any_one), ("one_to_one_count", unique_pair)):
                    counts[key][field] += int(value)
            details.write(json.dumps({
                "item_id": item_id, "target": ref["given_target"], "pair_status": reasons[item_id],
                "selected_target": ((predictions.get(item_id) or {}).get("l4_result") or {}).get("target_term"),
                "target_match": target_matches[item_id],
                "l4_status": ((predictions.get(item_id) or {}).get("l4_result") or {}).get("anchoring_status"),
                "final_detection_status": ((predictions.get(item_id) or {}).get("final") or {}).get("detection_status"),
                "execution_errors": [{"layer": t.get("layer"), "reason": t.get("reason")} for t in (predictions.get(item_id) or {}).get("trace", []) if t.get("status") in {"ERROR", "REJECTED"}],
                "predicted_senses": pair, "gold_sense_keys": ref["sense_key_groups"],
                "gold_gloss_groups": ref["gloss_groups"],
                "cosine_by_gold_slot": scores.tolist() if scores is not None else None,
                "threshold_results": flags,
            }, allow_nan=False) + "\n")
    n = len(references)
    metrics = {
        t: {**c, "acc": c["acc_count"] / n, "pma": c["pma_count"] / n, "one_to_one_accuracy": c["one_to_one_count"] / n}
        for t, c in counts.items()
    }
    accepted_count = sum(p is not None for p in pair_by_id.values())
    return {
        "protocol_version": PROTOCOL_VERSION, "input_mode": input_mode, "items": n,
        "encoder": model_name, "wordnet_reference_version": "3.1", "similarity": "normalized embedding cosine",
        "accepted_pair_count": accepted_count, "pair_coverage": accepted_count / n,
        "exclusion_counts": {reason: sum(r == reason for r in reasons.values()) for reason in sorted(set(reasons.values())) if reason != "accepted_pair"},
        "target_match_count": sum(target_matches.values()),
        "missing_or_unaccepted_pairs_counted_incorrect": n - accepted_count,
        "threshold_metrics": metrics, "primary_threshold": PRIMARY_THRESHOLD,
        "primary_metrics": metrics.get(f"{PRIMARY_THRESHOLD:.2f}"),
        "interpretation_f1": None,
        "comparison_status": "local semantic evaluator; published Table 1 encoder/threshold/F1 formula unavailable",
        "prediction_sha256": sha256(predictions_path), "reference_sha256": sha256(references_path),
        "evaluator_source_sha256": {name: sha256(Path(__file__).parent / name) for name in ("semeval_benchmark.py", "validation.py", "schema.py", "decisions.py")},
        "embedding_artifact": embedding_path.name, "embedding_sha256": sha256(embedding_path),
        "encoder_fingerprint": encoder_fingerprint(encoder),
        "scoring_rule": "Acc: both generated senses match any official gold gloss; PMA: at least one. Also report distinct gold-slot one-to-one matching. Missing/unaccepted pairs fail every threshold.",
        "prediction_policy": "End-to-end requires a validated final PUN at the official target. Given-target scores validated L4 PASS pairs only. Target comparison ignores case/surrounding whitespace only; neither mode uses rejected model responses.",
    }
