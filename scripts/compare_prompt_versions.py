"""Run a controlled comparison with identical pipeline code and two prompt directories.

Runs fresh provider inference in isolated source snapshots. Each arm receives
the same blind inputs, model configuration and local lexical resources. Gold is
used only by the evaluator. Previous run files are never resumed or overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crack.config import DEFAULT_SETTINGS, Settings
from crack.providers import resolve_backend
from crack.runner import _run_fingerprint
from crack.validation import RESPONSE_CONTRACT_VERSION


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_config(config: dict) -> dict:
    result = dict(config)
    for key in ("ACCEPTED_MECHANISMS", "EXCLUDED_MECHANISMS"):
        if key in result:
            result[key] = sorted(result[key])
    return result


def lexical_hashes() -> dict[str, str]:
    paths = [ROOT / "data/aoa_kuperman.csv"]
    for path in sorted((ROOT / "data/nltk_data/corpora").glob("wordnet*")):
        paths.extend(sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path])
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in paths if p.is_file()}


def prepare(before: Path, after: Path, output: Path, blind: Path, gold: Path,
            settings: Settings, concurrency: int, repeats: int) -> dict:
    if output.exists():
        raise ValueError(f"Output already exists; choose a new directory: {output}")
    names = {p.name for p in (ROOT / "src/crack/prompts").glob("*.md")}
    if any({p.name for p in directory.glob("*.md")} != names for directory in (before, after)):
        raise ValueError("Both arms must supply the same complete set of prompt templates")
    fingerprint = _run_fingerprint(blind, settings)
    code_hashes = {k: v for k, v in fingerprint["source_sha256"].items() if not k.startswith("prompts/")}
    output.mkdir(parents=True)
    prompts = {}
    for arm, directory in (("before", before), ("after", after)):
        workspace = output / "workspaces" / arm
        package = workspace / "src/crack"
        shutil.copytree(ROOT / "src/crack", package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in names:
            shutil.copyfile(directory / name, package / "prompts" / name)
        # L2 locates data relative to its installed source; both snapshots use
        # this same local resource directory and its bytes are checked again.
        (workspace / "data").symlink_to(ROOT / "data", target_is_directory=True)
        prompts[arm] = {name: sha(package / "prompts" / name) for name in sorted(names)}
    changed = [name for name in sorted(names) if prompts["before"][name] != prompts["after"][name]]
    if not changed:
        raise ValueError("The prompt directories are identical; no treatment to compare")
    manifest = {
        "experiment": "prompt_only_comparison", "validation_version": RESPONSE_CONTRACT_VERSION,
        "blind_path": str(blind), "blind_sha256": sha(blind),
        "gold_path": str(gold), "gold_sha256": sha(gold),
        "source_sha256": code_hashes, "prompt_sha256": prompts,
        "lexical_sha256": lexical_hashes(), "config": normalize_config(fingerprint["config"]),
        "concurrency": concurrency, "repeats": repeats, "changed_prompts": changed,
        "note": "Fresh model calls in both arms. One paired run is descriptive, not a causal or significance guarantee.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def check_run(meta: dict, manifest: dict, arm: str) -> None:
    assert meta["validation_version"] == manifest["validation_version"], "Response contract changed"
    assert meta["blind_sha256"] == manifest["blind_sha256"], "Input changed"
    assert normalize_config(meta["config"]) == manifest["config"], "Settings changed"
    code = {k: v for k, v in meta["source_sha256"].items() if not k.startswith("prompts/")}
    assert code == manifest["source_sha256"], "Non-prompt code changed"
    prompts = {k.removeprefix("prompts/"): v for k, v in meta["source_sha256"].items() if k.startswith("prompts/")}
    assert prompts == manifest["prompt_sha256"][arm], "Prompt snapshot changed"


def metrics(evaluation: dict) -> dict:
    binary = evaluation["binary_detection"]
    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None
    # Derive differences from counts, not already rounded display percentages.
    return {"classification_accuracy": ratio(evaluation["correct_classification"], evaluation["total_items"]),
            "decision_coverage": ratio(evaluation["decided_items"], evaluation["total_items"]),
            "classification_accuracy_on_decided": ratio(evaluation["correct_classification"], evaluation["decided_items"]),
            "binary_accuracy_all_items": ratio(binary["correct"], binary["eligible_items"]),
            "binary_accuracy_on_decided": ratio(binary["correct"], binary["decided_items"]),
            "binary_f1_on_decided": ratio(2 * binary["tp"], 2 * binary["tp"] + binary["fp"] + binary["fn"]),
            "age_assessment_coverage": ratio(evaluation["assessed_age_evals"], evaluation["total_age_evals"]),
            "age_accuracy_on_assessed": ratio(evaluation["correct_age_evals"], evaluation["assessed_age_evals"])}


def compare_records(before: Path, after: Path) -> list[dict]:
    def load(path):
        return {r["item_id"]: r for r in map(json.loads, path.read_text().splitlines())}
    a, b = load(before), load(after)
    assert a.keys() == b.keys(), "Prediction IDs differ"
    changed = []
    for ident in sorted(a):
        assert a[ident]["text"] == b[ident]["text"], "Prediction texts differ"
        old, new = a[ident]["final"], b[ident]["final"]
        if old["main_classification"] != new["main_classification"]:
            changed.append({"id": ident, "before": old["main_classification"],
                            "after": new["main_classification"],
                            "before_reason": old.get("review_reason", ""),
                            "after_reason": new.get("review_reason", "")})
    return changed


def run_comparison(output: Path, manifest: dict, backend: str) -> dict:
    pairs = []
    for index in range(manifest["repeats"]):
        arm_results = {}
        # Alternate order across repeated pairs to reduce systematic order effects.
        arms = ("before", "after") if index % 2 == 0 else ("after", "before")
        for arm in arms:
            assert sha(Path(manifest["blind_path"])) == manifest["blind_sha256"]
            assert sha(Path(manifest["gold_path"])) == manifest["gold_sha256"]
            assert lexical_hashes() == manifest["lexical_sha256"], "Lexical resources changed"
            arm_root = output / f"pair_{index + 1:02d}" / arm
            arm_root.mkdir(parents=True)
            env = dict(os.environ, PYTHONPATH=str(output / "workspaces" / arm / "src"), PYTHONUNBUFFERED="1")
            command = [sys.executable, "-m", "crack.runner", "--input", manifest["blind_path"],
                       "--eval", manifest["gold_path"], "--output", str(arm_root / "runs"),
                       "--backend", backend, "--concurrency", str(manifest["concurrency"])]
            print(f"Pair {index + 1}: {arm} started; progress log: {arm_root / 'progress.log'}", flush=True)
            with (arm_root / "progress.log").open("w") as log:
                subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            evaluations = list((arm_root / "runs").glob("*/evaluation.json"))
            if len(evaluations) != 1:
                raise ValueError("Expected exactly one completed evaluation for this arm")
            run_dir = evaluations[0].parent
            meta = json.loads((run_dir / "run_meta.json").read_text())
            check_run(meta, manifest, arm)
            evaluation = json.loads(evaluations[0].read_text())
            assert evaluation["missing_items"] == 0 and evaluation["unverified_contract_items"] == 0
            arm_results[arm] = {"run_dir": str(run_dir), "evaluation": evaluation}
            print(f"Pair {index + 1}: {arm} completed: {json.dumps(metrics(evaluation))}", flush=True)
        old, new = (metrics(arm_results[a]["evaluation"]) for a in ("before", "after"))
        delta = {key: round((new[key] - old[key]) * 100, 2)
                 if old[key] is not None and new[key] is not None else None for key in old}
        pairs.append({"pair": index + 1, **arm_results, "delta_percentage_points": delta,
                      "changed_predictions": compare_records(
                          Path(arm_results["before"]["run_dir"]) / "records.jsonl",
                          Path(arm_results["after"]["run_dir"]) / "records.jsonl")})
        (output / "comparison.json").write_text(json.dumps({"manifest": manifest, "pairs": pairs}, indent=2) + "\n")
    assert sha(Path(manifest["gold_path"])) == manifest["gold_sha256"]
    assert lexical_hashes() == manifest["lexical_sha256"]
    return {"manifest": manifest, "pairs": pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-prompts", type=Path, required=True)
    parser.add_argument("--after-prompts", type=Path, default=ROOT / "src/crack/prompts")
    parser.add_argument("--input", type=Path, default=ROOT / "corpus/joke_corpus_blind.jsonl")
    parser.add_argument("--gold", type=Path, default=ROOT / "corpus/joke_corpus_gold.jsonl")
    parser.add_argument("--backend", default="openai")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepare-only", action="store_true", help="Freeze snapshots without making API requests")
    args = parser.parse_args()
    if args.concurrency < 1 or args.repeats < 1:
        parser.error("concurrency and repeats must be positive")
    backend = resolve_backend(args.backend, DEFAULT_SETTINGS)
    settings = DEFAULT_SETTINGS.model_copy(update={f"L{i}_BACKEND": backend for i in range(4, 9)})
    output = (args.output or ROOT / "runs" / f"prompt_comparison_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}").resolve()
    manifest = prepare(args.before_prompts.resolve(), args.after_prompts.resolve(), output,
                       args.input.resolve(), args.gold.resolve(), settings, args.concurrency, args.repeats)
    print(f"Frozen comparison: {output}; changed prompts: {', '.join(manifest['changed_prompts'])}", flush=True)
    if not args.prepare_only:
        run_comparison(output, manifest, backend)
        print(f"Comparison written to {output / 'comparison.json'}", flush=True)


if __name__ == "__main__":
    main()
