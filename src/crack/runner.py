"""Pipeline runner with layer registry.

Layer registry
--------------
Layers are registered callables with signature:
    (record: AnalysisRecord, settings: Settings) -> AnalysisRecord

Register a layer:
    register_layer("L1", run_l1)

The runner calls registered layers in registration order.  Per-item
exceptions are caught and recorded as a LayerTrace(status="ERROR") rather
than crashing the whole run.

Output layout
-------------
    runs/<utc-timestamp>/
        records.jsonl   — one JSON object per input item
        run_meta.json   — config snapshot + git SHA

CLI
---
    crack --blind <path> [--output <root>]
    # or
    python -m crack.runner --blind <path> [--output <root>]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import warnings

# Suppress google-genai SDK internal AFC warning notice
warnings.filterwarnings("ignore", message=r".*automatic function calling.*")
try:
    from google.genai.models import Models
    Models._logged_afc_warning = True
except Exception:
    pass

# Support direct script execution without `python -m`
if __package__ in (None, ""):
    _src_dir = Path(__file__).resolve().parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from crack.config import DEFAULT_SETTINGS, Settings
    from crack.decisions import CANDIDATE_SEARCH_VERSION, DETECTION_LAYERS, detection_decision
    from crack.validation import RESPONSE_CONTRACT_VERSION
    from crack.age_evidence import AGE_AGGREGATION_VERSION, AGE_RESPONSE_CONTRACT_VERSION
    from crack.corpus import evaluate_run, load_blind
    from crack.enums import (
        AmbiguityAblation,
        AnchorRelation,
        AnchoringStatus,
        DistinctnessStatus,
        MainClassification,
        AgeAppropriatenessVerdict,
        ComprehensionStatus,
        ResolutionStatus,
        ScopeLabel,
    )
    from crack.l0_scope import (
        InputValidationError,
        LayerEvidence,
        assign_scope_label,
        preprocess_input,
    )
    from crack.layers import (
        run_l1,
        run_l2,
        run_l3,
        run_l4,
        run_l5,
        run_l6,
        run_l7,
        run_l8,
    )
    from crack.providers import resolve_backend
    from crack.schema import AgeVerdict, AnalysisRecord, FinalVerdict, LayerTrace
else:
    from .config import DEFAULT_SETTINGS, Settings
    from .decisions import CANDIDATE_SEARCH_VERSION, DETECTION_LAYERS, detection_decision
    from .validation import RESPONSE_CONTRACT_VERSION
    from .age_evidence import AGE_AGGREGATION_VERSION, AGE_RESPONSE_CONTRACT_VERSION
    from .corpus import evaluate_run, load_blind
    from .enums import (
        AmbiguityAblation,
        AnchorRelation,
        AnchoringStatus,
        DistinctnessStatus,
        MainClassification,
        AgeAppropriatenessVerdict,
        ComprehensionStatus,
        ResolutionStatus,
        ScopeLabel,
    )
    from .l0_scope import (
        InputValidationError,
        LayerEvidence,
        assign_scope_label,
        preprocess_input,
    )
    from .layers import (
        run_l1,
        run_l2,
        run_l3,
        run_l4,
        run_l5,
        run_l6,
        run_l7,
        run_l8,
    )
    from .providers import resolve_backend
    from .schema import AgeVerdict, AnalysisRecord, FinalVerdict, LayerTrace



# ---------------------------------------------------------------------------
# Layer registry
# ---------------------------------------------------------------------------

_LAYER_REGISTRY: list[tuple[str, Callable[[AnalysisRecord, Settings], AnalysisRecord]]] = []


def register_layer(
    name: str,
    fn: Callable[[AnalysisRecord, Settings], AnalysisRecord],
) -> None:
    """Append a named layer callable to the execution registry."""
    _LAYER_REGISTRY.append((name, fn))


def clear_registry() -> None:
    """Remove all registered layers.  Intended for use in tests only."""
    _LAYER_REGISTRY.clear()


def _discard_dependent_results(record: AnalysisRecord, name: str) -> None:
    """A skipped/failed layer cannot expose old or partially written results."""
    layers = [f"L{i}" for i in range(1, 9)]
    if name in layers:
        for layer in layers[layers.index(name):]:
            setattr(record, f"{layer.lower()}_result", None)


def execute_layer(
    name: str, fn: Callable[[AnalysisRecord, Settings], AnalysisRecord],
    record: AnalysisRecord, settings: Settings,
    *, stage_observer: Callable[[str], None] | None = None,
) -> AnalysisRecord:
    """Stop dependent work after failure/abstention; always run the finalizer."""
    reason = ""
    if name == "L4":
        record.candidate_search_version = CANDIDATE_SEARCH_VERSION
    if name != "L0-post":
        if any(t.layer in DETECTION_LAYERS and t.status in {"ERROR", "REJECTED"} for t in record.trace):
            reason = "An earlier detection stage failed."
        elif any(t.layer in DETECTION_LAYERS and t.status in {"FAIL", "UNKNOWN"} for t in record.trace):
            reason = "An earlier detection stage rejected the analysis or lacked evidence."
        elif name in {"L5", "L6", "L7", "L8"} and (
            record.l4_result is None or record.l4_result.anchoring_status != AnchoringStatus.PASS
        ):
            reason = "L4 did not confirm two anchored meanings."
        elif name in {"L7", "L8"} and not record.target_ages:
            reason = "No age assessment was requested."
        elif name in {"L6", "L7", "L8"} and (
            record.l5_result is None or record.l5_result.resolution_status != ResolutionStatus.RESOLUTION_PASS
        ):
            reason = "L5 did not confirm semantic resolution."
        elif name in {"L7", "L8"} and (
            record.l6_result is None
            or record.l6_result.distinctness_status != DistinctnessStatus.SENSES_DISTINCT
        ):
            reason = "L6 did not complete the required distinctness assessment."
        elif name == "L8":
            if any(t.layer == "L7" and t.status == "ERROR" for t in record.trace):
                reason = "L7 failed; age assessment stopped."
            elif record.l7_result is None:
                reason = "Comprehension assessment is unavailable."
            elif not any(record.l7_result.per_age_comprehension.get(a)
                         == ComprehensionStatus.FULLY_COMPREHENSIBLE for a in record.target_ages):
                reason = "L7 did not pass for any requested age; age assessment stopped."
    if reason:
        _discard_dependent_results(record, name)
        record.trace.append(LayerTrace(layer=name, status="SKIPPED", reason=reason, duration_ms=0))
        return record
    if stage_observer:
        stage_observer(name)
    try:
        result = fn(record, settings)
        if not isinstance(result, AnalysisRecord):
            raise TypeError(f"{name} must return an AnalysisRecord")
        return result
    except Exception as exc:
        _discard_dependent_results(record, name)
        if name in {"L4", "L5", "L6"} and record.l4_search:
            record.l4_search.stop_reason = "EXECUTION_FAILED"
        if name == "L0-post":
            record.final = FinalVerdict(main_classification=MainClassification.EXECUTION_FAILED,
                                        scope_label=ScopeLabel.NO_SCOPE_MECHANISM,
                                        review_reason=f"Finalization failed: {exc}")
        raise


# ---------------------------------------------------------------------------
# Built-in L0 layers
# ---------------------------------------------------------------------------

def _l0_pre_layer(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L0-pre: validate and normalise input text."""
    start = time.monotonic()
    record.validation_version = RESPONSE_CONTRACT_VERSION
    record.age_validation_version = AGE_RESPONSE_CONTRACT_VERSION
    record.age_aggregation_version = AGE_AGGREGATION_VERSION
    try:
        record.text = preprocess_input(record.text, settings)
        status, reason = "PASS", None
    except InputValidationError as exc:
        status, reason = "ERROR", str(exc)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.trace.append(LayerTrace(
        layer="L0-pre",
        status=status,
        reason=reason,
        duration_ms=duration_ms,
        hints_used=0,
    ))
    return record


