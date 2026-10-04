#!/usr/bin/env python3
"""Run a fixed, stateless direct-LLM detection baseline against a saved CRACK run.

The model receives only the frozen prompt and input text. Gold is used only by
the scorer. Transport/format retries repeat the identical request; semantic
answers are accepted without CRACK's candidate selection or evidence filters.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crack.providers import resolve_api_key, resolve_base_url  # noqa: E402
import openai  # noqa: E402

POSITIVE = {"VALID_HOMOGRAPH_JOKE", "VALID_COMPOUND_SPLIT_JOKE"}
NEGATIVE = {"ONE_SENSE_ONLY", "NO_WORDPLAY", "FAILED_RESOLUTION"}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def comparator_records(suite: Path) -> Path:
    paths = list((suite / "detection").glob("*/records.jsonl"))
    if len(paths) != 1:
        raise ValueError("Suite must contain exactly one saved detection run")
    return paths[0]


def timing(values: list[float]) -> dict:
    values = sorted(values)
    return {"mean_seconds": statistics.mean(values),
            "median_seconds": statistics.median(values),
            "p95_seconds": values[min(len(values)-1, int(len(values)*.95))]}


def metrics(predictions: dict[str, str], gold: dict[str, bool]) -> dict:
    tp = fp = tn = fn = up = un = 0
    for item_id, positive in gold.items():
        label = predictions.get(item_id)
        if label not in {"PUN", "NON_PUN"}:
            up += int(positive)
            un += int(not positive)
        elif label == "PUN":
            tp += int(positive)
            fp += int(not positive)
        else:
            fn += int(positive)
            tn += int(not positive)
    n = len(gold)
    decided = tp + fp + tn + fn
    ratio = lambda a, b: a / b if b else 0.0
    return {"items": n, "correct": tp+tn,
            "accuracy_all_items": ratio(tp+tn, n),
            "accuracy_on_decided": ratio(tp+tn, decided),
            "precision": ratio(tp, tp+fp),
            "recall_full_gold": ratio(tp, tp+fn+up),
            "f1_full_gold": ratio(2*tp, 2*tp+fp+fn+up),
            "decision_coverage": ratio(decided, n),
            "tp": tp, "fp": fp, "tn": tn, "fn_decided": fn,
            "unresolved_by_gold_class": {"positive": up, "negative": un},
            "outcomes": dict(Counter(predictions.get(i, "MISSING") for i in gold))}


def infer(client, row: dict, prompt: str, config: dict) -> dict:
    started = time.monotonic()
    record = {"item_id": row["id"], "text": row["text"],
              "started_at": utc(), "label": "EXECUTION_FAILED", "attempts": []}
    message = prompt.rstrip() + "\n\nInput text (JSON string):\n" + json.dumps(row["text"], ensure_ascii=False)
    for number in range(1, config["max_attempts"] + 1):
        attempt = {"number": number, "started_at": utc()}
        wait = min(30.0, 2 ** (number-1)) + random.uniform(0, .5)
        request_started = time.monotonic()
        retryable = True
        try:
            response = client.chat.completions.create(
                model=config["model"], messages=[{"role": "user", "content": message}],
                max_completion_tokens=config["max_completion_tokens"],
                response_format={"type": "json_object"})
            # Retain the provider response, including usage and finish reason.
            attempt["response"] = response.model_dump(mode="json")
            attempt["request_id"] = getattr(response, "_request_id", None)
            choice = response.choices[0]
            if choice.finish_reason != "stop" or choice.message.refusal:
                raise ValueError("incomplete_or_refused_response")
            data = json.loads(choice.message.content or "")
            if not isinstance(data, dict) or set(data) != {"label"} or data["label"] not in {"PUN", "NON_PUN"}:
                raise ValueError("invalid_label_schema")
            record["label"] = data["label"]
        except openai.APIError as exc:
            status = getattr(exc, "status_code", None)
            attempt["error"] = {"type": type(exc).__name__, "status_code": status,
                                "code": getattr(exc, "code", None),
                                "request_id": getattr(exc, "request_id", None)}
            retryable = status is None or status in {408, 409, 429} or status >= 500
            if not retryable:
                record["fatal_configuration_error"] = True
            headers = getattr(getattr(exc, "response", None), "headers", {})
            try:
                wait = max(wait, min(60.0, float(headers.get("retry-after", 0))))
            except (TypeError, ValueError):
                pass
        except (ValueError, TypeError, IndexError, AttributeError) as exc:
            attempt["error"] = {"type": type(exc).__name__, "code": "invalid_response"}
        attempt["duration_seconds"] = time.monotonic() - request_started
        record["attempts"].append(attempt)
        if record["label"] != "EXECUTION_FAILED" or not retryable:
            break
        if number < config["max_attempts"]:
            attempt["retry_wait_seconds"] = wait
            time.sleep(wait)
    record["finished_at"] = utc()
    record["duration_seconds"] = time.monotonic() - started
    return record


def score(run: Path, suite: Path) -> dict:
    blind = read_rows(run / "blind.jsonl")
    gold_rows = read_rows(run / "gold.jsonl")
    if any(r["gold_label"] not in POSITIVE | NEGATIVE for r in gold_rows):
        raise ValueError("Unsupported gold label")
    gold = {r["id"]: r["gold_label"] in POSITIVE for r in gold_rows}
    records = read_rows(run / "records.jsonl")
    if len(records) != len(gold) or len({r["item_id"] for r in records}) != len(gold):
        raise ValueError("Scoring requires exactly one record per gold item")
    baseline = {r["item_id"]: r["label"] for r in records}
    crack_path = comparator_records(suite)
    crack_records = read_rows(crack_path)
    crack = {r["item_id"]: r["final"]["detection_status"] for r in crack_records}
    texts = {r["id"]: r["text"] for r in blind}
    if set(gold) != set(baseline) or set(gold) != set(crack) or any(r["text"] != texts[r["item_id"]] for r in crack_records):
        raise ValueError("Input/record alignment mismatch")
    base_metrics, crack_metrics = metrics(baseline, gold), metrics(crack, gold)
    saved = json.loads((suite / "detection_summary.json").read_text())
    for key in ("accuracy_all_items", "precision", "recall_full_gold", "f1_full_gold", "decision_coverage", "tp", "fp", "tn", "fn_decided"):
        if abs(crack_metrics[key] - saved[key]) > 1e-10:
            raise ValueError(f"Saved CRACK metric mismatch: {key}")
    paired = Counter()
    disagreements = []
    for item_id, positive in gold.items():
        expected = "PUN" if positive else "NON_PUN"
        b, c = baseline[item_id], crack[item_id]
        b_ok, c_ok = b == expected, c == expected
        paired["both_correct" if b_ok and c_ok else "baseline_only_correct" if b_ok else "crack_only_correct" if c_ok else "neither_correct"] += 1
        if b != c:
            disagreements.append({"item_id": item_id, "text": texts[item_id], "gold": expected,
                                  "baseline": b, "crack": c, "baseline_correct": b_ok, "crack_correct": c_ok})
    with (run / "disagreements.jsonl").open("w") as stream:
        for row in disagreements:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    totals = Counter()
    attempts = 0
    errors = Counter()
    for record in records:
        for attempt in record["attempts"]:
            attempts += 1
            usage = (attempt.get("response") or {}).get("usage") or {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                totals[key] += usage.get(key, 0) or 0
            totals["reasoning_tokens"] += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
            if attempt.get("error"):
                error = attempt["error"]
                errors[str(error.get("status_code") or error.get("code") or error["type"])] += 1
    detection_layers = {"L0-pre", "L1", "L2", "L3", "L4", "L5", "L6", "L0-post"}
    crack_times = [sum(t.get("duration_ms", 0) for t in r["trace"] if t["layer"] in detection_layers)/1000 for r in crack_records]
    manifest = json.loads((run / "manifest.json").read_text())
    if sha(crack_path) != manifest["comparator_records_sha256"]:
        raise ValueError("Saved CRACK records changed after the experiment was frozen")
    result = {"baseline": base_metrics, "crack": crack_metrics,
              "always_pun": metrics({i: "PUN" for i in gold}, gold),
              "paired_correctness_all_items": dict(paired), "disagreement_count": len(disagreements),
              "baseline_timing": timing([r["duration_seconds"] for r in records]),
              "crack_detection_trace_timing": timing(crack_times),
              "baseline_usage": dict(totals), "api_attempts": attempts, "attempt_errors": dict(errors),
              "records_sha256": sha(run / "records.jsonl"),
              "metric_policy": "All 2250 items remain in accuracy and recall denominators. Unresolved positives count as misses for full-gold F1; unresolved negatives remain separate.",
              "timing_policy": "Baseline item duration includes retries; CRACK item duration sums saved detection layer traces (excludes L7/L8). Calls were made at different times; CRACK token usage and precise batch wall time were not recorded."}
    write_json(run / "evaluation.json", result)
    lines = ["# Direct LLM versus CRACK: homographic pun detection", "",
             f"Same frozen SemEval-2017 Task 7 inputs and binary gold labels; baseline requested model `{manifest['config']['model']}`. One independent request per baseline text, a fixed zero-shot prompt, no gold examples or lexical candidates. CRACK is the saved comparator run. This is a new baseline, not a reproduction of the ICIC 2026 paper's 3-shot experiment.", "",
             "| System | Accuracy (all) | Precision | Recall (all gold puns) | F1 (full gold) | Decision coverage |", "|---|---:|---:|---:|---:|---:|"]
    for name, value in (("Direct LLM", base_metrics), ("CRACK", crack_metrics), ("Always PUN", result["always_pun"])):
        lines.append("| " + name + " | " + " | ".join(f"{100*value[k]:.2f}%" for k in ("accuracy_all_items", "precision", "recall_full_gold", "f1_full_gold", "decision_coverage")) + " |")
    lines += ["", "## Counts", "", "| System | TP | FP | TN | FN (decided) | Unresolved positive / negative |", "|---|---:|---:|---:|---:|---:|"]
    for name, value in (("Direct LLM", base_metrics), ("CRACK", crack_metrics)):
        unresolved = value["unresolved_by_gold_class"]
        lines.append(f"| {name} | {value['tp']} | {value['fp']} | {value['tn']} | {value['fn_decided']} | {unresolved['positive']} / {unresolved['negative']} |")
    lines += ["", "## Paired outcomes", "", "```json", json.dumps(dict(paired), indent=2), "```", "",
              "## Runtime and API usage", "",
              f"Baseline batch wall time: {manifest.get('active_wall_seconds', 0):.1f} seconds across {manifest['config']['concurrency']} workers. API attempts: {attempts}; successful-response total tokens: {totals['total_tokens']:,}. Attempt errors: `{dict(errors)}`.", "",
              "| System | Mean item seconds | Median | P95 |", "|---|---:|---:|---:|"]
    for name, key in (("Direct LLM", "baseline_timing"), ("CRACK detection traces", "crack_detection_trace_timing")):
        lines.append(f"| {name} | " + " | ".join(f"{result[key][k]:.2f}" for k in ("mean_seconds", "median_seconds", "p95_seconds")) + " |")
    lines += ["", result["timing_policy"], "", "## Reproducibility", "",
              "`prompt.md`, `manifest.json`, `blind.jsonl`, `gold.jsonl`, and `runner.py` freeze the instructions, inputs and runner. `records.jsonl` includes raw responses, response model IDs, finish reasons, token usage, retries, request IDs and per-item timing. `disagreements.jsonl` aligns differing predictions by item ID. API credentials are not saved.", "",
              "The direct baseline is forced binary; 100% output coverage does not measure calibrated uncertainty. No baseline prompt was adjusted using these results. A single run compares these configurations; it does not isolate which CRACK layer causes a difference or establish a newer model's capability.", ""]
    (run / "comparison.md").write_text("\n".join(lines))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-completion-tokens", type=int, default=4096)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--prompt", type=Path, default=ROOT / "experiments/direct_detection/prompt.md")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/direct_detection_baseline")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()
    suite = args.suite.resolve()
    if args.concurrency < 1 or args.max_attempts < 1:
        parser.error("concurrency and max-attempts must be positive")
    if args.score_only:
        if not args.resume:
            parser.error("--score-only requires --resume")
        run = args.resume.resolve()
        manifest = json.loads((run / "manifest.json").read_text())
        for filename, checksum in manifest["frozen_sha256"].items():
            if sha(run / filename) != checksum:
                raise ValueError(f"Frozen artifact changed: {filename}")
        result = score(run, suite)
        print(json.dumps(result, indent=2))
        return
    key, key_name = resolve_api_key("openai")
    endpoint = resolve_base_url("openai") or "https://api.openai.com/v1"
    parts = urlsplit(endpoint)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Endpoint must not contain embedded credentials or query parameters")
    config = {"model": args.model, "concurrency": args.concurrency,
              "max_completion_tokens": args.max_completion_tokens, "max_attempts": args.max_attempts,
              "timeout_seconds": 90, "sdk_max_retries": 0, "temperature": "omitted (provider default)",
              "response_format": {"type": "json_object"}, "message_role": "user",
              "endpoint": endpoint, "input_wrapper": "Input text (JSON string):"}
    if args.resume:
        run = args.resume.resolve()
        manifest = json.loads((run / "manifest.json").read_text())
        if config != manifest["config"]:
            raise ValueError("Resume request config differs from the frozen run")
        for filename, checksum in manifest["frozen_sha256"].items():
            if sha(run / filename) != checksum:
                raise ValueError(f"Frozen artifact changed: {filename}")
        if sha(Path(__file__)) != manifest["frozen_sha256"]["runner.py"]:
            raise ValueError("Resume inference with the same runner source as the frozen run")
    else:
        if args.score_only:
            parser.error("--score-only requires --resume")
        run = args.output.resolve() / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        run.mkdir(parents=True, exist_ok=False)
        for destination, source in (("blind.jsonl", suite / "inputs/detection_blind.jsonl"),
                                    ("gold.jsonl", suite / "inputs/detection_gold.jsonl"),
                                    ("prompt.md", args.prompt), ("runner.py", Path(__file__))):
            (run / destination).write_bytes(source.read_bytes())
        manifest = {"started_at": utc(), "status": "running", "config": config,
                    "sdk_version": openai.__version__, "python_version": sys.version,
                    "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "suite_path": str(suite), "comparator_records_sha256": sha(comparator_records(suite)),
                    "frozen_sha256": {name: sha(run / name) for name in ("blind.jsonl", "gold.jsonl", "prompt.md", "runner.py")},
                    "active_wall_seconds": 0,
                    "design": "Fixed zero-shot prompt before inference, one independent request per text, no target/gold/age/lexical candidates; identical-request bounded retries; errors remain unresolved."}
        write_json(run / "manifest.json", manifest)
    if not key:
        raise RuntimeError("Missing OpenAI API key")
    rows = read_rows(run / "blind.jsonl")
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate input IDs")
    records_path = run / "records.jsonl"
    existing = read_rows(records_path) if records_path.exists() else []
    completed = {r["item_id"] for r in existing}
    if len(completed) != len(existing) or not completed <= {r["id"] for r in rows}:
        raise ValueError("Duplicate or foreign records")
    pending = [r for r in rows if r["id"] not in completed]
    prompt = (run / "prompt.md").read_text()
    client = openai.OpenAI(api_key=key, base_url=endpoint, timeout=90, max_retries=0)
    started = time.monotonic()
    print(f"Starting {len(pending)}/{len(rows)} items with {args.concurrency} workers. Run: {run}", flush=True)
    count, failures = len(existing), sum(r["label"] == "EXECUTION_FAILED" for r in existing)
    try:
        with records_path.open("a") as stream:
            def save(record):
                nonlocal count, failures
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                count += 1
                failures += int(record["label"] == "EXECUTION_FAILED")
                if count == 1 or count % 100 == 0 or count == len(rows):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {count}/{len(rows)}; unresolved={failures}; elapsed={time.monotonic()-started:.1f}s", flush=True)
            # First real input checks configuration; its prediction counts once.
            if pending and not existing:
                record = infer(client, pending.pop(0), prompt, config)
                save(record)
                if record.get("fatal_configuration_error"):
                    raise RuntimeError("API configuration rejected; see the first record's error code")
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [pool.submit(infer, client, row, prompt, config) for row in pending]
                for future in as_completed(futures):
                    record = future.result()
                    save(record)
                    if record.get("fatal_configuration_error"):
                        for queued in futures:
                            queued.cancel()
                        raise RuntimeError("API configuration rejected during run; completed records retained")
        manifest["status"] = "complete"
    finally:
        if manifest["status"] != "complete":
            manifest["status"] = "interrupted"
        manifest["active_wall_seconds"] += time.monotonic() - started
        manifest["last_updated_at"] = utc()
        manifest["completed_items"] = count
        write_json(run / "manifest.json", manifest)
        client.close()
    result = score(run, suite)
    b = result["baseline"]
    print(f"Baseline: accuracy {b['accuracy_all_items']:.2%}, F1 {b['f1_full_gold']:.2%}, coverage {b['decision_coverage']:.2%}")
    print(f"Report: {run / 'comparison.md'}")


if __name__ == "__main__":
    main()
