#!/usr/bin/env python3
"""Compare search policies on fixed saved replies, calling only new candidates."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time
import sys

ROOT = Path.cwd()
SUPPORT = Path(__file__).with_name("comparison_support.py")
if not SUPPORT.exists():
    SUPPORT = Path(__file__).with_name("compare_full_assignment.py")
spec = importlib.util.spec_from_file_location("comparison_support", SUPPORT)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
REQUEST_FIELDS = ("model", "messages", "max_completion_tokens", "temperature", "response_format")


def replay_observer(source_records, allow_live):
    def install(local):
        from openai.resources.chat.completions import Completions
        from openai.types.chat import ChatCompletion
        original = Completions.create

        def observed(self, *args, **kwargs):
            started = time.monotonic()
            item_id = local.item_id
            original_events = source_records[item_id]["api_events"]
            if not hasattr(local, "prefix_positions"):
                local.prefix_positions = {}
            position = local.prefix_positions.get(item_id, 0)
            request = {k: kwargs[k] for k in REQUEST_FIELDS if k in kwargs}
            event = {"started_at": support.utc(), "stage": local.stage,
                     "request": request, "origin": "new", "source_item_id": item_id}
            try:
                if position < len(original_events):
                    old = original_events[position]
                    if request != old["request"] or local.stage != old["stage"]:
                        raise ValueError(f"Saved request prefix mismatch at {item_id}, event {position}; refusing new inference")
                    if old.get("error") or not old.get("response"):
                        raise ValueError("Source prefix contains an unavailable response")
                    response = ChatCompletion.model_validate(old["response"])
                    event.update(origin="cached", source_event_index=position,
                                 source_request_seconds=old["duration_seconds"])
                    local.prefix_positions[item_id] = position + 1
                    event["request_id"] = old.get("request_id")
                elif allow_live:
                    response = original(self, *args, **kwargs)
                    event["request_id"] = getattr(response, "_request_id", None)
                else:
                    raise ValueError(f"Control requested new inference for {item_id}")
                event["response"] = response.model_dump(mode="json")
                return response
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "status_code": getattr(exc, "status_code", None),
                                  "code": getattr(exc, "code", None)}
                raise
            finally:
                event["duration_seconds"] = time.monotonic() - started
                local.events.append(event)

        Completions.create = observed
    return install


def prepare(args):
    old = support.check_frozen(args.source_run)
    if old["model"] != args.model:
        raise ValueError("Model must match the saved prefix")
    run = support.prepare(args.output, args.model, args.concurrency)
    manifest = support.check_frozen(run)
    original_source = old["production_fingerprint"]["source_sha256"]
    new_source = manifest["production_fingerprint"]["source_sha256"]
    allowed = {"candidate_search.py", "config.py", "decisions.py", "l4_anchoring.py", "layers.py", "runner.py", "schema.py"}
    differences = [k for k in sorted(set(original_source) | set(new_source))
                   if original_source.get(k) != new_source.get(k)]
    if set(differences) - allowed:
        raise ValueError(f"Changes outside search orchestration: {set(differences) - allowed}")
    for name in ("blind.jsonl", "gold.jsonl"):
        if support.sha(run / name) != support.sha(args.source_run / name):
            raise ValueError("Corpus differs from prefix experiment")
    config = manifest["crack_config"]
    if {k: v for k, v in config.items() if k != "CONTINUE_AFTER_CANDIDATE_REJECTION"} != old["crack_config"]:
        raise ValueError("Non-search settings differ from the source experiment")
    for path, checksum in old["workspace_sha256"].items():
        if path.startswith("workspace/data/") and manifest["workspace_sha256"].get(path) != checksum:
            raise ValueError(f"Resource mismatch: {path}")
    for source, dest in ((args.source_run / "crack/records.jsonl", "source_records.jsonl"),
                         (args.source_run / "shared_inputs.jsonl", "shared_inputs.jsonl"),
                         (Path(__file__), "runner.py"), (SUPPORT, "comparison_support.py"),
                         (ROOT / "experiments/full_assignment/candidate_continuation_protocol.md", "protocol.md")):
        shutil.copyfile(source, run / dest)
    manifest.update(experiment="candidate-continuation-fixed-prefix-v1",
                    source_run=str(args.source_run), source_manifest_sha256=support.sha(args.source_run / "manifest.json"),
                    changed_source_files=differences, arm_order=["baseline", "continuation"],
                    arm_configs={a: {**config, "CONTINUE_AFTER_CANDIDATE_REJECTION": a == "continuation"}
                                 for a in ("baseline", "continuation")},
                    limitations=["Fixed saved prefix, not fresh full inference", "Inspected 60-item corpus", "Human review pending"])
    for name in ("runner.py", "comparison_support.py", "protocol.md", "source_records.jsonl", "shared_inputs.jsonl"):
        manifest["frozen_sha256"][name] = support.sha(run / name)
    support.write(run / "manifest.json", manifest)
    return run


def worker(run, arm):
    support.check_frozen(run)
    source = {r["item_id"]: r for r in support.rows(run / "source_records.jsonl")}
    support.observe_sdk = replay_observer(source, allow_live=arm == "continuation")
    support.worker(run, arm)


def score(run):
    manifest = support.check_frozen(run)
    gold = {r["id"]: r for r in support.rows(run / "gold.jsonl")}
    source = {r["item_id"]: r for r in support.rows(run / "source_records.jsonl")}
    raw = {a: support.rows(run / a / "records.jsonl") for a in manifest["arm_order"]}
    predictions, result = {}, {"run_path": str(run), "model": manifest["model"], "arms": {}}
    for arm, records in raw.items():
        if len(records) != len(gold) or len({r["item_id"] for r in records}) != len(records) or {r["item_id"] for r in records} != set(gold):
            raise ValueError("One record per frozen input is required")
        for row in records:
            original = source[row["item_id"]]
            if (row["text"], row["target_ages"]) != (original["text"], original["target_ages"]):
                raise ValueError("Input mismatch")
            cached = [e for e in row["api_events"] if e["origin"] == "cached"]
            if len(cached) != len(original["api_events"]):
                raise ValueError(f"Saved prefix was not completely reproduced: {arm} {row['item_id']}")
            if arm == "baseline" and any(e["origin"] != "cached" for e in row["api_events"]):
                raise ValueError("Control made additional calls")
            if arm == "baseline" and any(row["analysis"][k] != original["analysis"][k] for k in ("decision", "target", "meanings", "per_age")):
                raise ValueError(f"Control output differs from source: {row['item_id']}")
        p = {r["item_id"]: r["analysis"] for r in records}
        predictions[arm] = p
        metrics = support.detection(p, gold)
        pairs = [(i, "D" + i[1:]) for i in gold if i.startswith("J") and "D" + i[1:] in gold]
        metrics["pair_success_count"] = sum(p[j]["decision"] == "PUN" and p[d]["decision"] == "NON_PUN" for j, d in pairs)
        metrics["pair_count"] = len(pairs)
        positives = {i for i in gold if gold[i]["gold_label"] in support.POSITIVE}
        metrics["target_matches"] = sum(p[i]["decision"] == "PUN" and support.normalized_target(p[i]["target"]) == support.normalized_target(gold[i]["ambiguous_term"]) for i in positives)
        metrics["target_denominator"] = len(positives)
        metrics["age_gold_positive_labels"] = support.age_metrics(p, gold, positives)
        metrics["common_contract_failures"] = sum(not r["common_contract_passed"] for r in records)
        metrics["records_sha256"] = support.sha(run / arm / "records.jsonl")
        metrics["api_usage"] = {origin: support.api_totals([
            {"api_events": [e for e in r["api_events"] if e["origin"] == origin]} for r in records])
            for origin in ("cached", "new")}
        metrics["replay_timing"] = json.loads((run / arm / "timing.json").read_text())
        metrics["new_request_seconds_sum"] = sum(e["duration_seconds"] for r in records for e in r["api_events"] if e["origin"] == "new")
        result["arms"][arm] = metrics
    changes, paired = [], Counter()
    for item_id, g in gold.items():
        a, b = predictions["baseline"][item_id], predictions["continuation"][item_id]
        expected = "PUN" if g["gold_label"] in support.POSITIVE else "NON_PUN"
        ca, cb = a["decision"] == expected, b["decision"] == expected
        paired["both_correct" if ca and cb else "baseline_only_correct" if ca else "continuation_only_correct" if cb else "neither_correct"] += 1
        if a != b:
            changes.append({"item_id": item_id, "gold": g, "baseline": a, "continuation": b})
    result.update(paired_correctness=dict(paired), changed_output_count=len(changes),
                  timing_policy="Cached inference is replayed. Replay wall time and additional request seconds are not fresh end-to-end latency.",
                  human_review="Pending; full anonymous materials provided")
    support.jsonl(run / "changes.jsonl", changes)
    support.write(run / "evaluation.json", result)
    support.packets(run)
    lines = ["# Candidate continuation: fixed-prefix comparison", "",
             "Same 60 texts/ages, model, prompts, thresholds, gold and resources. Both policies reuse request-matched SDK replies; only continuation requests additional candidates.", "",
             "| Policy | Correct | Precision | Recall | F1 | Coverage | Pair success | Targets | New calls |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a, v in result["arms"].items():
        lines.append(f"| {a} | {v['correct']}/60 | {v['precision']:.2%} | {v['recall_full_gold']:.2%} | {v['f1_full_gold']:.2%} | {v['coverage']:.2%} | {v['pair_success_count']}/{v['pair_count']} | {v['target_matches']}/{v['target_denominator']} | {v['api_usage']['new'].get('observed_calls',0)} |")
    lines += ["", "Paired correctness: " + json.dumps(dict(paired)), "", result["timing_policy"], "",
              "This measures a search-policy intervention on fixed saved prefixes and an inspected corpus. It does not establish performance on unseen texts. Age algorithms and semantic gates remain unchanged. Human review is pending.", "",
              "All changed outputs are in `changes.jsonl`; anonymous materials are in `blind_review/`. Source prefixes, cached/new responses and hashes are preserved.", ""]
    (run / "comparison.md").write_text("\n".join(lines))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, default=ROOT / "runs/full_assignment_comparison/20261003T021452.992281Z/corrected_validation")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/candidate_continuation_comparison")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--worker", choices=["baseline", "continuation", "score"])
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if not args.run:
            parser.error("--worker requires --run")
        if args.worker == "score":
            result = score(args.run.resolve())
            print(json.dumps({a: {k: v[k] for k in ("correct", "f1_full_gold", "pair_success_count", "outcomes")} for a, v in result["arms"].items()}, indent=2))
        else:
            worker(args.run.resolve(), args.worker)
        return
    if args.concurrency < 1:
        parser.error("Concurrency must be positive")
    args.source_run = args.source_run.resolve()
    run = prepare(args)
    print(f"Frozen comparison: {run}", flush=True)
    if args.prepare_only:
        return
    for phase in ("baseline", "continuation", "score"):
        subprocess.run([sys.executable, str(run / "runner.py"), "--run", str(run), "--worker", phase], cwd=ROOT, check=True)
    manifest = support.check_frozen(run)
    manifest.update(status="complete", finished_at=support.utc())
    support.write(run / "manifest.json", manifest)
    print(f"Report: {run / 'comparison.md'}", flush=True)


if __name__ == "__main__":
    main()