def _l0_post_layer(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L0-post: assign scope label from accumulated L2–L4 evidence."""
    start = time.monotonic()

    has_split = False
    has_homo = False
    is_homophone = False
    is_nonlexical = False

    if record.final and record.final.scope_label == ScopeLabel.OUT_OF_SCOPE_HOMOPHONE:
        is_homophone = True

    # Co-occurring soundalike spellings do not establish a homophone joke.
    # Scope follows assessed wordplay evidence, never a token-pair blacklist.
    if is_homophone:
        has_homo = False
        has_split = False
    elif record.l4_result is not None and record.l4_result.anchoring_status == AnchoringStatus.PASS:
        if record.l4_result.anchor_relation == AnchorRelation.RESEGMENTATION:
            has_split = True
        else:
            has_homo = True
    elif record.l3_result is not None and record.l3_result.candidates:
        top = record.l3_result.candidates[0]
        if top.score_components.get("compound_split") == 1.0:
            has_split = True
        elif top.score > 0:
            has_homo = True

    evidence = LayerEvidence(
        has_homograph=has_homo,
        has_compound_split=has_split,
        is_homophone=is_homophone,
        is_nonlexical_joke=is_nonlexical,
    )
    scope_label = assign_scope_label(evidence)

    main_class, review_reason = detection_decision(record, scope_label)
    decided = main_class in {
        MainClassification.VALID_HOMOGRAPH_JOKE, MainClassification.VALID_COMPOUND_SPLIT_JOKE,
        MainClassification.ONE_SENSE_ONLY, MainClassification.RESOLUTION_FAIL, MainClassification.SENSES_TOO_CLOSE,
    }
    record.confidence = (
        record.l5_result.resolution_score if decided and record.l5_result else None
    )
    per_age = {}
    if main_class in {MainClassification.VALID_HOMOGRAPH_JOKE, MainClassification.VALID_COMPOUND_SPLIT_JOKE}:
        for age in record.target_ages:
            comp = record.l7_result.per_age_comprehension.get(age, ComprehensionStatus.AOA_UNKNOWN) if record.l7_result else ComprehensionStatus.AOA_UNKNOWN
            appr = record.l8_result.per_age_verdict.get(age, AgeAppropriatenessVerdict.UNKNOWN) if record.l8_result else AgeAppropriatenessVerdict.UNKNOWN
            per_age[age] = AgeVerdict(comprehension=comp, appropriateness=appr)
    record.final = FinalVerdict(
        main_classification=main_class, scope_label=scope_label,
        per_age=per_age,
        review_reason=review_reason,
    )
    duration_ms = round((time.monotonic() - start) * 1000, 3)

    record.trace.append(LayerTrace(
        layer="L0-post",
        status="OK",
        reason=review_reason or f"scope_label={scope_label}",
        duration_ms=duration_ms,
        hints_used=0,
    ))
    return record


register_layer("L0-pre", _l0_pre_layer)
register_layer("L1", run_l1)
register_layer("L2", run_l2)
register_layer("L3", run_l3)
register_layer("L4", run_l4)
register_layer("L5", run_l5)
register_layer("L6", run_l6)
register_layer("L7", run_l7)
register_layer("L8", run_l8)
register_layer("L0-post", _l0_post_layer)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _run_fingerprint(blind_path: str | Path, settings: Settings) -> dict:
    """Freeze inputs, source/prompt bytes and nonsecret settings before inference."""
    package_root = Path(__file__).resolve().parent
    source_files = sorted([
        *package_root.glob("*.py"), *package_root.joinpath("prompts").glob("*.md"),
    ])
    excluded = {name for name in Settings.model_fields if name.endswith(("_API_KEY", "_BASE_URL"))}
    return {
        "blind_sha256": hashlib.sha256(Path(blind_path).read_bytes()).hexdigest(),
        "source_sha256": {
            path.relative_to(package_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "config": settings.model_dump(mode="json", exclude=excluded),
    }


def _check_resume_fingerprint(resume_path: Path, fingerprint: dict) -> None:
    """Reuse decisions only with the same source, prompts and nonsecret settings.

    The corpus may grow; item text and ages are checked separately below.
    Reject incompatible caches before making any new model calls.
    """
    metadata_path = resume_path.parent / "run_meta.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Resume requires readable run_meta.json next to records.jsonl. "
            "Omit --resume to start a fresh run."
        ) from exc
    if not isinstance(metadata, dict) or any(
        metadata.get(key) != fingerprint[key] for key in ("source_sha256", "config")
    ):
        raise ValueError(
            "Resume source, prompts or model/settings differ from this run. "
            "Omit --resume to start a fresh run without mixing results."
        )


def run(
    blind_path: str | Path,
    settings: Settings = DEFAULT_SETTINGS,
    output_root: str | Path = "runs",
    resume_from: str | Path | None = None,
    concurrency: int = 1,
) -> Path:
    """Execute all registered layers over a blind corpus.

    Returns the path to the output directory created for this run.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    if settings is DEFAULT_SETTINGS:
        backend_req = os.getenv("CRACK_BACKEND") or os.getenv("DOUBLETAKE_BACKEND") or "auto"
        backend = resolve_backend(backend_req)
        settings = DEFAULT_SETTINGS.model_copy(update={
            "L4_BACKEND": backend,
            "L5_BACKEND": backend,
            "L6_BACKEND": backend,
            "L7_BACKEND": backend,
            "L8_BACKEND": backend,
        })

    blind_items = load_blind(blind_path)
    fingerprint = _run_fingerprint(blind_path, settings)

    existing_records: dict[str, AnalysisRecord] = {}
    if resume_from:
        resume_p = Path(resume_from)
        if not resume_p.is_file():
            raise ValueError(f"Resume records file does not exist: {resume_p}")
        _check_resume_fingerprint(resume_p, fingerprint)
        if resume_p.is_file():
            with resume_p.open("r", encoding="utf-8") as rf:
                for line in rf:
                    line = line.strip()
                    if line:
                        try:
                            rec = AnalysisRecord.model_validate_json(line)
                            # Only resume items that completed cleanly without layer errors
                            if (
                                rec.validation_version == RESPONSE_CONTRACT_VERSION
                                and rec.age_validation_version == AGE_RESPONSE_CONTRACT_VERSION
                                and rec.age_aggregation_version == AGE_AGGREGATION_VERSION
                                and rec.candidate_search_version == CANDIDATE_SEARCH_VERSION
                                and rec.final and not rec.final.review_required
                                and not any(t.status in {"ERROR", "UNKNOWN"} for t in rec.trace)
                            ):
                                verified, _ = detection_decision(rec, rec.final.scope_label)
                                if verified == rec.final.main_classification:
                                    existing_records[rec.item_id] = rec
                        except Exception:
                            pass

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(output_root) / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "timestamp": ts,
        "validation_version": RESPONSE_CONTRACT_VERSION,
        "age_validation_version": AGE_RESPONSE_CONTRACT_VERSION,
        "age_aggregation_version": AGE_AGGREGATION_VERSION,
        "git_sha": _git_sha(),
        "blind_path": str(blind_path),
        **fingerprint,
        "layers": [name for name, _ in _LAYER_REGISTRY],
        "item_count": len(blind_items),
        "concurrency": concurrency,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _process_item(item: BlindItem) -> AnalysisRecord:
        record = AnalysisRecord(
            item_id=item.id,
            text=item.text,
            target_ages=item.target_ages,
        )
        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                record = execute_layer(layer_name, layer_fn, record, settings)
            except Exception as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 3)
                record.trace.append(LayerTrace(
                    layer=layer_name,
                    status="ERROR",
                    reason=f"{type(exc).__name__}: {exc}",
                    duration_ms=duration_ms,
                    hints_used=0,
                ))
        return record

    total_items = len(blind_items)
    completed_count = 0
    file_lock = threading.Lock()

    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as fout:
        remaining_items: list[BlindItem] = []
        for item in blind_items:
            if item.id in existing_records and existing_records[item.id].text == item.text and existing_records[item.id].target_ages == item.target_ages:
                record = existing_records[item.id]
                fout.write(record.model_dump_json() + "\n")
                fout.flush()
                completed_count += 1
            else:
                remaining_items.append(item)

        if completed_count > 0:
            print(f"Resumed {completed_count}/{total_items} items from previous run. Processing remaining {len(remaining_items)} items...", flush=True)

        active_workers = min(concurrency, len(remaining_items))
        print(
            f"Starting {len(remaining_items)} items with {active_workers} concurrent worker(s). "
            f"Records: {out_dir / 'records.jsonl'}",
            flush=True,
        )

        if concurrency <= 1:
            for item in remaining_items:
                record = _process_item(item)
                completed_count += 1
                fout.write(record.model_dump_json() + "\n")
                fout.flush()
                if completed_count % 10 == 0 or completed_count == total_items:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress: {completed_count}/{total_items} items processed ({completed_count/total_items:.1%})", flush=True)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(_process_item, item): item for item in remaining_items}
                for future in concurrent.futures.as_completed(futures):
                    record = future.result()
                    with file_lock:
                        completed_count += 1
                        fout.write(record.model_dump_json() + "\n")
                        fout.flush()
                        if completed_count % 10 == 0 or completed_count == total_items:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress: {completed_count}/{total_items} items processed ({completed_count/total_items:.1%})", flush=True)

    return out_dir


