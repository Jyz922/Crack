#!/usr/bin/env python3
"""Run detection and supplied-target interpretation as separate experiments.

Use --prepare-only to fetch public reference resources without making model
calls. Use --score-only SUITE_DIR to rebuild reports from saved predictions.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crack.config import DEFAULT_SETTINGS
from crack.corpus import evaluate_run
from crack.l4_anchoring import anchor_l4
from crack.l2_senses import senses_for
from crack.layers import run_l1
from crack.providers import resolve_backend
from crack.runner import _run_fingerprint, _git_sha, run
from crack.schema import AnalysisRecord, CandidateEntry, L2Result, L3Result, LayerTrace
from crack.validation import RESPONSE_CONTRACT_VERSION
from crack.semeval_benchmark import (
    ARCHIVE_URL, DEFAULT_ENCODER, DEFAULT_THRESHOLDS, PRIMARY_THRESHOLD,
    PROTOCOL_VERSION, REFERENCES_PATH, WORDNET31_URL, detection_report,
    download_if_missing, encoder_fingerprint, evaluate_senses, prepare_references, read_jsonl,
    sha256, verify_detection_inputs, write_json,
)


def _given_target_item(item: dict[str, Any], settings: Any) -> dict[str, Any]:
    # Deliberately receive an input-only row, never the corresponding gold row.
    if set(item) != {"id", "text", "given_target", "target_word_id"}:
        raise ValueError("Interpretation input contains unexpected fields")
    record = AnalysisRecord(item_id=item["id"], text=item["text"], target_ages=[], validation_version=RESPONSE_CONTRACT_VERSION)
    layer = "L1"
    start = time.monotonic()
    try:
        record = run_l1(record, settings)
        layer, start = "L2", time.monotonic()
        target = item["given_target"]
        record.l2_result = L2Result(senses=senses_for(target.casefold().replace(" ", "_"), term=target))
        record.trace.append(LayerTrace(
            layer="L2", status="OK", reason="Dictionary retrieval for supplied target; no gold sense selection",
            duration_ms=round((time.monotonic() - start) * 1000, 3),
        ))
        layer, start = "L3", time.monotonic()
        record.l3_result = L3Result(candidates=[CandidateEntry(term=target, score=0.0)], total_terms=1)
        record.trace.append(LayerTrace(layer="L3", status="OK", reason="Target supplied by interpretation task; candidate ranking not evaluated", duration_ms=0))
        layer, start = "L4", time.monotonic()
        record.l4_result = anchor_l4(record, settings, ambiguous_term=target)
        record.trace.append(LayerTrace(
            layer="L4", status="OK", reason=f"Supplied-target interpretation: {record.l4_result.anchoring_status.value}",
            duration_ms=round((time.monotonic() - start) * 1000, 3),
        ))
    except Exception as exc:
        record.trace.append(LayerTrace(
            layer=layer, status="ERROR", reason=f"{type(exc).__name__}: {exc}",
            duration_ms=round((time.monotonic() - start) * 1000, 3),
        ))
    return {
        **record.model_dump(mode="json"),
        "benchmark_input": {"given_target": item["given_target"], "target_word_id": item["target_word_id"]},
    }


def _run_given_target(input_path: Path, output: Path, settings: Any, concurrency: int) -> Path:
    items = list(read_jsonl(input_path, "id").values())
    output.mkdir(parents=True, exist_ok=False)
    records = output / "records.jsonl"
    write_json(output / "run_meta.json", {
        "timestamp": datetime.now(timezone.utc).isoformat(), "git_sha": _git_sha(),
        **_run_fingerprint(input_path, settings), "protocol_version": PROTOCOL_VERSION,
        "input_mode": "given_target", "layers": ["L1", "L2", "L3", "L4"],
        "item_count": len(items), "concurrency": concurrency,
        "input_policy": "Sentence and marked pun word only; gold keys/glosses are withheld from inference",
    })
    print(f"Starting {len(items)} supplied-target interpretation items with {concurrency} workers. Records: {records}", flush=True)
    with records.open("w", encoding="utf-8") as handle:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(_given_target_item, item, settings) for item in items]
            for completed, future in enumerate(concurrent.futures.as_completed(futures), 1):
                handle.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
                handle.flush()
                if completed % 10 == 0 or completed == len(items):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Interpretation: {completed}/{len(items)}", flush=True)
    return records


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.2f}%"


def _make_comparison(suite: Path, detection: dict[str, Any], senses: dict[str, dict[str, Any]]) -> None:
    refs = json.loads((suite / "benchmark_references.json").read_text())
    comparison = {
        "detection": {"metrics": detection},
        "interpretation": {"crack": senses, "reference_protocol": refs["pungraph_homographic"],
                           "direct_comparison_ready": False,
                           "missing_paper_settings": ["semantic encoder", "Table 1 threshold", "interpretation F1 formula"]},
    }
    write_json(suite / "comparison.json", comparison)
    lines = ["# CRACK SemEval benchmark results", "", "## Detection: CRACK run", "",
             f"Accuracy: **{_percent(detection['accuracy_all_items'])}**; precision: **{_percent(detection['precision'])}**; recall: **{_percent(detection['recall_full_gold'])}**; F1: **{_percent(detection['f1_full_gold'])}**.", "",
             f"Decision coverage: {_percent(detection['decision_coverage'])}; outcomes: `{detection['outcomes']}`.", ""]
    lines += ["Unresolved items remain in the accuracy and positive-recall denominators.", "",
              "## Interpretation: CRACK local evaluator", "",
              "All 1,298 official interpretation items stay in the denominator. The encoder and threshold were declared before inference; failed or unaccepted pairs count as incorrect.", "",
              "| CRACK input mode | Two-sense Acc | At-least-one PMA | One-to-one Acc | Accepted-pair coverage |", "|---|---:|---:|---:|---:|"]
    for mode, result in senses.items():
        primary = result["primary_metrics"]
        lines.append(f"| {mode} | {_percent(primary['acc'])} | {_percent(primary['pma'])} | {_percent(primary['one_to_one_accuracy'])} | {_percent(result['pair_coverage'])} |")
    lines += ["", f"Encoder: `{next(iter(senses.values()))['encoder']}`; cosine threshold: **{PRIMARY_THRESHOLD:.2f}**. See each `threshold_metrics` table for the full predeclared sensitivity sweep.", "",
              "The end-to-end view scores final CRACK pun predictions. The given-target experiment runs the existing L4 anchoring contract on the marked word and reports interpretation only; it does not contribute to detection scores.", ""]
    lines += ["", "Protocol reference: [PunGraph v1, Table 1 and Section 5.3](https://arxiv.org/abs/2609.16557v1). The paper supplies the pun word, but does not specify the sentence encoder, final table threshold or interpretation F1 formula. CRACK reports its declared local evaluator and leaves interpretation F1 uncomputed.", "",
              "SemEval does not contain human age-comprehension labels. This report evaluates detection and lexical interpretation only.", ""]
    (suite / "comparison.md").write_text("\n".join(lines), encoding="utf-8")


def _score_suite(suite: Path, encoder: Any) -> None:
    manifest = json.loads((suite / "suite_manifest.json").read_text())
    if encoder_fingerprint(encoder) != manifest["encoder_fingerprint"]:
        raise ValueError("Loaded encoder artifacts/packages differ from the frozen evaluator")
    for name, expected in manifest["frozen_artifacts"].items():
        if sha256(suite / name) != expected:
            raise ValueError(f"Frozen benchmark input/settings changed: {name}")
    detection_records = suite / manifest["detection_records"]
    evaluation = evaluate_run(detection_records, suite / "inputs" / "detection_gold.jsonl")
    write_json(detection_records.parent / "evaluation.json", evaluation)
    detection = detection_report(evaluation)
    senses = {}
    jobs = [("end_to_end", detection_records)]
    if manifest.get("given_target_records"):
        jobs.append(("given_target", suite / manifest["given_target_records"]))
    elif manifest["given_target_enabled"]:
        raise ValueError("The requested given-target experiment has not completed; retain detection outputs and complete that experiment before the combined report")
    for mode, records in jobs:
        out = suite / "interpretation_scores" / mode
        out.mkdir(parents=True, exist_ok=True)
        result = evaluate_senses(
            records, suite / "inputs" / "interpretation_gold.jsonl", input_mode=mode,
            encoder=encoder, model_name=manifest["encoder"], thresholds=tuple(manifest["thresholds"]),
            details_path=out / "per_item.jsonl",
        )
        write_json(out / "evaluation.json", result)
        senses[mode] = result
    _make_comparison(suite, detection, senses)
    print(f"\nDetection: accuracy {_percent(detection['accuracy_all_items'])}, F1 {_percent(detection['f1_full_gold'])}, coverage {_percent(detection['decision_coverage'])}")
    for mode, result in senses.items():
        m = result["primary_metrics"]
        print(f"Interpretation ({mode}, threshold 0.50): Acc {_percent(m['acc'])}, PMA {_percent(m['pma'])}, pair coverage {_percent(result['pair_coverage'])}")
    print(f"Full report: {suite / 'comparison.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind", type=Path, default=ROOT / "corpus/semeval_blind.jsonl")
    parser.add_argument("--eval", dest="gold", type=Path, default=ROOT / "corpus/semeval_gold.jsonl")
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--candidate-budget", type=int, default=8)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/semeval_benchmark")
    parser.add_argument("--resources", type=Path, default=ROOT / "data/semeval_benchmark")
    parser.add_argument("--encoder", default=DEFAULT_ENCODER)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/embedding_cache")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--skip-given-target", action="store_true", help="Run only detection and its end-to-end interpretation diagnostic")
    parser.add_argument("--score-only", type=Path, metavar="SUITE_DIR", help="Re-score saved outputs; no LLM calls")
    args = parser.parse_args()
    if args.concurrency < 1 or args.candidate_budget < 1:
        parser.error("Concurrency and candidate budget must be positive")
    if args.prepare_only and args.score_only:
        parser.error("Choose either --prepare-only or --score-only")
    if args.score_only:
        manifest = json.loads((args.score_only / "suite_manifest.json").read_text())
        model_name = manifest["encoder"]
    else:
        archive = args.resources / "semeval2017_task7.tar.xz"
        wordnet31 = args.resources / "wordnet31.zip"
        print("Preparing official SemEval / WordNet 3.1 references (no LLM calls).", flush=True)
        download_if_missing(ARCHIVE_URL, archive)
        download_if_missing(WORDNET31_URL, wordnet31)
        reference_manifest = prepare_references(archive, wordnet31, args.resources / "references")
        verify_detection_inputs(archive, args.blind, args.gold)
        print(f"Ready: 2,250 detection items; 1,298 interpretation items; {reference_manifest['multiple_key_items']} items with alternative gold senses.", flush=True)
        if args.prepare_only:
            return
        model_name = args.encoder
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise SystemExit("Install evaluation dependencies before inference: .venv/bin/python -m pip install -e '.[eval]'") from exc
    # Preload the evaluator so an unavailable encoder cannot waste a full run.
    print(f"Loading semantic encoder: {model_name}", flush=True)
    encoder = TextEmbedding(model_name=model_name, cache_dir=str(args.cache_dir))
    if args.score_only:
        _score_suite(args.score_only.resolve(), encoder)
        return
    backend = resolve_backend(args.backend)
    settings = DEFAULT_SETTINGS.model_copy(update={
        **{f"L{i}_BACKEND": backend for i in range(4, 9)},
        "L4_MAX_CANDIDATES": args.candidate_budget,
    })
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    suite = args.output.resolve() / timestamp
    inputs = suite / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.blind, inputs / "detection_blind.jsonl")
    shutil.copyfile(args.gold, inputs / "detection_gold.jsonl")
    for path in (args.resources / "references").iterdir():
        shutil.copyfile(path, inputs / path.name)
    shutil.copyfile(REFERENCES_PATH, suite / "benchmark_references.json")
    shutil.copytree(ROOT / "src/crack/prompts", suite / "prompts")
    initial = _run_fingerprint(inputs / "detection_blind.jsonl", settings)
    manifest = {
        "protocol_version": PROTOCOL_VERSION, "timestamp": timestamp, "git_sha": _git_sha(),
        "source_sha256": initial["source_sha256"], "config": initial["config"],
        "suite_script_sha256": sha256(Path(__file__)), "concurrency": args.concurrency,
        "encoder": model_name, "encoder_fingerprint": encoder_fingerprint(encoder),
        "thresholds": DEFAULT_THRESHOLDS, "primary_threshold": PRIMARY_THRESHOLD,
        "frozen_artifacts": {p.relative_to(suite).as_posix(): sha256(p) for p in [*inputs.iterdir(), *list((suite / "prompts").glob("*.md")), suite / "benchmark_references.json"]},
        "given_target_enabled": not args.skip_given_target,
        "detection_records": None, "given_target_records": None,
    }
    write_json(suite / "suite_manifest.json", manifest)
    print(f"Suite: {suite}\nInference jobs: 2,250 detection items" + (" + 1,298 separate given-target items" if not args.skip_given_target else ""), flush=True)

    def assert_source_unchanged() -> None:
        if _run_fingerprint(inputs / "detection_blind.jsonl", settings) != initial or sha256(Path(__file__)) != manifest["suite_script_sha256"]:
            raise RuntimeError("Source/config changed during inference. Retain these outputs and restart with a frozen revision.")

    assert_source_unchanged()
    detection_dir = run(inputs / "detection_blind.jsonl", settings=settings, output_root=suite / "detection", concurrency=args.concurrency)
    manifest["detection_records"] = (detection_dir / "records.jsonl").relative_to(suite).as_posix()
    write_json(suite / "suite_manifest.json", manifest)
    assert_source_unchanged()
    evaluation = evaluate_run(detection_dir / "records.jsonl", inputs / "detection_gold.jsonl")
    write_json(detection_dir / "evaluation.json", evaluation)
    detection = detection_report(evaluation)
    write_json(suite / "detection_summary.json", detection)
    print(f"Detection complete: accuracy {_percent(detection['accuracy_all_items'])}, F1 {_percent(detection['f1_full_gold'])}, coverage {_percent(detection['decision_coverage'])}", flush=True)
    if not args.skip_given_target:
        records = _run_given_target(inputs / "interpretation_input.jsonl", suite / "given_target", settings, args.concurrency)
        manifest["given_target_records"] = records.relative_to(suite).as_posix()
        write_json(suite / "suite_manifest.json", manifest)
        assert_source_unchanged()
    _score_suite(suite, encoder)


if __name__ == "__main__":
    main()
