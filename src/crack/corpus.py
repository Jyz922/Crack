"""Blind and gold JSONL corpus loaders with strict field validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .enums import (
    AgeAppropriatenessVerdict,
    ComprehensionStatus,
    Genre,
    MainClassification,
    DetectionStatus,
    detection_status_for,
)

_COMPREHENSION_STATUSES = frozenset({e.value for e in ComprehensionStatus})
_APPROPRIATENESS_STATUSES = frozenset({e.value for e in AgeAppropriatenessVerdict})


@dataclass
class BlindItem:
    id: str
    text: str
    target_ages: list[int]


@dataclass
class GoldItem:
    id: str
    gold_label: MainClassification
    genre: Genre
    ambiguous_term: str
    sense_a: str
    sense_b: str
    expected_age_verdict: dict[str, str]


_BLIND_REQUIRED: frozenset[str] = frozenset({"id", "text", "target_ages"})
_GOLD_REQUIRED: frozenset[str] = frozenset({
    "id",
    "gold_label",
    "genre",
    "ambiguous_term",
    "sense_a",
    "sense_b",
    "expected_age_verdict",
})


def load_blind(path: str | Path) -> list[BlindItem]:
    """Load and validate a blind JSONL corpus file.

    Raises ValueError on malformed JSON, missing fields, unknown fields,
    or duplicate ids.
    """
    items: list[BlindItem] = []
    seen_ids: set[str] = set()

    for lineno, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"blind corpus line {lineno}: invalid JSON — {exc}"
            ) from exc

        _check_fields(obj, _BLIND_REQUIRED, lineno, "blind")

        item_id = obj["id"]
        if item_id in seen_ids:
            raise ValueError(
                f"blind corpus line {lineno}: duplicate id '{item_id}'"
            )
        seen_ids.add(item_id)

        items.append(BlindItem(
            id=item_id,
            text=obj["text"],
            target_ages=obj["target_ages"],
        ))

    return items


def load_gold(path: str | Path) -> dict[str, GoldItem]:
    """Load and validate a gold JSONL corpus file.

    Returns a dict keyed by item id.

    Raises ValueError on malformed JSON, missing fields, unknown fields,
    or duplicate ids.
    """
    items: dict[str, GoldItem] = {}

    for lineno, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"gold corpus line {lineno}: invalid JSON — {exc}"
            ) from exc

        _check_fields(obj, _GOLD_REQUIRED, lineno, "gold")

        item_id = obj["id"]
        if item_id in items:
            raise ValueError(
                f"gold corpus line {lineno}: duplicate id '{item_id}'"
            )

        items[item_id] = GoldItem(
            id=item_id,
            gold_label=MainClassification(obj["gold_label"]),
            genre=Genre(obj["genre"]),
            ambiguous_term=obj["ambiguous_term"],
            sense_a=obj["sense_a"],
            sense_b=obj["sense_b"],
            expected_age_verdict=obj["expected_age_verdict"],
        )

    return items


def join_blind_gold(
    blind: list[BlindItem],
    gold: dict[str, GoldItem],
) -> list[tuple[BlindItem, GoldItem]]:
    """Pair blind items with their gold annotations.

    Raises ValueError if any gold id is absent from the blind set.
    Returns only items present in both sets (blind items without gold are
    included in runs but skipped here).
    """
    blind_ids = {item.id for item in blind}
    gold_only = set(gold) - blind_ids
    if gold_only:
        raise ValueError(
            f"Gold ids not found in blind set: {sorted(gold_only)}"
        )
    return [(item, gold[item.id]) for item in blind if item.id in gold]


def evaluate_run(
    records_path: str | Path,
    gold_path: str | Path,
) -> dict[str, Any]:
    """Report accuracy over all gold items AND accuracy/coverage of decided items.

    Missing records and execution failures never count as negative predictions.
    Precision/recall/F1 use decided binary cases only; coverage is always reported
    alongside them. The all-item accuracy denominator includes abstentions.
    """
    gold_dict = load_gold(gold_path)
    records: dict[str, dict[str, Any]] = {}
    for line in Path(records_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        item_id = rec.get("item_id")
        if item_id in records:
            raise ValueError(f"Duplicate prediction id: {item_id}")
        if item_id not in gold_dict:
            raise ValueError(f"Prediction id missing from gold corpus: {item_id}")
        records[item_id] = rec

    total_items = len(gold_dict)
    correct = decided = total_age = correct_age = assessed_age = 0
    eligible = binary_decided = binary_correct = 0
    tp = fp = tn = fn = 0
    confusion: dict[str, dict[str, int]] = {}
    counts = {s.value: 0 for s in DetectionStatus}
    binary_abstentions = {"positive": 0, "negative": 0}
    unverified_contract_items = 0

    for item_id, gold in gold_dict.items():
        rec = records.get(item_id)
        final = (rec or {}).get("final") or {}
        pred = final.get("main_classification", MainClassification.EXECUTION_FAILED.value)
        if not rec or not final or any(
            t.get("layer") in {"L0-pre", "L1", "L2", "L3", "L4", "L5", "L6", "L0-post"}
            and t.get("status") in {"ERROR", "REJECTED"}
            for t in (rec or {}).get("trace", [])
        ):
            pred = MainClassification.EXECUTION_FAILED.value
        if rec:
            from .validation import RESPONSE_CONTRACT_VERSION
            if rec.get("validation_version") != RESPONSE_CONTRACT_VERSION:
                unverified_contract_items += 1
            else:
                from .schema import AnalysisRecord
                from .decisions import detection_decision
                try:
                    typed = AnalysisRecord.model_validate(rec)
                    verified, _ = detection_decision(typed, typed.final.scope_label)
                    if verified.value != pred:
                        pred = MainClassification.EXECUTION_FAILED.value
                except (ValueError, TypeError, AttributeError):
                    pred = MainClassification.EXECUTION_FAILED.value
        state = detection_status_for(pred)
        counts[state.value] += 1
        is_decided = state in {DetectionStatus.PUN, DetectionStatus.NON_PUN}
        decided += int(is_decided)
        correct += int(is_decided and pred == gold.gold_label.value)
        confusion.setdefault(gold.gold_label.value, {})
        bucket = confusion[gold.gold_label.value]
        bucket[pred] = bucket.get(pred, 0) + 1

        gold_state = detection_status_for(gold.gold_label)
        if gold_state in {DetectionStatus.PUN, DetectionStatus.NON_PUN}:
            eligible += 1
            positive = gold_state == DetectionStatus.PUN
            if is_decided:
                binary_decided += 1
                predicted_positive = state == DetectionStatus.PUN
                binary_correct += int(predicted_positive == positive)
                tp += int(positive and predicted_positive)
                fn += int(positive and not predicted_positive)
                fp += int(not positive and predicted_positive)
                tn += int(not positive and not predicted_positive)
            else:
                binary_abstentions["positive" if positive else "negative"] += 1

        per_age = final.get("per_age", {}) if is_decided else {}
        for age, expected in gold.expected_age_verdict.items():
            total_age += 1
            actual = per_age.get(str(age)) or per_age.get(int(age)) or {}
            field = "comprehension" if expected in _COMPREHENSION_STATUSES else "appropriateness"
            value = actual.get(field)
            valid_statuses = _COMPREHENSION_STATUSES if field == "comprehension" else _APPROPRIATENESS_STATUSES
            if value in valid_statuses and value != ComprehensionStatus.AOA_UNKNOWN.value:
                assessed_age += 1
                correct_age += int(value == expected)

    def ratio(n: int, d: int) -> float | None:
        return round(n / d, 4) if d else None

    return {
        "total_items": total_items,
        "recorded_items": len(records),
        "missing_items": total_items - len(records),
        "unverified_contract_items": unverified_contract_items,
        "correct_classification": correct,
        "classification_accuracy": ratio(correct, total_items),
        "decided_items": decided,
        "decision_coverage": ratio(decided, total_items),
        "classification_accuracy_on_decided": ratio(correct, decided),
        "outcome_counts": counts,
        "confusion_matrix": confusion,
        "total_age_evals": total_age,
        "correct_age_evals": correct_age,
        "age_accuracy": ratio(correct_age, total_age),
        "assessed_age_evals": assessed_age,
        "age_assessment_coverage": ratio(assessed_age, total_age),
        "age_accuracy_on_assessed": ratio(correct_age, assessed_age),
        "binary_detection": {
            "eligible_items": eligible,
            "decided_items": binary_decided,
            "decision_coverage": ratio(binary_decided, eligible),
            "correct": binary_correct,
            "accuracy_all_items": ratio(binary_correct, eligible),
            "accuracy_on_decided": ratio(binary_correct, binary_decided),
            "precision_on_decided": ratio(tp, tp + fp),
            "recall_on_decided": ratio(tp, tp + fn),
            "f1_on_decided": ratio(2 * tp, 2 * tp + fp + fn),
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "abstentions_by_gold_class": binary_abstentions,
        },
    }


def _check_fields(
    obj: dict,
    required: frozenset[str],
    lineno: int,
    corpus: str,
) -> None:
    missing = required - set(obj)
    if missing:
        raise ValueError(
            f"{corpus} corpus line {lineno}: "
            f"missing required fields {sorted(missing)}"
        )
    extra = set(obj) - required
    if extra:
        raise ValueError(
            f"{corpus} corpus line {lineno}: "
            f"unknown fields {sorted(extra)}"
        )