def format_analysis_report(record: AnalysisRecord, target_age: int) -> str:
    """Format an AnalysisRecord into a clear, intuitive English analysis report."""
    lines = [
        "",
        "=" * 70,
        "                      CRACK HUMOR ANALYSIS REPORT",
        "=" * 70,
    ]
    mc = record.final.main_classification.value if record.final else "UNKNOWN"

    # 1. Clear Verdict at the very top: Is it a joke?
    if mc in ("VALID_HOMOGRAPH_JOKE", "VALID_COMPOUND_SPLIT_JOKE"):
        verdict = "🎉 VALID JOKE"
    elif mc in ("OUT_OF_SCOPE_HOMOPHONE", "OUT_OF_SCOPE_NONLEXICAL_JOKE"):
        verdict = "⚠️ OUT OF SCOPE (Potential joke beyond homograph model scope)"
    elif mc == "EXECUTION_FAILED":
        verdict = "EXECUTION FAILED — retry or review required"
    elif mc in ("ONE_SENSE_ONLY", "ANCHORING_FAIL", "RESOLUTION_FAIL", "SENSES_TOO_CLOSE"):
        verdict = "NO PUN DETECTED"
    else:
        verdict = "INSUFFICIENT EVIDENCE — context or review required"

    mc_map = {
        "VALID_HOMOGRAPH_JOKE": "VALID_HOMOGRAPH_JOKE (Lexical pun: dual meanings of a single homograph)",
        "VALID_COMPOUND_SPLIT_JOKE": "VALID_COMPOUND_SPLIT_JOKE (Compound resegmentation: word split pun)",
        "ONE_SENSE_ONLY": "ONE_SENSE_ONLY (Context activates only a single literal meaning)",
        "RESOLUTION_FAIL": "RESOLUTION_FAIL (Ambiguity present, but punchline lacks contrast or resolution)",
        "OUT_OF_SCOPE_HOMOPHONE": "OUT_OF_SCOPE_HOMOPHONE (Heterographic wordplay: sounds alike, spelled differently)",
        "OUT_OF_SCOPE_NONLEXICAL_JOKE": "OUT_OF_SCOPE_NONLEXICAL_JOKE (Non-lexical humor: situational, absurd, or slapstick)",
        "NO_AMBIGUITY_FOUND": "NO_AMBIGUITY_FOUND (No lexical ambiguity detected in text)",
        "ANCHORING_FAIL": "ANCHORING_FAIL (Failed to anchor multiple senses in context)",
    }
    mc_desc = mc_map.get(mc, mc)
    conf = f"{record.confidence:.0%}" if record.confidence is not None else "N/A"

    lines.append(f"[VERDICT]           {verdict}")
    lines.append(f"[CLASSIFICATION]    {mc_desc}")
    lines.append(f"[RESOLUTION SCORE]  {conf}")
    if record.final and record.final.review_required:
        lines.append(f"[REVIEW REQUIRED]   {record.final.review_reason}")

    # 2. Text & Genre
    lines.append("-" * 70)
    lines.append(f"[INPUT TEXT]        {record.text}")
    if record.l1_result:
        genre_map = {
            "QA_RIDDLE": "QA_RIDDLE (Question & Answer Riddle)",
            "DEFINITIONAL_ONELINER": "DEFINITIONAL_ONELINER (Dictionary-style one-liner definition)",
            "DIALOGUE_MISUNDERSTANDING": "DIALOGUE_MISUNDERSTANDING (Multi-turn dialogue with sense misalignment)",
            "DECLARATIVE": "DECLARATIVE (Declarative narrative sentence)",
        }
        lines.append(f"[GENRE]             {genre_map.get(record.l1_result.genre.value, record.l1_result.genre.value)}")

    # 3. Wordplay & Senses
    ambiguous_term = None
    if record.l3_result and record.l3_result.candidates:
        ambiguous_term = record.l3_result.candidates[0].term
    elif record.l4_result and record.l4_result.sense_a_anchor_quote:
        ambiguous_term = record.l4_result.sense_a_anchor_quote

    if ambiguous_term:
        lines.append(f"[AMBIGUOUS TERM]    {ambiguous_term}")

    if record.l4_result and record.l4_result.anchoring_status == AnchoringStatus.PASS:
        lines.append(f"[SENSE A]           {record.l4_result.sense_a} (anchor context: \"{record.l4_result.sense_a_anchor_quote}\")")
        lines.append(f"[SENSE B]           {record.l4_result.sense_b} (anchor context: \"{record.l4_result.sense_b_anchor_quote}\")")
        if record.l4_result.resolving_sense:
            res_sense = record.l4_result.resolving_sense
            res_text = record.l4_result.sense_a if res_sense == "sense_a" else record.l4_result.sense_b
            res_label = "Sense A" if res_sense == "sense_a" else "Sense B"
            lines.append(f"[PUNCHLINE SENSE]   {res_label} ({res_text})")

    if record.l6_result and record.l6_result.explanation:
        lines.append(f"[EXPLANATION]       {record.l6_result.explanation}")

    # 4. Age Assessment
    if record.final and record.final.per_age:
        lines.append("-" * 70)
        comp_map = {
            "FULLY_COMPREHENSIBLE": "FULLY_COMPREHENSIBLE (Understands both wordplay readings)",
            "PARTIALLY_COMPREHENSIBLE": "PARTIALLY_COMPREHENSIBLE (Understands only surface literal meaning)",
            "INCOMPREHENSIBLE": "INCOMPREHENSIBLE (Vocabulary or syntax beyond comprehension)",
        }
        appr_map = {
            "FULLY_AGE_APPROPRIATE": "FULLY_AGE_APPROPRIATE (Suitable for target age)",
            "VOCABULARY_TOO_ADVANCED": "VOCABULARY_TOO_ADVANCED (Required vocabulary AoA exceeds age level)",
            "WORDPLAY_SKILL_TOO_ADVANCED": "WORDPLAY_SKILL_TOO_ADVANCED (Resegmentation / wordplay skill exceeds age level)",
        }
        for a, av in record.final.per_age.items():
            comp_str = comp_map.get(av.comprehension.value, av.comprehension.value)
            appr_str = appr_map.get(av.appropriateness.value, av.appropriateness.value)
            lines.append(f"[AGE {a} ASSESSMENT]")
            lines.append(f"  Comprehension:    {comp_str}")
            lines.append(f"  Appropriateness:  {appr_str}")

    lines.append("=" * 70)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="crack",
        description="CRACK: Neuro-symbolic pun identification and developmental appropriateness pipeline.",
    )
    parser.add_argument(
        "--blind", "--input", dest="blind", default=None, metavar="PATH",
        help="Path to the blind JSONL corpus file.",
    )
    parser.add_argument(
        "--text", default=None, metavar="TEXT",
        help="Single text input to analyze directly.",
    )
    parser.add_argument(
        "--age", type=int, default=8, metavar="AGE",
        help="Target age for single text analysis (default: 8).",
    )
    parser.add_argument(
        "--output", default="runs", metavar="DIR_OR_FILE",
        help="Root directory for run output or target .jsonl path (default: runs).",
    )
    parser.add_argument(
        "--eval", default=None, metavar="GOLD_PATH",
        help="Optional path to gold JSONL corpus to evaluate run output against.",
    )
    parser.add_argument(
        "--resume", default=None, metavar="PATH",
        help="Optional path to existing records.jsonl to resume from.",
    )
    parser.add_argument(
        "--backend", default=None, metavar="NAME",
        help="Backend LLM provider (openai, gemini, anthropic, deepseek, etc.).",
    )
    parser.add_argument(
        "--concurrency", "-j", type=int, default=1, metavar="N",
        help="Number of texts processed concurrently (default: 1). Lexical reader access is synchronized; model requests can overlap.",
    )
    parser.add_argument(
        "--candidate-budget", type=int, default=None, metavar="N",
        help="Maximum candidates offered in one L4 shortlist request (default: 8). No tail search or downstream restarts.",
    )
    parser.add_argument(
        "--no-candidate-continuation", action="store_true",
        help="Legacy compatibility flag; downstream candidate continuation is always disabled.",
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Start the interactive CRACK visual web UI server.",
    )
    parser.add_argument(
        "--port", type=int, default=8000, metavar="PORT",
        help="Port for the web UI server (default: 8000).",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", metavar="HOST",
        help="Host for the web UI server (default: 127.0.0.1).",
    )
    args = parser.parse_args(argv)
    if args.concurrency < 1:
        parser.error("--concurrency must be positive")
    if args.candidate_budget is not None and args.candidate_budget < 1:
        parser.error("--candidate-budget must be positive")

    if args.serve:
        import uvicorn
        from crack.serve import app
        print(f"\n✨ Starting CRACK Interactive Web UI at http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
        return

    backend_req = args.backend or os.getenv("CRACK_BACKEND") or os.getenv("DOUBLETAKE_BACKEND") or "auto"
    backend = resolve_backend(backend_req)
    settings = DEFAULT_SETTINGS.model_copy(update={
        "L4_BACKEND": backend,
        "L5_BACKEND": backend,
        "L6_BACKEND": backend,
        "L7_BACKEND": backend,
        "L8_BACKEND": backend,
        "CONTINUE_AFTER_CANDIDATE_REJECTION": False,
        **({"L4_MAX_CANDIDATES": args.candidate_budget} if args.candidate_budget is not None else {}),
    })

    if args.text:
        record = AnalysisRecord(
            item_id="CLI_01",
            text=args.text,
            target_ages=[args.age],
        )
        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                record = execute_layer(layer_name, layer_fn, record, settings)
            except Exception as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 3)
                record.trace.append(LayerTrace(
                    layer=layer_name,
                    status="ERROR",
                    reason=f"{type(exc).__name__}: {exc}",
                    duration_ms=duration_ms,
                    hints_used=0,
                ))
        print(format_analysis_report(record, args.age))
        return

    if not args.blind and not args.serve:
        parser.error("Either --blind/--input <path>, --text <string>, or --serve must be provided.")

    out_root = Path(args.output)
    is_jsonl_target = out_root.suffix == ".jsonl"
    actual_root = out_root.parent if is_jsonl_target else out_root

    out_dir = run(
        blind_path=args.blind,
        settings=settings,
        output_root=actual_root,
        resume_from=args.resume,
        concurrency=args.concurrency,
    )
    records_file = out_dir / "records.jsonl"
    print(f"Run complete. Output: {out_dir}")

    if is_jsonl_target:
        out_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(records_file, out_root)
        print(f"Copied output records to: {out_root}")

    if args.eval:
        eval_res = evaluate_run(records_file, args.eval)
        eval_file = out_dir / "evaluation.json"
        eval_file.write_text(json.dumps(eval_res, indent=2), encoding="utf-8")
        if is_jsonl_target:
            eval_target = out_root.parent / f"{out_root.stem}_eval.json"
            shutil.copyfile(eval_file, eval_target)
        print("\nEvaluation summary:")
        def percent(value):
            return f"{value:.1%}" if value is not None else "N/A"
        print(f"  Classification accuracy (all items): {percent(eval_res['classification_accuracy'])} ({eval_res['correct_classification']}/{eval_res['total_items']})")
        print(f"  Decision coverage: {percent(eval_res['decision_coverage'])} ({eval_res['decided_items']}/{eval_res['total_items']})")
        print(f"  Classification accuracy (decided): {percent(eval_res['classification_accuracy_on_decided'])}")
        binary = eval_res["binary_detection"]
        print(f"  Binary accuracy (all items): {percent(binary['accuracy_all_items'])}")
        print(f"  Binary accuracy (decided): {percent(binary['accuracy_on_decided'])}; coverage: {percent(binary['decision_coverage'])}")
        print(f"  Outcomes: {eval_res['outcome_counts']}")
        print(f"  Age label agreement (all labels): {percent(eval_res['age_accuracy'])} ({eval_res['correct_age_evals']}/{eval_res['total_age_evals']})")
        print(f"  Age assessment coverage: {percent(eval_res['age_assessment_coverage'])} ({eval_res['assessed_age_evals']}/{eval_res['total_age_evals']})")
        print(f"  Age label agreement (assessed): {percent(eval_res['age_accuracy_on_assessed'])}")
        pun_age = eval_res['age_gold_puns']
        print(f"  Age agreement (gold puns, all labels): {percent(pun_age['accuracy_all_labels'])} ({pun_age['correct_labels']}/{pun_age['total_labels']}); coverage: {percent(pun_age['assessment_coverage'])}")
        print(f"  Report written to: {eval_file}")



def main() -> None:
    _main()


if __name__ == "__main__":
    _main()
