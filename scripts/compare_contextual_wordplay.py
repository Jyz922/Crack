#!/usr/bin/env python3
"""Freeze and compare one L6 contextual-ablation clarification.

New stage cases use fresh calls in both arms. The course-corpus intervention
reuses only identical requests from the previous completed search comparison.
Inference workers never load annotation/gold files.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path.cwd()
SUPPORT = Path(__file__).with_name("comparison_support.py")
if not SUPPORT.exists():
    SUPPORT = Path(__file__).with_name("compare_full_assignment.py")
spec = importlib.util.spec_from_file_location("comparison_support", SUPPORT)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
REQUEST_FIELDS = ("model", "messages", "max_completion_tokens", "temperature", "response_format")
ARMS = ("baseline", "contextual")


def prepare(args):
    old = support.check_frozen(args.source_run)
    run = support.prepare(args.output, args.model, args.concurrency)
    manifest = support.check_frozen(run)
    if manifest["production_fingerprint"]["source_sha256"] != old["production_fingerprint"]["source_sha256"]:
        raise ValueError("Production source differs from completed candidate-search run")
    if manifest["crack_config"] != old["crack_config"] or args.model != old["model"]:
        raise ValueError("Model/settings differ from saved replies")
    for name in ("blind.jsonl", "gold.jsonl"):
        if support.sha(run / name) != support.sha(args.source_run / name):
            raise ValueError("Course corpus changed")
    for path, checksum in old["workspace_sha256"].items():
        if path.startswith("workspace/data/") and manifest["workspace_sha256"].get(path) != checksum:
            raise ValueError("Frozen lexical/AoA resource differs")
    experiment = ROOT / "experiments/contextual_wordplay"
    dataset = ROOT / "corpus/prompt_development/contextual_v1"
    dataset_manifest = json.loads((dataset / "manifest.json").read_text())
    for name, checksum in dataset_manifest["sha256"].items():
        if support.sha(dataset / name) != checksum:
            raise ValueError("Development/confirmation cases changed")
    if support.sha(experiment / "l6_baseline.md") != support.sha(run / "workspace/src/crack/prompts/l6_distinctness.md"):
        raise ValueError("Baseline template mismatch")
    copies = [(Path(__file__), "runner.py"), (SUPPORT, "comparison_support.py"),
              (Path(__file__).with_name("summarize_contextual_wordplay.py"), "summarize.py"),
              (args.source_run / "continuation/records.jsonl", "source_records.jsonl"),
              (args.source_run / "shared_inputs.jsonl", "shared_inputs.jsonl"),
              (dataset / "manifest.json", "stage_manifest.json")]
    copies += [(experiment / name, name) for name in ("l6_baseline.md", "l6_contextual_v1.md", "protocol.md")]
    copies += [(dataset / name, name) for name in dataset_manifest["sha256"]]
    for source, name in copies:
        shutil.copyfile(source, run / name)
        manifest["frozen_sha256"][name] = support.sha(run / name)
    manifest.update(experiment="contextual-ablation-v1", source_run=str(args.source_run),
                    source_manifest_sha256=support.sha(args.source_run / "manifest.json"),
                    arm_order=list(ARMS), arm_configs={a: manifest["crack_config"] for a in ARMS},
                    prompt_by_arm={"baseline": "l6_baseline.md", "contextual": "l6_contextual_v1.md"},
                    limitations=["One frozen prompt draft; no outcome-guided revisions",
                                 "Synthetic stage labels are provisional; human review pending",
                                 "Inspected course corpus; not an unseen benchmark",
                                 "Request-matched branch replay; not fresh end-to-end latency"])
    support.write(run / "manifest.json", manifest)
    return run


def use_prompt(run, arm):
    support.activate(run)
    import crack.l6_distinctness as l6
    manifest = support.check_frozen(run)
    l6._PROMPT_PATH = run / manifest["prompt_by_arm"][arm]
    return l6


def stage_worker(run, arm):
    manifest = support.check_frozen(run)
    l6 = use_prompt(run, arm)
    from crack.config import Settings
    from crack.enums import Genre
    from crack.validation import validate_l6_response
    settings = Settings(**manifest["crack_config"])
    local = threading.local()
    support.observe_sdk(local)
    # These files contain hypotheses/input only; expectations are loaded at score time.
    inputs = [r for split in ("development", "confirmation")
              for r in support.rows(run / f"{split}_inputs.jsonl")]
    destination = run / "stage" / arm
    destination.mkdir(parents=True, exist_ok=False)

    def process(row):
        started = time.monotonic()
        local.events, local.stage = [], "L6"
        output = {"item_id": row["id"], "input": row}
        try:
            prompt = l6._render_l6_prompt(row["text"], Genre(row["genre"]), row["target_term"],
                                         row["sense_a"], row["anchor_a"], row["sense_b"], row["anchor_b"])
            response = l6._complete_l6(prompt, settings, None)
            output["result"] = validate_l6_response(response.parsed)
        except Exception as exc:
            output["result"] = None
            output["error"] = f"{type(exc).__name__}: {exc}"
        output.update(api_events=local.events, duration_seconds=time.monotonic() - started)
        return output

    print(f"Stage {arm}: {len(inputs)} independent cases", flush=True)
    with (destination / "records.jsonl").open("w") as stream, ThreadPoolExecutor(max_workers=manifest["concurrency"]) as pool:
        for count, future in enumerate(as_completed([pool.submit(process, r) for r in inputs]), 1):
            stream.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
            stream.flush()
            if count % 6 == 0:
                print(f"Stage {arm}: {count}/{len(inputs)}", flush=True)
    support.check_frozen(run)


def matched_observer(source, allow_live):
    def install(local):
        from openai.resources.chat.completions import Completions
        from openai.types.chat import ChatCompletion
        original = Completions.create

        def observed(self, *args, **kwargs):
            started = time.monotonic()
            item_id = local.item_id
            request = {k: kwargs[k] for k in REQUEST_FIELDS if k in kwargs}
            event = {"started_at": support.utc(), "stage": local.stage, "request": request, "origin": "new"}
            if not hasattr(local, "used_saved_events"):
                local.used_saved_events = {}
            used = local.used_saved_events.setdefault(item_id, set())
            match = next((i for i, e in enumerate(source[item_id]["api_events"])
                          if i not in used and not e.get("error") and e.get("response")
                          and e["request"] == request and e["stage"] == local.stage), None)
            try:
                if match is not None:
                    old = source[item_id]["api_events"][match]
                    response = ChatCompletion.model_validate(old["response"])
                    used.add(match)
                    event.update(origin="cached", source_event_index=match, request_id=old.get("request_id"))
                elif allow_live:
                    response = original(self, *args, **kwargs)
                    event["request_id"] = getattr(response, "_request_id", None)
                else:
                    raise ValueError(f"Control requested uncached inference: {item_id} {local.stage}")
                event["response"] = response.model_dump(mode="json")
                return response
            except Exception as exc:
                event["error"] = {"type": type(exc).__name__, "status_code": getattr(exc, "status_code", None)}
                raise
            finally:
                event["duration_seconds"] = time.monotonic() - started
                local.events.append(event)
        Completions.create = observed
    return install


def corpus_worker(run, arm):
    use_prompt(run, arm)
    source = {r["item_id"]: r for r in support.rows(run / "source_records.jsonl")}
    support.observe_sdk = matched_observer(source, allow_live=arm == "contextual")
    support.worker(run, arm)


def supported(result):
    return bool(result and result["distinctness_status"] == "SENSES_DISTINCT"
                and result["ambiguity_ablation"] == "SUPPORTED")


def verify_control(run):
    support.check_frozen(run)
    source = {r["item_id"]: r for r in support.rows(run / "source_records.jsonl")}
    records = support.rows(run / "baseline/records.jsonl")
    if len(records) != len(source) or len({r["item_id"] for r in records}) != len(source):
        raise ValueError("Missing or duplicate control records")
    for row in records:
        old = source[row["item_id"]]
        if (row["text"], row["target_ages"]) != (old["text"], old["target_ages"]):
            raise ValueError("Control input changed")
        if any(row["analysis"][k] != old["analysis"][k] for k in ("decision", "target", "meanings", "per_age")):
            raise ValueError(f"Control differs from saved source: {row['item_id']}")
        if len(row["api_events"]) != len(old["api_events"]):
            raise ValueError("Control call count differs")
        for index, event in enumerate(row["api_events"]):
            if event["origin"] != "cached" or event["source_event_index"] != index:
                raise ValueError("Control did not replay source calls in order")
            if any(event[k] != old["api_events"][index][k] for k in ("request", "stage", "response")):
                raise ValueError("Control request/response mismatch")
    print(f"Control verified: {len(records)} exact outputs; zero new API calls", flush=True)


def stage_score(run):
    expectations = {r["id"]: r for split in ("development", "confirmation")
                    for r in support.rows(run / f"{split}_annotations.jsonl")}
    result = {}
    for arm in ARMS:
        records = support.rows(run / "stage" / arm / "records.jsonl")
        if len(records) != len(expectations) or {r["item_id"] for r in records} != set(expectations):
            raise ValueError("Missing/duplicate stage records")
        metrics = {}
        for split in ("development", "confirmation"):
            counts = Counter()
            for row in records:
                gold = expectations[row["item_id"]]
                if gold["split"] != split:
                    continue
                expected = gold["expected_supported_wordplay"]
                if not row["result"]:
                    counts["execution_failed"] += 1
                elif supported(row["result"]):
                    counts["tp" if expected else "fp"] += 1
                else:
                    counts["fn" if expected else "tn"] += 1
            metrics[split] = {"counts": dict(counts), "correct": counts["tp"] + counts["tn"], "total": 12}
        result[arm] = {**metrics, "api_usage": support.api_totals(records),
                       "records_sha256": support.sha(run / "stage" / arm / "records.jsonl")}
    support.write(run / "stage_evaluation.json", result)
    return result


def corpus_score(run):
    manifest = support.check_frozen(run)
    source = {r["item_id"]: r for r in support.rows(run / "source_records.jsonl")}
    gold = {r["id"]: r for r in support.rows(run / "gold.jsonl")}
    positives = {i for i, g in gold.items() if g["gold_label"] in support.POSITIVE}
    predictions, result = {}, {"arms": {}, "run_path": str(run), "model": manifest["model"]}
    for arm in ARMS:
        records = support.rows(run / arm / "records.jsonl")
        if len(records) != len(gold) or len({r["item_id"] for r in records}) != len(gold) or {r["item_id"] for r in records} != set(gold):
            raise ValueError("Missing/duplicate course-corpus records")
        for row in records:
            old = source[row["item_id"]]
            if (row["text"], row["target_ages"]) != (old["text"], old["target_ages"]):
                raise ValueError("Changed course input")
            cached = [e for e in row["api_events"] if e["origin"] == "cached"]
            indexes = [e["source_event_index"] for e in cached]
            if len(indexes) != len(set(indexes)):
                raise ValueError("Saved reply reused more than once")
            for event in cached:
                previous = old["api_events"][event["source_event_index"]]
                if any(event[k] != previous[k] for k in ("request", "stage", "response")):
                    raise ValueError("Cached request/reply mismatch")
            if arm == "baseline":
                if len(cached) != len(old["api_events"]) or len(cached) != len(row["api_events"]):
                    raise ValueError("Control did not reproduce all saved calls")
                if any(row["analysis"][k] != old["analysis"][k] for k in ("decision", "target", "meanings", "per_age")):
                    raise ValueError("Control does not exactly reproduce source")
        p = {r["item_id"]: r["analysis"] for r in records}
        predictions[arm] = p
        metrics = support.detection(p, gold)
        metrics.update(pair_success_count=sum(p[f"J{i:02d}"]["decision"] == "PUN" and p[f"D{i:02d}"]["decision"] == "NON_PUN" for i in range(1, 26)),
                       pair_count=25, target_matches=sum(p[i]["decision"] == "PUN" and support.normalized_target(p[i]["target"]) == support.normalized_target(gold[i]["ambiguous_term"]) for i in positives),
                       target_denominator=len(positives), age_gold_positive_labels=support.age_metrics(p, gold, positives),
                       common_contract_failures=sum(not r["common_contract_passed"] for r in records),
                       records_sha256=support.sha(run / arm / "records.jsonl"),
                       api_usage={origin: support.api_totals([{"api_events": [e for e in r["api_events"] if e["origin"] == origin]} for r in records]) for origin in ("cached", "new")})
        result["arms"][arm] = metrics
    changes = [{"item_id": i, "gold": gold[i], **{a: predictions[a][i] for a in ARMS}}
               for i in gold if predictions["baseline"][i] != predictions["contextual"][i]]
    result.update(changed_output_count=len(changes), timing_policy="Identical requests are replayed; no fresh full-run latency claim.", human_review="pending")
    support.jsonl(run / "changes.jsonl", changes)
    support.write(run / "evaluation.json", result)
    if not (run / "blind_review").exists():
        support.packets(run)
        directory = run / "blind_review"
        shutil.copyfile(directory / "packets.jsonl", directory / "all_packets.jsonl")
        keys = json.loads((directory / "identity_key.json").read_text())
        changed_ids = {r["item_id"] for r in changes}
        cases = {k["case"] for k in keys if k["item_id"] in changed_ids}
        support.jsonl(directory / "packets.jsonl", [p for p in support.rows(directory / "all_packets.jsonl") if p["case"] in cases])
        review_manifest = json.loads((directory / "manifest.json").read_text())
        review_manifest.update(packets_sha256=support.sha(directory / "packets.jsonl"),
                               all_packets_sha256=support.sha(directory / "all_packets.jsonl"),
                               case_count=len(cases), selection="All changed assignment outputs; both orders. No gold/performance-based selection.")
        support.write(directory / "manifest.json", review_manifest)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, default=ROOT / "runs/candidate_continuation_comparison/20261003T032128.960031Z")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/contextual_wordplay")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--worker", choices=["stage_baseline", "stage_contextual", "baseline", "contextual", "control_check", "stage_score", "score", "review"])
    args = parser.parse_args()
    if args.worker:
        if not args.run:
            parser.error("--worker requires --run")
        run = args.run.resolve()
        if args.worker.startswith("stage_") and args.worker != "stage_score":
            stage_worker(run, args.worker.removeprefix("stage_"))
        elif args.worker in ARMS:
            corpus_worker(run, args.worker)
        elif args.worker == "stage_score":
            print(json.dumps(stage_score(run), indent=2))
        elif args.worker == "score":
            print(json.dumps(corpus_score(run), indent=2))
        elif args.worker == "control_check":
            verify_control(run)
        else:
            support.judge(run)
        return
    if args.concurrency < 1:
        parser.error("Concurrency must be positive")
    args.source_run = args.source_run.resolve()
    run = prepare(args)
    print(f"Frozen contextual comparison: {run}", flush=True)
    if not args.prepare_only:
        for phase in ("stage_baseline", "stage_contextual", "stage_score", "baseline", "control_check", "contextual", "score", "review"):
            subprocess.run([sys.executable, str(run / "runner.py"), "--run", str(run), "--worker", phase], cwd=ROOT, check=True)
        manifest = support.check_frozen(run)
        manifest.update(status="complete", finished_at=support.utc())
        support.write(run / "manifest.json", manifest)
        subprocess.run([sys.executable, str(run / "summarize.py"), "--run", str(run)], cwd=ROOT, check=True)
        print(f"Summary: {run / 'summary.json'}", flush=True)


if __name__ == "__main__":
    main()
