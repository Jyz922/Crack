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
    python -m doubletake.runner --blind <path> [--output <root>]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
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
    from doubletake.config import DEFAULT_SETTINGS, Settings
    from doubletake.corpus import evaluate_run, load_blind
    from doubletake.enums import (
        AnchorRelation,
        AnchoringStatus,
        DistinctnessStatus,
        MainClassification,
        ResolutionStatus,
        ScopeLabel,
    )
    from doubletake.l0_scope import (
        InputValidationError,
        LayerEvidence,
        assign_scope_label,
        preprocess_input,
    )
    from doubletake.layers import (
        run_l1,
        run_l2,
        run_l3,
        run_l4,
        run_l5,
        run_l6,
        run_l7,
        run_l8,
    )
    from doubletake.providers import resolve_backend
    from doubletake.schema import AnalysisRecord, FinalVerdict, LayerTrace
else:
    from .config import DEFAULT_SETTINGS, Settings
    from .corpus import evaluate_run, load_blind
    from .enums import (
        AnchorRelation,
        AnchoringStatus,
        DistinctnessStatus,
        MainClassification,
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
    from .schema import AnalysisRecord, FinalVerdict, LayerTrace



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


# ---------------------------------------------------------------------------
# Built-in L0 layers
# ---------------------------------------------------------------------------

def _l0_pre_layer(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L0-pre: validate and normalise input text."""
    start = time.monotonic()
    try:
        record.text = preprocess_input(record.text, settings)
        status, reason = "OK", None
    except InputValidationError as exc:
        status, reason = "REJECTED", str(exc)
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
    if record.l4_result is not None and record.l4_result.anchoring_status == AnchoringStatus.PASS:
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
        is_homophone=False,
        is_nonlexical_joke=False,
    )
    scope_label = assign_scope_label(evidence)

    main_class = MainClassification.NO_AMBIGUITY_FOUND
    if scope_label == ScopeLabel.OUT_OF_SCOPE_HOMOPHONE:
        main_class = MainClassification.OUT_OF_SCOPE_HOMOPHONE
    elif scope_label == ScopeLabel.OUT_OF_SCOPE_NONLEXICAL_JOKE:
        main_class = MainClassification.OUT_OF_SCOPE_NONLEXICAL_JOKE
    elif record.l4_result is not None and record.l4_result.anchoring_status == AnchoringStatus.ONE_SENSE_ONLY:
        main_class = MainClassification.ONE_SENSE_ONLY
    elif record.l4_result is not None and record.l4_result.anchoring_status == AnchoringStatus.FAIL:
        main_class = MainClassification.ANCHORING_FAIL
    elif record.l5_result is not None:
        if record.l5_result.resolution_status == ResolutionStatus.RESOLUTION_PASS:
            if record.l6_result is not None and record.l6_result.distinctness_status == DistinctnessStatus.SENSES_TOO_CLOSE:
                main_class = MainClassification.SENSES_TOO_CLOSE
            else:
                main_class = (
                    MainClassification.VALID_COMPOUND_SPLIT_JOKE
                    if scope_label == ScopeLabel.COMPOUND_SPLIT
                    else MainClassification.VALID_HOMOGRAPH_JOKE
                )
        elif record.l5_result.resolution_status == ResolutionStatus.RESOLUTION_FAIL:
            main_class = MainClassification.RESOLUTION_FAIL

    # Confidence calculation per README § L6 (lowered when L6 paraphrase is skipped)
    confidence: float | None = None
    if record.l5_result is not None and record.l5_result.resolution_score is not None:
        confidence = float(record.l5_result.resolution_score)
        if record.l6_result is not None:
            if record.l6_result.distinctness_status == DistinctnessStatus.L6_SKIPPED_NO_PARAPHRASE:
                confidence = round(confidence * 0.85, 3)
            elif record.l6_result.distinctness_status == DistinctnessStatus.SENSES_DISTINCT:
                confidence = min(1.0, round(confidence, 3))
    elif record.l3_result is not None and record.l3_result.candidates:
        confidence = round(record.l3_result.candidates[0].score, 3)
    record.confidence = confidence

    duration_ms = round((time.monotonic() - start) * 1000, 3)

    if record.final is None:
        record.final = FinalVerdict(
            main_classification=main_class,
            scope_label=scope_label,
        )
    else:
        record.final = record.final.model_copy(update={
            "scope_label": scope_label,
            "main_classification": main_class,
        })

    record.trace.append(LayerTrace(
        layer="L0-post",
        status="OK",
        reason=f"scope_label={scope_label}",
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


def run(
    blind_path: str | Path,
    settings: Settings = DEFAULT_SETTINGS,
    output_root: str | Path = "runs",
) -> Path:
    """Execute all registered layers over a blind corpus.

    Returns the path to the output directory created for this run.
    """
    if settings is DEFAULT_SETTINGS:
        backend_req = os.getenv("DOUBLETAKE_BACKEND") or "auto"
        backend = resolve_backend(backend_req)
        settings = DEFAULT_SETTINGS.model_copy(update={
            "L4_BACKEND": backend,
            "L5_BACKEND": backend,
            "L6_BACKEND": backend,
            "L7_BACKEND": backend,
            "L8_BACKEND": backend,
        })

    blind_items = load_blind(blind_path)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(output_root) / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as fout:
        for item in blind_items:
            record = AnalysisRecord(
                item_id=item.id,
                text=item.text,
                target_ages=item.target_ages,
            )
            for layer_name, layer_fn in _LAYER_REGISTRY:
                start = time.monotonic()
                try:
                    record = layer_fn(record, settings)
                except Exception as exc:
                    duration_ms = round((time.monotonic() - start) * 1000, 3)
                    record.trace.append(LayerTrace(
                        layer=layer_name,
                        status="ERROR",
                        reason=f"{type(exc).__name__}: {exc}",
                        duration_ms=duration_ms,
                        hints_used=0,
                    ))
            fout.write(record.model_dump_json() + "\n")

    meta = {
        "timestamp": ts,
        "git_sha": _git_sha(),
        "blind_path": str(blind_path),
        "config": {
            "MAX_INPUT_CHARS": settings.MAX_INPUT_CHARS,
            "MIN_INPUT_CHARS": settings.MIN_INPUT_CHARS,
            "MAX_NON_ASCII_RATIO": settings.MAX_NON_ASCII_RATIO,
            "L3_TOP_K": settings.L3_TOP_K,
            "L4_BACKEND": settings.L4_BACKEND,
            "L5_BACKEND": settings.L5_BACKEND,
            "L6_BACKEND": settings.L6_BACKEND,
            "L7_BACKEND": settings.L7_BACKEND,
            "L8_BACKEND": settings.L8_BACKEND,
            "L5_QA_WEIGHTS": settings.L5_QA_WEIGHTS,
            "L5_RESOLUTION_THRESHOLDS": dict(settings.L5_RESOLUTION_THRESHOLDS),
        },
        "layers": [name for name, _ in _LAYER_REGISTRY],
        "item_count": len(blind_items),
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    return out_dir


def format_analysis_report(record: AnalysisRecord, target_age: int) -> str:
    """Format an AnalysisRecord into a clear, intuitive human-readable report."""
    lines = [
        "",
        "=" * 67,
        "              DOUBLETAKE 语义与笑话分析报告 (Analysis Report)",
        "=" * 67,
    ]
    mc = record.final.main_classification.value if record.final else "UNKNOWN"

    # 1. Clear Verdict at the very top: Is it a joke?
    if mc in ("VALID_HOMOGRAPH_JOKE", "VALID_COMPOUND_SPLIT_JOKE"):
        verdict = "🎉 是双关笑话 (VALID JOKE)"
    elif mc in ("OUT_OF_SCOPE_HOMOPHONE", "OUT_OF_SCOPE_NONLEXICAL_JOKE"):
        verdict = "⚠️ 可能是笑话，但超出本模型识别范围 (OUT OF SCOPE)"
    else:
        verdict = "❌ 不是笑话 (NOT A JOKE)"

    mc_map = {
        "VALID_HOMOGRAPH_JOKE": "有效同形双关笑话 (VALID_HOMOGRAPH_JOKE - 同拼写词的多义对立)",
        "VALID_COMPOUND_SPLIT_JOKE": "有效复合词拆解笑话 (VALID_COMPOUND_SPLIT_JOKE - 复合词拆分重构语义)",
        "ONE_SENSE_ONLY": "单一词义 (ONE_SENSE_ONLY - 语境仅激活单一字面含义，未构成双关)",
        "RESOLUTION_FAIL": "语义对比未达成 (RESOLUTION_FAIL - 谜底未形成有效双关反差)",
        "OUT_OF_SCOPE_HOMOPHONE": "同音异形双关 (OUT_OF_SCOPE_HOMOPHONE - 读音相同但拼写不同)",
        "OUT_OF_SCOPE_NONLEXICAL_JOKE": "非词汇双关笑话 (OUT_OF_SCOPE_NONLEXICAL_JOKE - 荒诞情境或非语言幽默)",
        "NO_AMBIGUITY_FOUND": "未发现多义词 (NO_AMBIGUITY_FOUND - 文本不含可识别的歧义词)",
        "ANCHORING_FAIL": "语境锚定失败 (ANCHORING_FAIL)",
    }
    mc_desc = mc_map.get(mc, mc)
    conf = f"{record.confidence:.0%}" if record.confidence is not None else "N/A"

    lines.append(f"【判 定 结 论】: {verdict}")
    lines.append(f"【分 类 判 定】: {mc_desc}")
    lines.append(f"【判定置信度】: {conf}")

    # 2. Text & Genre
    lines.append("-" * 67)
    lines.append(f"【分 析 文 本】: {record.text}")
    if record.l1_result:
        genre_map = {
            "QA_RIDDLE": "问答谜语 (QA_RIDDLE)",
            "DEFINITIONAL_ONELINER": "定义式一句话幽默 (DEFINITIONAL_ONELINER)",
            "DIALOGUE_MISUNDERSTANDING": "对话误会 (DIALOGUE_MISUNDERSTANDING)",
            "DECLARATIVE": "陈述句笑话 (DECLARATIVE)",
        }
        lines.append(f"【体 裁 分 类】: {genre_map.get(record.l1_result.genre.value, record.l1_result.genre.value)}")

    # 3. Wordplay & Senses
    ambiguous_term = None
    if record.l3_result and record.l3_result.candidates:
        ambiguous_term = record.l3_result.candidates[0].term
    elif record.l4_result and record.l4_result.sense_a_anchor_quote:
        ambiguous_term = record.l4_result.sense_a_anchor_quote

    if ambiguous_term:
        lines.append(f"【双关歧义词】: {ambiguous_term}")

    if record.l4_result and record.l4_result.anchoring_status == AnchoringStatus.PASS:
        lines.append(f"【含  义  A 】: {record.l4_result.sense_a} (对应语境: \"{record.l4_result.sense_a_anchor_quote}\")")
        lines.append(f"【含  义  B 】: {record.l4_result.sense_b} (对应语境: \"{record.l4_result.sense_b_anchor_quote}\")")
        if record.l4_result.resolving_sense:
            res_sense = record.l4_result.resolving_sense
            res_text = record.l4_result.sense_a if res_sense == "sense_a" else record.l4_result.sense_b
            res_label = "含义 A" if res_sense == "sense_a" else "含义 B"
            lines.append(f"【谜底所用含义】: {res_label} ({res_text})")

    if record.l6_result and record.l6_result.explanation:
        lines.append(f"【幽默机制解析】: {record.l6_result.explanation}")

    # 4. Age Assessment
    if record.final and record.final.per_age:
        lines.append("-" * 67)
        comp_map = {
            "FULLY_COMPREHENSIBLE": "完全能理解 (FULLY_COMPREHENSIBLE)",
            "PARTIALLY_COMPREHENSIBLE": "部分理解 (PARTIALLY_COMPREHENSIBLE - 仅理解表层字面义)",
            "INCOMPREHENSIBLE": "无法理解 (INCOMPREHENSIBLE)",
        }
        appr_map = {
            "FULLY_AGE_APPROPRIATE": "完全适龄 (FULLY_AGE_APPROPRIATE)",
            "VOCABULARY_TOO_ADVANCED": "超龄偏难：词汇水平超出该年龄段认知 (VOCABULARY_TOO_ADVANCED)",
            "WORDPLAY_SKILL_TOO_ADVANCED": "超龄偏难：双关认知技能尚不足 (WORDPLAY_SKILL_TOO_ADVANCED)",
        }
        for a, av in record.final.per_age.items():
            comp_str = comp_map.get(av.comprehension.value, av.comprehension.value)
            appr_str = appr_map.get(av.appropriateness.value, av.appropriateness.value)
            lines.append(f"【{a} 岁儿童评估】: 理解程度: {comp_str}")
            lines.append(f"               适龄结论: {appr_str}")

    lines.append("=" * 67)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m doubletake.runner",
        description="Run the DoubleTake pipeline over a blind JSONL corpus or single text.",
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
    args = parser.parse_args(argv)

    backend_req = os.getenv("DOUBLETAKE_BACKEND") or "auto"
    backend = resolve_backend(backend_req)
    settings = DEFAULT_SETTINGS.model_copy(update={
        "L4_BACKEND": backend,
        "L5_BACKEND": backend,
        "L6_BACKEND": backend,
        "L7_BACKEND": backend,
        "L8_BACKEND": backend,
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
                record = layer_fn(record, settings)
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

    if not args.blind:
        parser.error("Either --blind/--input <path> or --text <string> must be provided.")

    out_root = Path(args.output)
    is_jsonl_target = out_root.suffix == ".jsonl"
    actual_root = out_root.parent if is_jsonl_target else out_root

    out_dir = run(blind_path=args.blind, settings=settings, output_root=actual_root)
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
        print(f"  Classification accuracy: {eval_res['classification_accuracy']:.1%} ({eval_res['correct_classification']}/{eval_res['total_items']})")
        print(f"  Age verdict match rate:  {eval_res['age_accuracy']:.1%} ({eval_res['correct_age_evals']}/{eval_res['total_age_evals']})")
        print(f"  Report written to: {eval_file}")



if __name__ == "__main__":
    _main()
