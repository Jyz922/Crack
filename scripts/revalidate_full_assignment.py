#!/usr/bin/env python3
"""Audit-preserving repair for rejecting faithful null/miss AoA references.

No inference prompt, corpus, gold, native gate or model changes. Revalidate all
responses using a generic source-membership rule; null stays unknown and earns
no numeric-source credit. Take the first valid response, never the best answer.
Only changed anonymous cards and failed reviewer calls are reviewed again.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    original = args.run.resolve()
    run = original / "corrected_validation"
    run.mkdir(exist_ok=False)
    original_source = (original / "runner.py").read_text()
    corrected_source = original_source.replace(
        'if citation not in package["aoa_lookup"] or citation["aoa"] is None:',
        'if citation not in package["aoa_lookup"]:').replace(
        'cited += int(bool(value.get("aoa_evidence")))',
        'cited += int(any(c.get("aoa") is not None for c in value.get("aoa_evidence", [])))')
    if corrected_source == original_source:
        raise ValueError("Original runner does not contain the known null-reference bug")
    (run / "runner.py").write_text(corrected_source)
    (run / "revalidation_runner.py").write_bytes(Path(__file__).read_bytes())
    diff = ''.join(difflib.unified_diff(original_source.splitlines(True), corrected_source.splitlines(True), fromfile="original/runner.py", tofile="corrected_validation/runner.py"))
    (run / "validator_patch.diff").write_text(diff)
    spec = importlib.util.spec_from_file_location("frozen_full_assignment", run / "runner.py")
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    manifest = engine.check_frozen(original)
    if manifest["status"] != "complete":
        raise ValueError("Wait for the original comparison to complete before repairing")
    for filename in manifest["frozen_sha256"]:
        if filename != "runner.py":
            shutil.copyfile(original / filename, run / filename)
    (run / "workspace").symlink_to(original / "workspace", target_is_directory=True)
    manifest["frozen_sha256"]["runner.py"] = engine.sha(run / "runner.py")
    manifest["frozen_sha256"]["revalidation_runner.py"] = engine.sha(run / "revalidation_runner.py")
    manifest["frozen_sha256"]["validator_patch.diff"] = engine.sha(run / "validator_patch.diff")
    manifest["status"] = "revalidating"
    manifest["validation_correction"] = {
        "recorded_at": engine.utc(), "original_run": str(original),
        "original_manifest_sha256": engine.sha(original / "manifest.json"),
        "reason": "Faithful citations of null/miss entries describe missing data, not fabricated numeric AoA. Accept exact table references, retain null, credit numeric support only for nonnull values.",
        "selection_rule": "Revalidate every response in chronological order; accept first valid response. No choice based on prediction, gold, reviewer preference or metric improvement.",
        "original_inference_retained": True,
        "runtime_policy": "Original measured latencies, attempts and usage retained, including retries caused by the validator bug; no faster counterfactual timing claimed.",
    }
    engine.write(run / "manifest.json", manifest)
    packages = {p["item_id"]: p for p in engine.rows(run / "shared_inputs.jsonl")}
    changes = []
    for arm in ("crack", "direct"):
        destination = run / arm
        destination.mkdir()
        fixed = []
        for record in engine.rows(original / arm / "records.jsonl"):
            data = None
            candidates = []
            if arm == "crack":
                candidates = [record.get("native_view", record["analysis"])]
            else:
                for event in record["api_events"]:
                    response = event.get("response") or {}
                    choices = response.get("choices") or []
                    if not choices or choices[0].get("finish_reason") != "stop" or choices[0]["message"].get("refusal"):
                        continue
                    try:
                        candidates.append(json.loads(choices[0]["message"].get("content") or ""))
                    except json.JSONDecodeError:
                        continue
            for candidate in candidates:
                try:
                    engine.validate(candidate, packages[record["item_id"]])
                    if arm == "direct" and set(candidate["per_age"]) != {str(a) for a in packages[record["item_id"]]["target_ages"]}:
                        raise ValueError("Requested age assessment missing")
                    data = candidate
                    break
                except (ValueError, TypeError, KeyError):
                    continue
            if data is not None and data != record["analysis"]:
                changes.append({"arm": arm, "item_id": record["item_id"], "before": record["analysis"]["decision"], "after": data["decision"], "reason": "First source-faithful response accepted; explicit missing AoA remains null."})
                record["original_analysis"] = record["analysis"]
                record["original_common_contract_passed"] = record["common_contract_passed"]
                record["analysis"] = data
                record["common_contract_passed"] = True
                record["revalidation"] = "Generic null/miss citation correction, not new model inference"
            fixed.append(record)
        engine.jsonl(destination / "records.jsonl", fixed)
        shutil.copyfile(original / arm / "timing.json", destination / "timing.json")
    engine.write(run / "validation_changes.json", changes)
    print("Source-validation correction:", json.dumps(changes), flush=True)
    engine.packets(run)
    old_packets = {p["case"]: p for p in engine.rows(original / "blind_review/packets.jsonl")}
    new_packets = {p["case"]: p for p in engine.rows(run / "blind_review/packets.jsonl")}
    old_key = json.loads((original / "blind_review/identity_key.json").read_text())
    if old_key != json.loads((run / "blind_review/identity_key.json").read_text()):
        raise ValueError("Case mapping changed")
    changed_cases = {c for c in old_packets if old_packets[c] != new_packets[c]}
    reviews = engine.rows(original / "blind_review/llm_reviews.jsonl")
    reusable, jobs = [], []
    for record in reviews:
        if record["case"] in changed_cases or record["review"] is None:
            jobs.append((record["case"], record["swapped"]))
        else:
            record["review_origin"] = "Original valid review; anonymous packet byte-content unchanged"
            reusable.append(record)
    if len(reviews) != 120 or len(set(jobs)) != len(jobs):
        raise ValueError("Expected one original review per case/order")
    engine.activate(run)
    from crack.config import Settings
    from crack.providers import create_client
    local = threading.local()
    engine.observe_sdk(local)
    client = create_client("openai", Settings(**manifest["crack_config"]))
    prompt = (run / "judge_prompt.md").read_text()

    def review(job):
        case, swapped = job
        p = new_packets[case]
        payload = {k: p[k] for k in ("text", "target_ages", "aoa_lookup", "A", "B")}
        if swapped:
            payload["A"], payload["B"] = payload["B"], payload["A"]
        local.events, local.stage = [], "anonymous_review_after_validation_correction"
        started = time.monotonic()
        data, problems = engine.request_json(client, prompt, payload, manifest["model"], manifest["judge_max_completion_tokens"], engine.judge_validate, local)
        return {"case": case, "swapped": swapped, "review": data, "problems": problems, "api_events": local.events, "duration_seconds": time.monotonic()-started,
                "review_origin": "Replaced inaccurate failure card" if case in changed_cases else "Retry of invalid-format review, identical anonymous request"}

    print(f"Re-review {len(jobs)} case/order requests; other valid reviews retained", flush=True)
    updated = []
    with ThreadPoolExecutor(max_workers=manifest["concurrency"]) as pool:
        for future in as_completed([pool.submit(review, j) for j in jobs]):
            updated.append(future.result())
    client.close()
    engine.jsonl(run / "blind_review/additional_review_calls.jsonl", updated)
    engine.jsonl(run / "blind_review/llm_reviews.jsonl", reusable + updated)
    engine.write(run / "blind_review/review_correction.json", {"changed_cases": sorted(changed_cases), "new_request_count": len(jobs), "reused_valid_request_count": len(reusable), "original_reviews_sha256": engine.sha(original / "blind_review/llm_reviews.jsonl"), "reason": "Re-review changed cards in both orders and retry all invalid-format reviews; no selection by scores."})
    result = engine.score(run)
    manifest["status"], manifest["finished_at"] = "complete", engine.utc()
    engine.write(run / "manifest.json", manifest)
    print(json.dumps({a: {k: v[k] for k in ("accuracy_all", "f1_full_gold", "pair_success_count")} for a, v in result["arms"].items()}, indent=2))
    print("Corrected report:", run / "comparison.md")


if __name__ == "__main__":
    main()
