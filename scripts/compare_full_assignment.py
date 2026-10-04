#!/usr/bin/env python3
"""Frozen full-task comparison; never changes production prompts, gold or gates.

The coordinator reexecutes its frozen source with an isolated CRACK package.
Inference workers cannot read gold through this code path. Common contracts,
raw SDK observations, anonymous packets and both reviewer orders are retained.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path.cwd()
SOURCE = "Kuperman word-level AoA (shared frozen CSV)"
DECISIONS = {"PUN", "NON_PUN", "INSUFFICIENT_EVIDENCE", "EXECUTION_FAILED", "OUT_OF_SCOPE"}
COMPREHENSION = {"FULLY_COMPREHENSIBLE", "PARTIALLY_COMPREHENSIBLE", "SENSE_B_TOO_ADVANCED", "WORDPLAY_SKILL_TOO_ADVANCED", "AOA_UNKNOWN"}
APPROPRIATENESS = {"FULLY_AGE_APPROPRIATE", "CONTENT_OK_INFERENCE_TOO_ADVANCED", "VOCABULARY_TOO_ADVANCED", "CONTENT_NOT_APPROPRIATE", "UNKNOWN"}
DIMENSIONS = ["detection_reasoning", "meanings_and_evidence", "humor_explanation", "age_evidence", "appropriateness_reasoning"]
POSITIVE = {"VALID_HOMOGRAPH_JOKE", "VALID_COMPOUND_SPLIT_JOKE"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def jsonl(path, values):
    Path(path).write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))


def activate(run):
    sys.path.insert(0, str(run / "workspace/src"))


def fingerprints(run):
    return {p.relative_to(run).as_posix(): sha(p) for p in sorted((run / "workspace").rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}


def check_frozen(run):
    m = json.loads((run / "manifest.json").read_text())
    for name, checksum in m["frozen_sha256"].items():
        if sha(run / name) != checksum:
            raise ValueError(f"Frozen artifact changed: {name}")
    if fingerprints(run) != m["workspace_sha256"]:
        raise ValueError("Frozen source or resources changed")
    return m


def prepare(output, model, concurrency):
    sys.path.insert(0, str(ROOT / "src"))
    from crack.config import DEFAULT_SETTINGS, Settings
    from crack.providers import resolve_model
    from crack.runner import _run_fingerprint
    settings = DEFAULT_SETTINGS.model_copy(update={
        **{f"L{i}_BACKEND": "openai" for i in range(4, 9)},
        **{f"L{i}_MODEL": model for i in range(4, 9)}, "L4_MAX_CANDIDATES": 24,
    })
    if {resolve_model("openai", f"L{i}", settings) for i in range(4, 9)} != {model}:
        raise ValueError("Stage model mismatch")
    run = output.resolve() / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run.mkdir(parents=True, exist_ok=False)
    for name, source in (("blind.jsonl", ROOT / "corpus/joke_corpus_blind.jsonl"),
                         ("gold.jsonl", ROOT / "corpus/joke_corpus_gold.jsonl"),
                         ("runner.py", Path(__file__)),
                         *[(name, ROOT / "experiments/full_assignment" / name)
                           for name in ("direct_prompt.md", "judge_prompt.md", "protocol.md")]):
        shutil.copyfile(source, run / name)
    package = run / "workspace/src/crack"
    shutil.copytree(ROOT / "src/crack", package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    data = run / "workspace/data"
    (data / "nltk_data/corpora").mkdir(parents=True)
    shutil.copyfile(ROOT / "data/aoa_kuperman.csv", data / "aoa_kuperman.csv")
    for resource in (ROOT / "data/nltk_data/corpora").glob("wordnet*"):
        if resource.is_dir():
            shutil.copytree(resource, data / "nltk_data/corpora" / resource.name)
        else:
            shutil.copyfile(resource, data / "nltk_data/corpora" / resource.name)
    excludes = {k for k in Settings.model_fields if k.endswith(("_API_KEY", "_BASE_URL"))}
    config = settings.model_dump(mode="json", exclude=excludes)
    for k in ("ACCEPTED_MECHANISMS", "EXCLUDED_MECHANISMS"):
        config[k] = sorted(config[k])
    arm_order = ["crack", "direct"]
    random.Random(20261002).shuffle(arm_order)
    manifest = {"created_at": utc(), "status": "prepared", "model": model,
                "concurrency": concurrency, "seed": 20261002, "arm_order": arm_order,
                "crack_config": config, "direct_max_completion_tokens": 8192,
                "judge_max_completion_tokens": 8192,
                "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "production_fingerprint": _run_fingerprint(ROOT / "corpus/joke_corpus_blind.jsonl", settings),
                "frozen_sha256": {n: sha(run / n) for n in ("blind.jsonl", "gold.jsonl", "runner.py", "direct_prompt.md", "judge_prompt.md", "protocol.md")},
                "workspace_sha256": fingerprints(run),
                "limitations": ["One fresh pass, not a repeatability study",
                                 "Compares complete configurations, not a pure layering ablation",
                                 "Project age labels are not child comprehension ground truth",
                                 "Automated blind reviewer is the same model family, not a human"]}
    write(run / "manifest.json", manifest)
    return run


def make_packages(run):
    activate(run)
    from crack.l1_surface import analyze
    from crack.l2_senses import aoa_lookup, compound_splits, _aoa_tables
    _aoa_tables()  # same initialization outside both inference timers
    packages = []
    for row in rows(run / "blind.jsonl"):
        words = {t.lower() for t in analyze(row["text"]).tokens}
        # All dictionary-recognized literal parts; no gold target selects them.
        words |= {p for w in list(words) for split in compound_splits(w) for p in split}
        lookup = []
        for word in sorted(words):
            value, match = aoa_lookup(word)
            lookup.append({"word": word, "aoa": value, "match": match, "source": SOURCE})
        packages.append({"item_id": row["id"], "text": row["text"],
                         "target_ages": row["target_ages"], "aoa_lookup": lookup})
    jsonl(run / "shared_inputs.jsonl", packages)
    m = json.loads((run / "manifest.json").read_text())
    m["frozen_sha256"]["shared_inputs.jsonl"] = sha(run / "shared_inputs.jsonl")
    write(run / "manifest.json", m)


def exact_fields(value, fields, where):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f"{where}: missing or extra fields")


def text_value(value, where, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{where}: expected {'string' if empty else 'nonempty string'}")


def validate(data, package):
    """The same assignment-output contract is applied to both configurations."""
    exact_fields(data, {"decision", "scope", "target", "meanings", "explanation", "rejection_reason", "per_age"}, "analysis")
    if data["decision"] not in DECISIONS or data["scope"] not in {"HOMOGRAPH", "COMPOUND_SPLIT", "NONE", "HOMOPHONE", "NONLEXICAL", "UNKNOWN"}:
        raise ValueError("Invalid decision/scope")
    for f in ("target", "explanation", "rejection_reason"):
        text_value(data[f], f, empty=True)
    if not isinstance(data["meanings"], list):
        raise ValueError("meanings must be an array")
    if data["decision"] == "PUN":
        if data["scope"] not in {"HOMOGRAPH", "COMPOUND_SPLIT"} or not data["target"].strip() or data["target"] not in package["text"]:
            raise ValueError("PUN needs an in-scope source target")
        if len(data["meanings"]) != 2 or not data["explanation"].strip() or data["rejection_reason"]:
            raise ValueError("PUN needs two meanings, explanation, no rejection reason")
        for meaning in data["meanings"]:
            exact_fields(meaning, {"definition", "quote", "connection"}, "meaning")
            for f in meaning:
                text_value(meaning[f], f)
            if meaning["quote"] not in package["text"]:
                raise ValueError("Quote is not an exact input substring")
        if data["meanings"][0]["definition"].strip().casefold() == data["meanings"][1]["definition"].strip().casefold():
            raise ValueError("Two identical meaning descriptions")
    elif data["target"] or data["meanings"] or data["explanation"] or not data["rejection_reason"].strip():
        raise ValueError("Non-PUN needs rejection reason without confirmed wordplay")
    if not isinstance(data["per_age"], dict) or not set(data["per_age"]) <= {str(a) for a in package["target_ages"]}:
        raise ValueError("Unexpected age keys")
    for age, assessment in data["per_age"].items():
        exact_fields(assessment, {"comprehension", "appropriateness", "reason", "aoa_evidence"}, f"age {age}")
        if assessment["comprehension"] not in COMPREHENSION or assessment["appropriateness"] not in APPROPRIATENESS:
            raise ValueError("Invalid age status")
        text_value(assessment["reason"], "age reason")
        if not isinstance(assessment["aoa_evidence"], list):
            raise ValueError("AoA evidence must be an array")
        for citation in assessment["aoa_evidence"]:
            exact_fields(citation, {"word", "aoa", "match", "source"}, "citation")
            if citation not in package["aoa_lookup"]:
                raise ValueError("AoA citation not backed by shared table")
    return data


def failure(reason):
    return {"decision": "EXECUTION_FAILED", "scope": "UNKNOWN", "target": "", "meanings": [],
            "explanation": "", "rejection_reason": reason, "per_age": {}}


def source_target(term, text):
    # Case-only normalization is an adapter display operation, not quote repair.
    match = re.search(re.escape(term), text, re.IGNORECASE) if term else None
    return match.group() if match else term


def native_view(record, package):
    raw = record.model_dump(mode="json")
    final = raw.get("final") or {}
    l4, l5, l6 = (raw.get(f"l{i}_result") or {} for i in (4, 5, 6))
    decision = final.get("detection_status", "EXECUTION_FAILED")
    scope = {"NO_SCOPE_MECHANISM": "NONE", "OUT_OF_SCOPE_HOMOPHONE": "HOMOPHONE", "OUT_OF_SCOPE_NONLEXICAL_JOKE": "NONLEXICAL"}.get(final.get("scope_label"), final.get("scope_label", "UNKNOWN"))
    explanation = "\n".join(x for x in (l5.get("explanation"), l6.get("explanation")) if x)
    per_age = {}
    l7, l8 = raw.get("l7_result") or {}, raw.get("l8_result") or {}
    for age, values in final.get("per_age", {}).items():
        # Preserve original reasoning. No program-added citation is credited.
        detail = l7.get("per_age_details", {}).get(str(age), {})
        age_error = "; ".join(t.get("reason", "") for t in raw.get("trace", []) if t.get("layer") in {"L7", "L8"} and t.get("status") == "ERROR")
        reason = "\n".join(x for x in (detail.get("reason") or l7.get("explanation"), l8.get("per_age_reasons", {}).get(str(age)) or l8.get("explanation"), age_error) if x)
        per_age[str(age)] = {**values, "reason": reason or "Age evidence is unavailable.", "aoa_evidence": l7.get("aoa_evidence", [])}
    data = {"decision": decision, "scope": scope, "target": "", "meanings": [],
            "explanation": "", "rejection_reason": "", "per_age": per_age}
    if decision == "PUN":
        data["target"] = source_target(l4.get("target_term", ""), package["text"])
        data["meanings"] = [{"definition": l4.get(f"sense_{s}", ""), "quote": l4.get(f"sense_{s}_anchor_quote", ""), "connection": l4.get("reasoning", "")} for s in ("a", "b")]
        data["explanation"] = explanation
    else:
        data["scope"] = scope if scope in {"HOMOPHONE", "NONLEXICAL"} else "NONE"
        data["rejection_reason"] = "\n".join(x for x in (final.get("review_reason"), l4.get("reasoning"), explanation) if x) or "No completed assessment."
    return data


def observe_sdk(local):
    """Observe SDK calls without altering provider arguments, retries or outputs."""
    from openai.resources.chat.completions import Completions
    original = Completions.create

    def observed(self, *args, **kwargs):
        started = time.monotonic()
        event = {"started_at": utc(), "request": {k: kwargs[k] for k in ("model", "messages", "max_completion_tokens", "temperature", "response_format") if k in kwargs}, "stage": getattr(local, "stage", None)}
        try:
            response = original(self, *args, **kwargs)
            event["response"] = response.model_dump(mode="json")
            event["request_id"] = getattr(response, "_request_id", None)
            return response
        except Exception as exc:
            event["error"] = {"type": type(exc).__name__, "status_code": getattr(exc, "status_code", None), "code": getattr(exc, "code", None)}
            raise
        finally:
            event["duration_seconds"] = time.monotonic() - started
            if hasattr(local, "events"):
                local.events.append(event)

    Completions.create = observed


def request_json(client, prompt, payload, model, budget, validator, local):
    import openai
    message = prompt.rstrip() + "\n\nINPUT JSON:\n" + json.dumps(payload, ensure_ascii=False)
    problems = []
    for format_attempt in range(2):
        parsed = None
        for transport_attempt in range(4):
            try:
                response = client.chat.completions.create(model=model,
                    messages=[{"role": "user", "content": message}],
                    max_completion_tokens=budget, response_format={"type": "json_object"})
                choice = response.choices[0]
                if choice.finish_reason != "stop" or choice.message.refusal:
                    raise ValueError("Incomplete or refused response")
                parsed = json.loads(choice.message.content or "")
                return validator(parsed), problems
            except openai.APIError as exc:
                status = getattr(exc, "status_code", None)
                problems.append({"type": type(exc).__name__, "status_code": status})
                if status is not None and status not in {408, 409, 429} and status < 500:
                    raise
                if transport_attempt == 3:
                    return None, problems
                time.sleep((2, 4, 8)[transport_attempt])
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                problems.append({"type": type(exc).__name__, "reason": str(exc)})
                break  # retry the identical request, never repair evidence
    return None, problems


def worker(run, arm):
    m = check_frozen(run)
    activate(run)
    from crack.config import Settings
    from crack.providers import create_client
    from crack.l2_senses import _aoa_tables
    from crack.runner import _LAYER_REGISTRY, execute_layer
    from crack.schema import AnalysisRecord, LayerTrace
    settings = Settings(**m.get("arm_configs", {}).get(arm, m["crack_config"]))
    _aoa_tables()
    packages = rows(run / "shared_inputs.jsonl")
    local = threading.local()
    observe_sdk(local)
    client = create_client("openai", settings)
    prompt = (run / "direct_prompt.md").read_text()
    destination = run / arm
    destination.mkdir(exist_ok=False)

    def process(package):
        started = time.monotonic()
        local.events, local.stage = [], "direct" if arm == "direct" else None
        local.item_id = package["item_id"]
        output = {"item_id": package["item_id"], "text": package["text"], "target_ages": package["target_ages"], "started_at": utc(), "problems": []}
        try:
            if arm == "direct":
                payload = {k: package[k] for k in ("text", "target_ages", "aoa_lookup")}
                def direct_check(data):
                    validate(data, package)
                    if set(data["per_age"]) != {str(a) for a in package["target_ages"]}:
                        raise ValueError("Requested age assessment missing (AOA_UNKNOWN is allowed)")
                    return data
                data, problems = request_json(client, prompt, payload, m["model"], m["direct_max_completion_tokens"], direct_check, local)
                output["problems"] = problems
                output["analysis"] = data or failure("Direct request failed validation or transport; see attempts.")
                output["common_contract_passed"] = data is not None
            else:
                record = AnalysisRecord(item_id=package["item_id"], text=package["text"], target_ages=package["target_ages"])
                for name, fn in _LAYER_REGISTRY:
                    local.stage = name
                    stage_start = time.monotonic()
                    try:
                        record = execute_layer(name, fn, record, settings,
                                               stage_observer=lambda stage: setattr(local, "stage", stage))
                    except Exception as exc:
                        record.trace.append(LayerTrace(layer=name, status="ERROR", reason=f"{type(exc).__name__}: {exc}", duration_ms=(time.monotonic()-stage_start)*1000))
                output["native_record"] = record.model_dump(mode="json")
                data = native_view(record, package)
                output["native_view"] = data
                try:
                    output["analysis"] = validate(data, package)
                    output["common_contract_passed"] = True
                except ValueError as exc:
                    output["problems"].append({"type": "CommonContractError", "reason": str(exc)})
                    output["analysis"] = failure(str(exc))
                    output["common_contract_passed"] = False
        except Exception as exc:
            output["problems"].append({"type": type(exc).__name__, "reason": str(exc) if not hasattr(exc, "status_code") else f"API status {exc.status_code}"})
            output["analysis"] = failure("Analysis did not complete; see problems.")
            output["common_contract_passed"] = False
        output["api_events"] = local.events
        output["duration_seconds"] = time.monotonic() - started
        output["finished_at"] = utc()
        return output

    started = time.monotonic()
    print(f"{arm}: starting {len(packages)} items, concurrency {m['concurrency']}", flush=True)
    with (destination / "records.jsonl").open("w") as stream, ThreadPoolExecutor(max_workers=m["concurrency"]) as pool:
        futures = [pool.submit(process, p) for p in packages]
        for count, future in enumerate(as_completed(futures), 1):
            record = future.result()
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            if count % 10 == 0:
                print(f"{arm}: {count}/{len(packages)}, elapsed {time.monotonic()-started:.1f}s", flush=True)
    write(destination / "timing.json", {"batch_wall_seconds": time.monotonic()-started, "finished_at": utc(), "concurrency": m["concurrency"]})
    client.close()
    check_frozen(run)


def anonymous(data):
    """Display-only normalization; no semantic explanation is manufactured."""
    value = json.loads(json.dumps(data))
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, str):
            v = re.sub(r"\bL[0-8](?:-post|-pre)?\b", "stage", v)
            v = v.replace("CRACK", "system").replace("Psycholinguistic baseline: ", "Estimate: ").replace("Deterministic baseline: ", "Assessment: ")
            v = v.replace("Direct request failed", "Request failed")
        return v
    return clean(value)


def packets(run):
    manifest = check_frozen(run)
    arms = manifest.get("arm_order", ["crack", "direct"])
    packages = rows(run / "shared_inputs.jsonl")
    if manifest.get("review_item_ids") is not None:
        selected = set(manifest["review_item_ids"])
        packages = [p for p in packages if p["item_id"] in selected]
    results = {arm: {r["item_id"]: r for r in rows(run / arm / "records.jsonl")} for arm in arms}
    rng = random.Random(20261002)
    positions = [arms[0]] * (len(packages)//2) + [arms[1]] * (len(packages)-len(packages)//2)
    rng.shuffle(positions)
    rng.shuffle(packages)
    public, private = [], []
    for index, (p, first) in enumerate(zip(packages, positions), 1):
        second = arms[1] if first == arms[0] else arms[0]
        code = f"R{index:03d}"
        public.append({"case": code, **{k: p[k] for k in ("text", "target_ages", "aoa_lookup")},
                       "A": anonymous(results[first][p["item_id"]]["analysis"]),
                       "B": anonymous(results[second][p["item_id"]]["analysis"])})
        private.append({"case": code, "item_id": p["item_id"], "A": first, "B": second})
    directory = run / "blind_review"
    directory.mkdir(exist_ok=True)
    jsonl(directory / "packets.jsonl", public)
    write(directory / "identity_key.json", private)
    with (directory / "human_ratings.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case", "response", *DIMENSIONS, "errors", "preference", "notes"])
        for p in public:
            for label in ("A", "B"):
                writer.writerow([p["case"], label, *[""]*(len(DIMENSIONS)+3)])
    html = ['<!doctype html><meta charset="utf-8"><title>Anonymous full-assignment review</title>',
            '<style>body{font:15px system-ui;margin:28px;color:#182d3a}article{border:1px solid #ccc;border-radius:10px;padding:20px;margin:25px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px monospace;background:#f5f7f8;padding:15px}summary{cursor:pointer}</style>',
            '<h1>Anonymous full-assignment review</h1><p>No system identities or gold labels. Score each dimension 0–2 using rubric.md; leave non-applicable dimensions blank.</p>']
    import html as h
    for p in public:
        html.append(f'<article><h2>{p["case"]}</h2><p>{h.escape(p["text"])}</p><p>Target ages: {p["target_ages"]}</p><details><summary>Shared word-level AoA table</summary><pre>{h.escape(json.dumps(p["aoa_lookup"], indent=2))}</pre></details><div class="pair">')
        for label in ("A", "B"):
            html.append(f'<section><h3>Response {label}</h3><pre>{h.escape(json.dumps(p[label], ensure_ascii=False, indent=2))}</pre></section>')
        html.append('</div></article>')
    (directory / "packets.html").write_text("\n".join(html))
    shutil.copyfile(run / "judge_prompt.md", directory / "rubric.md")
    write(directory / "manifest.json", {"packets_sha256": sha(directory / "packets.jsonl"), "identity_key_sha256": sha(directory / "identity_key.json"), "seed": 20261002, "first_position_counts": Counter(positions)})


def judge_validate(data):
    exact_fields(data, {"input_is_in_scope_pun", "A", "B", "preference", "preference_reason"}, "review")
    if type(data["input_is_in_scope_pun"]) is not bool or data["preference"] not in {"A", "B", "TIE"}:
        raise ValueError("Invalid reviewer decision")
    text_value(data["preference_reason"], "preference reason")
    for label in ("A", "B"):
        x = data[label]
        exact_fields(x, {"scores", "errors", "rationale"}, "reviewed response")
        exact_fields(x["scores"], DIMENSIONS, "scores")
        for dimension, score in x["scores"].items():
            nullable = dimension in DIMENSIONS[2:] and not data["input_is_in_scope_pun"]
            if nullable:
                if score is not None:
                    raise ValueError("Non-pun wordplay/age scores must be null")
            elif type(score) is not int or score not in {0, 1, 2}:
                raise ValueError("Applicable scores must be integers 0–2")
        text_value(x["rationale"], "rationale")
        if not isinstance(x["errors"], list):
            raise ValueError("Errors must be an array")
        for error in x["errors"]:
            exact_fields(error, {"type", "reason"}, "review error")
            for f in error:
                text_value(error[f], f)
    return data


def judge(run):
    m = check_frozen(run)
    activate(run)
    from crack.config import Settings
    from crack.providers import create_client
    directory = run / "blind_review"
    frozen = json.loads((directory / "manifest.json").read_text())
    if sha(directory / "packets.jsonl") != frozen["packets_sha256"]:
        raise ValueError("Review packets changed")
    local = threading.local()
    observe_sdk(local)
    client = create_client("openai", Settings(**m["crack_config"]))
    prompt = (run / "judge_prompt.md").read_text()
    tasks = [(p, swapped) for p in rows(directory / "packets.jsonl") for swapped in (False, True)]
    destination = directory / "llm_reviews.jsonl"
    if destination.exists():
        raise ValueError("Refusing to overwrite blind review results")

    def process(task):
        p, swapped = task
        payload = {k: p[k] for k in ("text", "target_ages", "aoa_lookup", "A", "B")}
        if swapped:
            payload["A"], payload["B"] = payload["B"], payload["A"]
        local.events, local.stage = [], "anonymous_review"
        started = time.monotonic()
        review, problems = request_json(client, prompt, payload, m["model"], m["judge_max_completion_tokens"], judge_validate, local)
        return {"case": p["case"], "swapped": swapped, "review": review, "problems": problems,
                "api_events": local.events, "duration_seconds": time.monotonic()-started}

    started = time.monotonic()
    print(f"Anonymous LLM review: {len(tasks)} requests, both A/B orders", flush=True)
    with destination.open("w") as stream, ThreadPoolExecutor(max_workers=m["concurrency"]) as pool:
        for count, future in enumerate(as_completed([pool.submit(process, t) for t in tasks]), 1):
            stream.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
            stream.flush()
            if count % 10 == 0:
                print(f"Review: {count}/{len(tasks)}, elapsed {time.monotonic()-started:.1f}s", flush=True)
    write(directory / "timing.json", {"batch_wall_seconds": time.monotonic()-started})
    client.close()


def ratio(a, b):
    return a/b if b else None


def detection(predictions, gold):
    counts = Counter()
    for ident, g in gold.items():
        positive = g["gold_label"] in POSITIVE
        label = predictions[ident]["decision"]
        if label == "PUN":
            counts["tp" if positive else "fp"] += 1
        elif label == "NON_PUN":
            counts["fn" if positive else "tn"] += 1
        else:
            counts["unresolved_positive" if positive else "unresolved_negative"] += 1
    tp, fp, tn, fn, up, un = (counts[k] for k in ("tp", "fp", "tn", "fn", "unresolved_positive", "unresolved_negative"))
    decided = tp+fp+tn+fn
    return {"counts": dict(counts), "correct": tp+tn, "accuracy_all": ratio(tp+tn, len(gold)),
            "accuracy_decided": ratio(tp+tn, decided), "precision": ratio(tp, tp+fp),
            "recall_full_gold": ratio(tp, tp+fn+up), "f1_full_gold": ratio(2*tp, 2*tp+fp+fn+up),
            "coverage": ratio(decided, len(gold)), "outcomes": dict(Counter(p["decision"] for p in predictions.values()))}


def normalized_target(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def age_metrics(predictions, gold, ids):
    total = assessed = correct = cited = 0
    for ident in ids:
        data = predictions[ident]
        for age, expected in gold[ident]["expected_age_verdict"].items():
            total += 1
            value = data["per_age"].get(str(age), {})
            actual = value.get("comprehension" if expected in COMPREHENSION else "appropriateness")
            if actual and actual not in {"AOA_UNKNOWN", "UNKNOWN"}:
                assessed += 1
                correct += int(actual == expected)
            cited += int(any(c.get("aoa") is not None for c in value.get("aoa_evidence", [])))
    return {"total": total, "assessed": assessed, "matches": correct,
            "agreement_all": ratio(correct, total), "coverage": ratio(assessed, total),
            "agreement_assessed": ratio(correct, assessed), "ages_with_verified_vocabulary_citations": cited,
            "vocabulary_citation_coverage": ratio(cited, total)}


def api_totals(records):
    totals, errors, models = Counter(), Counter(), Counter()
    for r in records:
        for event in r["api_events"]:
            totals["observed_calls"] += 1
            resp = event.get("response") or {}
            if resp:
                models[resp.get("model", "unknown")] += 1
                usage = resp.get("usage") or {}
                for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    totals[k] += usage.get(k, 0) or 0
                totals["reasoning_tokens"] += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
            if event.get("error"):
                errors[str(event["error"].get("status_code") or event["error"]["type"])] += 1
    return {**dict(totals), "error_counts": dict(errors), "response_model_ids": dict(models)}


def score(run):
    m = check_frozen(run)
    gold = {r["id"]: r for r in rows(run / "gold.jsonl")}
    blind = {r["id"]: r for r in rows(run / "blind.jsonl")}
    raw, predictions = {}, {}
    for arm in ("crack", "direct"):
        raw[arm] = rows(run / arm / "records.jsonl")
        if len(raw[arm]) != len(gold) or {r["item_id"] for r in raw[arm]} != set(gold):
            raise ValueError("One and only one record required per input")
        for r in raw[arm]:
            if r["text"] != blind[r["item_id"]]["text"] or r["target_ages"] != blind[r["item_id"]]["target_ages"]:
                raise ValueError("Input alignment mismatch")
        predictions[arm] = {r["item_id"]: r["analysis"] for r in raw[arm]}
    positives = {i for i, g in gold.items() if g["gold_label"] in POSITIVE}
    common_tp = {i for i in positives if all(predictions[a][i]["decision"] == "PUN" for a in predictions)}
    result = {"run_path": str(run), "model": m["model"], "arms": {}, "common_true_positive_items": sorted(common_tp)}
    for arm, p in predictions.items():
        metrics = detection(p, gold)
        metrics["pair_success_count"] = sum(p[f"J{i:02d}"]["decision"] == "PUN" and p[f"D{i:02d}"]["decision"] == "NON_PUN" for i in range(1, 26))
        metrics["pair_success_rate"] = metrics["pair_success_count"]/25
        metrics["subgroups"] = {group: {"correct": sum(p[i]["decision"] == ("PUN" if i in positives else "NON_PUN") for i in gold if i.startswith(group)), "total": sum(i.startswith(group) for i in gold)} for group in ("J", "D", "N")}
        matches = {i for i in positives if p[i]["decision"] == "PUN" and normalized_target(p[i]["target"]) == normalized_target(gold[i]["ambiguous_term"])}
        metrics["target_localization"] = {"matches": len(matches), "all_positive_items": len(positives), "recall_all_positive": ratio(len(matches), len(positives)), "agreement_true_positives": ratio(len(matches), metrics["counts"].get("tp", 0))}
        metrics["age_all_labels"] = age_metrics(p, gold, set(gold))
        metrics["age_gold_positive_labels"] = age_metrics(p, gold, positives)
        metrics["age_common_true_positive_labels"] = age_metrics(p, gold, common_tp)
        exact = 0
        for i, g in gold.items():
            predicted = ("VALID_COMPOUND_SPLIT_JOKE" if p[i]["scope"] == "COMPOUND_SPLIT" else "VALID_HOMOGRAPH_JOKE") if p[i]["decision"] == "PUN" else "ONE_SENSE_ONLY" if p[i]["decision"] == "NON_PUN" else p[i]["decision"]
            if arm == "crack":
                record = next(r for r in raw[arm] if r["item_id"] == i)
                predicted = (record["native_record"].get("final") or {}).get("main_classification") if record["common_contract_passed"] else "EXECUTION_FAILED"
            exact += int(predicted == g["gold_label"])
        metrics["exact_label_matches"] = exact
        times = sorted(r["duration_seconds"] for r in raw[arm])
        metrics["timing"] = {**json.loads((run / arm / "timing.json").read_text()), "mean_item_seconds": statistics.mean(times), "median_item_seconds": statistics.median(times), "p95_item_seconds": times[math.ceil(.95*len(times))-1]}
        metrics["api_usage"] = api_totals(raw[arm])
        metrics["common_contract_failures"] = sum(not r["common_contract_passed"] for r in raw[arm])
        metrics["records_sha256"] = sha(run / arm / "records.jsonl")
        result["arms"][arm] = metrics
    paired = Counter()
    differences = []
    for i, g in gold.items():
        expected = "PUN" if i in positives else "NON_PUN"
        a, b = (predictions[arm][i]["decision"] for arm in ("crack", "direct"))
        ca, cb = a == expected, b == expected
        paired["both_correct" if ca and cb else "crack_only_correct" if ca else "direct_only_correct" if cb else "neither_correct"] += 1
        if a != b or predictions["crack"][i]["target"] != predictions["direct"][i]["target"]:
            differences.append({"item_id": i, "text": blind[i]["text"], "gold": g, "crack": predictions["crack"][i], "direct": predictions["direct"][i]})
    result["paired_detection_correctness"] = dict(paired)
    jsonl(run / "differences.jsonl", differences)
    review_path = run / "blind_review/llm_reviews.jsonl"
    if review_path.exists():
        keys = {r["case"]: r for r in json.loads((run / "blind_review/identity_key.json").read_text())}
        reviews = rows(review_path)
        scores = {a: {d: [] for d in DIMENSIONS} for a in predictions}
        preferences = {}
        errors = {a: Counter() for a in predictions}
        for r in reviews:
            if not r["review"]:
                continue
            key = keys[r["case"]]
            for label in ("A", "B"):
                original_label = ("B" if label == "A" else "A") if r["swapped"] else label
                arm = key[original_label]
                for dimension, value in r["review"][label]["scores"].items():
                    if value is not None:
                        scores[arm][dimension].append(value)
                errors[arm].update(e["type"] for e in r["review"][label]["errors"])
            pref = r["review"]["preference"]
            if pref != "TIE":
                label = ("B" if pref == "A" else "A") if r["swapped"] else pref
                pref = key[label]
            preferences.setdefault(r["case"], {})[str(r["swapped"])] = pref
        stable = Counter()
        for case in keys:
            choices = list(preferences.get(case, {}).values())
            stable[choices[0] if len(choices) == 2 and choices[0] == choices[1] else "ORDER_UNSTABLE" if len(choices) == 2 else "INCOMPLETE"] += 1
        result["llm_blind_review"] = {
            "reviewer_model": m["model"], "completed_requests": sum(r["review"] is not None for r in reviews), "planned_requests": 120,
            "stable_case_preferences": dict(stable),
            "mean_scores": {a: {d: {"mean": statistics.mean(v) if v else None, "judgments": len(v)} for d, v in dims.items()} for a, dims in scores.items()},
            "reviewer_flag_counts_across_both_orders": {a: dict(v) for a, v in errors.items()},
            "api_usage": api_totals(reviews),
            "human_review_status": "Pending independent review of anonymous packets and CSV",
        }
    write(run / "evaluation.json", result)
    make_report(run, result)
    return result


def percent(value):
    return "—" if value is None else f"{100*value:.2f}%"


def make_report(run, result):
    names = {"crack": "CRACK", "direct": "Direct full-task LLM"}
    lines = ["# Complete assignment: CRACK versus direct LLM", "",
             f"Frozen 60 texts, 180 target-age annotations, unchanged gold; requested model `{result['model']}`. One fresh run per configuration, 8 workers. Both use the same frozen AoA resource and common output checks. See `protocol.md` and `manifest.json` for the predeclared design.", "",
             "## Detection and paired controls", "",
             "| Configuration | Accuracy (all) | Precision | Recall (full gold) | F1 | Decision coverage | Pair success | Target recall |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, v in result["arms"].items():
        lines.append(f"| {names[arm]} | " + " | ".join(percent(v[k]) for k in ("accuracy_all", "precision", "recall_full_gold", "f1_full_gold", "coverage")) + f" | {v['pair_success_count']}/25 | {v['target_localization']['matches']}/25 |")
    lines += ["", "| Configuration | TP | FP | TN | FN | Unresolved positive / negative | Originals | Rewrites | Ordinary controls |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, v in result["arms"].items():
        c = v["counts"]
        lines.append(f"| {names[arm]} | " + " | ".join(str(c.get(k, 0)) for k in ("tp", "fp", "tn", "fn")) + f" | {c.get('unresolved_positive',0)} / {c.get('unresolved_negative',0)} | " + " | ".join(f"{v['subgroups'][g]['correct']}/{v['subgroups'][g]['total']}" for g in ("J", "D", "N")) + " |")
    lines += ["", "Paired correctness: `" + json.dumps(result["paired_detection_correctness"]) + "`.", "", "## Age: annotation agreement and evidence traceability", "",
              "Primary wordplay age comparison uses the 75 age labels on the 25 original gold puns. All 180 labels are also retained for continuity, including literal-text labels that the current CRACK pipeline does not assess after rejecting a pun. Appropriateness has no independent gold here.", "",
              "| Configuration / subset | Matching labels | Assessed | Agreement (all) | Agreement (assessed) | Age explanations with verified AoA citations |", "|---|---:|---:|---:|---:|---:|"]
    for arm, v in result["arms"].items():
        for field, title in (("age_gold_positive_labels", "gold puns"), ("age_all_labels", "all texts"), ("age_common_true_positive_labels", "common true positives")):
            a = v[field]
            lines.append(f"| {names[arm]} / {title} | {a['matches']}/{a['total']} | {a['assessed']}/{a['total']} | {percent(a['agreement_all'])} | {percent(a['agreement_assessed'])} | {a['ages_with_verified_vocabulary_citations']}/{a['total']} |")
    lines += ["", "Verified citations support word-level vocabulary statements. They do not measure the acquisition of either sense or establish a child's comprehension of the complete joke. CRACK's sense-age numbers are heuristic estimates; its current output does not explicitly cite source entries, and the adapter does not add citations to its answer. This does not mean CRACK has no access to AoA: both configurations use the same CSV; each chooses different queries and age algorithms.", "",
              "## Complete-task latency and observed API usage", "",
              "| Configuration | Batch seconds | Mean item seconds | Median | P95 | Observed SDK calls | Total response tokens |", "|---|---:|---:|---:|---:|---:|---:|"]
    for arm, v in result["arms"].items():
        t, u = v["timing"], v["api_usage"]
        lines.append(f"| {names[arm]} | " + " | ".join(f"{t[k]:.2f}" for k in ("batch_wall_seconds", "mean_item_seconds", "median_item_seconds", "p95_item_seconds")) + f" | {u.get('observed_calls',0)} | {u.get('total_tokens',0):,} |")
    lines += ["", "Includes complete per-item processing and application retries; excludes shared lexical initialization and table preparation. Arms ran sequentially in a preselected order. This is one observation, not a controlled service-latency study. The SDK observer does not expose all internal HTTP retries. CRACK L7/L8 are deterministic in this runner.", ""]
    review = result.get("llm_blind_review")
    if review:
        lines += ["## LLM-assisted anonymous review", "", f"Reviewer `{review['reviewer_model']}` completed {review['completed_requests']}/120 requests: 60 anonymous pairs reviewed in both A/B orders, no identities, gold or aggregate metrics in requests. Human review is pending. Same-model and response-style bias remain possible.", "",
                  "| Dimension (0–2) | CRACK | Direct full-task LLM | Applicable judgments per configuration |", "|---|---:|---:|---:|"]
        for d in DIMENSIONS:
            a, b = (review["mean_scores"][arm][d] for arm in ("crack", "direct"))
            lines.append(f"| {d} | {a['mean']:.3f} | {b['mean']:.3f} | {a['judgments']} / {b['judgments']} |" if a["mean"] is not None and b["mean"] is not None else f"| {d} | — | — | {a['judgments']} / {b['judgments']} |")
        lines += ["", "Stable case preferences (both orders agree): `" + json.dumps(review["stable_case_preferences"]) + "`.", "",
                  "Order-unstable cases remain separate. Means retain both review orders; error flags are reviewer assessments, not independently verified facts. Missing explanations for actual puns are scored rather than excluded.", ""]
    lines += ["## Review and reproduction", "",
              "- `blind_review/packets.html`: anonymous A/B materials.",
              "- `blind_review/human_ratings.csv`: empty independent-review sheet; do not inspect `identity_key.json` before rating.",
              "- `differences.jsonl`: item-aligned decisions and outputs, with frozen gold for analysis after inference.",
              "- `crack/records.jsonl`, `direct/records.jsonl`: complete outputs, raw SDK responses, usage, request IDs, validation issues and timings.",
              "- `workspace/`, `runner.py`, prompts and manifests: frozen source, resources and evaluation protocol; no credentials saved.", "",
              "This compares these full configurations on a previously developed project corpus. It cannot establish a winner on unseen inputs or identify a particular layer's causal contribution. No corpus labels, thresholds or production prompts were modified for this experiment.", ""]
    (run / "comparison.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/full_assignment_comparison")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--worker", choices=["crack", "direct", "packages", "packets", "judge", "score"])
    parser.add_argument("--with-judge", action="store_true")
    args = parser.parse_args()
    if args.worker:
        if not args.run:
            parser.error("--worker requires --run")
        run = args.run.resolve()
        if args.worker in {"crack", "direct"}:
            worker(run, args.worker)
        elif args.worker == "packages":
            make_packages(run)
        elif args.worker == "packets":
            packets(run)
        elif args.worker == "judge":
            judge(run)
        else:
            result = score(run)
            print(json.dumps({a: {k: v[k] for k in ("accuracy_all", "f1_full_gold", "pair_success_count")} for a, v in result["arms"].items()}, indent=2))
        return
    if args.concurrency < 1:
        parser.error("Concurrency must be positive")
    run = prepare(args.output, args.model, args.concurrency)
    print(f"Frozen comparison: {run}", flush=True)
    print(f"Arm order: {json.loads((run / 'manifest.json').read_text())['arm_order']}", flush=True)
    def dispatch(phase):
        subprocess.run([sys.executable, str(run / "runner.py"), "--run", str(run), "--worker", phase], cwd=ROOT, check=True)
    dispatch("packages")
    for arm in check_frozen(run)["arm_order"]:
        dispatch(arm)
    dispatch("packets")
    if args.with_judge:
        dispatch("judge")
    dispatch("score")
    m = check_frozen(run)
    m["status"], m["finished_at"] = "complete", utc()
    write(run / "manifest.json", m)
    print(f"Report: {run / 'comparison.md'}", flush=True)


if __name__ == "__main__":
    main()
