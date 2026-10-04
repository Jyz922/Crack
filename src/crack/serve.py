"""CRACK Interactive Web Demo & Visual Pipeline Server.

Runs the real CRACK neuro-symbolic pipeline (L0-L8) with real-time SSE streaming.
Every input joke executes live through tokenization, WordNet retrieval,
AoA evaluation, LLM sense anchoring, incongruity resolution, developmental
modeling, and child-safety guardrails.

Usage:
    python -m crack.serve [--port 8000] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator

# Ensure .env is loaded before configuring backends
from crack.providers import load_dotenv, resolve_backend
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from crack.config import DEFAULT_SETTINGS, Settings
from crack.enums import (
    AnchorRelation,
    AnchoringStatus,
    Genre,
    MainClassification,
    DetectionStatus,
    detection_status_for,
    ResolutionStatus,
    ScopeLabel,
)
from crack.l2_senses import _aoa_tables
from crack.runner import _LAYER_REGISTRY, execute_layer
from crack.schema import (
    AgeAppropriatenessVerdict,
    AgeVerdict,
    AnalysisRecord,
    ComprehensionStatus,
    FinalVerdict,
    L4Result,
    LayerTrace,
)

_LOG = logging.getLogger("crack.serve")
_STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="CRACK Web UI",
    description="Interactive visual demonstration for CRACK neuro-symbolic humor analysis.",
    version="1.0.0",
)


@app.on_event("startup")
async def _warm_lexical_resources() -> None:
    """Build the cached AoA/WordNet index before the first analysis request."""
    start = time.monotonic()
    try:
        await asyncio.to_thread(_aoa_tables)
    except Exception:
        # Keep the web app available; L2 will surface the same resource error
        # in its per-layer trace if lexical data is unavailable.
        _LOG.exception("L2 lexical resource warm-up failed")
        return
    elapsed_ms = (time.monotonic() - start) * 1000
    _LOG.info("L2 lexical resources warmed in %.1f ms", elapsed_ms)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    target_age: int = Field(default=8, ge=4, le=18)


def _tokenize_text(text: str) -> list[dict[str, Any]]:
    """Tokenize text preserving whitespace and position offsets."""
    pattern = re.compile(r"(\w+|[^\w\s]|\s+)")
    tokens = []
    idx = 0
    for match in pattern.finditer(text):
        val = match.group(0)
        is_word = bool(re.match(r"^\w+$", val))
        tokens.append({
            "id": idx,
            "text": val,
            "is_word": is_word,
            "lower": val.lower() if is_word else "",
        })
        idx += 1
    return tokens


def _get_configured_settings() -> Settings:
    """Resolve backend from environment (.env) and configure settings."""
    backend_req = os.getenv("CRACK_BACKEND") or os.getenv("DOUBLETAKE_BACKEND") or "auto"
    backend = resolve_backend(backend_req)
    return DEFAULT_SETTINGS.model_copy(update={
        "L4_BACKEND": backend,
        "L5_BACKEND": backend,
        "L6_BACKEND": backend,
        "L7_BACKEND": backend,
        "L8_BACKEND": backend,
    })


def _build_final_payload(rec: AnalysisRecord, target_age: int) -> dict[str, Any]:
    """Transform an executed AnalysisRecord into the structured frontend payload."""
    tokens = _tokenize_text(rec.text)

    # 1. Candidates from L3
    candidates = []
    if rec.l3_result and rec.l3_result.candidates:
        for c in rec.l3_result.candidates[:6]:
            candidates.append({
                "term": c.term,
                "score": round(c.score, 3),
                "sense_a_id": c.sense_a_id,
                "sense_b_id": c.sense_b_id,
                "split_options": c.split_options,
                "components": c.score_components,
            })

    # Only expose a punchline and dual readings after the pipeline confirms a
    # resolved homographic or compound-split joke. L3 candidates alone are
    # hypotheses, not evidence that a text uses both meanings.
    classification = rec.final.main_classification if rec.final else MainClassification.EXECUTION_FAILED
    if any(t.layer == "L0-post" and t.status == "ERROR" for t in rec.trace):
        classification = MainClassification.EXECUTION_FAILED
    detection_status = detection_status_for(classification)
    review_required = detection_status not in {DetectionStatus.PUN, DetectionStatus.NON_PUN}
    review_reason = (rec.final.review_reason if rec.final else "") if review_required else ""
    if review_required and not review_reason:
        review_reason = "Analysis could not reach a validated decision. Review the execution trace and retry."
    has_confirmed_wordplay = classification in {
        MainClassification.VALID_HOMOGRAPH_JOKE,
        MainClassification.VALID_COMPOUND_SPLIT_JOKE,
    }
    is_joke_result = has_confirmed_wordplay

    # 2. Use the assessed target; lexical ranking is only a proposal.
    punchline = (rec.l4_result.target_term
                 if has_confirmed_wordplay and rec.l4_result
                 and rec.l4_result.anchoring_status == AnchoringStatus.PASS else None)

    # 3. Dual senses from validated L4 evidence only
    sense_a = None
    sense_b = None
    if has_confirmed_wordplay and rec.l4_result and rec.l4_result.anchoring_status == AnchoringStatus.PASS:
        sense_a = {
            "definition": rec.l4_result.sense_a,
            "quote": rec.l4_result.sense_a_anchor_quote,
            "aoa": getattr(rec.l7_result, "sense_a_aoa", None),
            "label": "Sense A (Anchored Meaning)",
        }
        sense_b = {
            "definition": rec.l4_result.sense_b,
            "quote": rec.l4_result.sense_b_anchor_quote,
            "aoa": getattr(rec.l7_result, "sense_b_aoa", None),
            "label": "Sense B (Anchored Meaning)",
        }
    # 4. Incongruity Resolution explanation
    resolution_explanation = ""
    if review_required:
        resolution_explanation = review_reason
    elif not has_confirmed_wordplay:
        resolution_explanation = "No confirmed humorous wordplay was found in this text."
    elif rec.l5_result:
        expl = getattr(rec.l5_result, "explanation", "")
        if expl:
            resolution_explanation = expl
    if not resolution_explanation:
        resolution_explanation = "An explanation was not returned for this assessment."

    # 5. Token annotation
    annotated_tokens = []
    cand_terms = {c["term"].lower(): c for c in candidates}
    for t in tokens:
        w_lower = t["lower"]
        is_punchline = bool(punchline and w_lower == punchline.lower())
        cand_info = cand_terms.get(w_lower)
        annotated_tokens.append({
            **t,
            "is_candidate": bool(cand_info) and not is_punchline,
            "is_punchline": is_punchline,
            "candidate_score": cand_info["score"] if cand_info else None,
            "candidate_term": cand_info["term"] if cand_info else None,
        })

    # 6. Age evidence remains separate from the detection result.
    age_spectrum = {}
    age_assessment_available = bool(is_joke_result)
    age_errors = "; ".join(t.reason or "" for t in rec.trace if t.layer in {"L7", "L8"} and t.status == "ERROR")
    if is_joke_result:
        for a in sorted(set(rec.target_ages) | {target_age}):
            comp = rec.l7_result.per_age_comprehension.get(a) if rec.l7_result else None
            appr = rec.l8_result.per_age_verdict.get(a) if rec.l8_result else None
            detail = rec.l7_result.per_age_details.get(a) if rec.l7_result else None
            summary = rec.l7_result.per_age_summaries.get(a) if rec.l7_result else None
            estimate = rec.l7_result.per_age_estimates.get(a) if rec.l7_result else None
            reason7 = (estimate.reason if estimate else detail.reason if detail else
                       rec.l7_result.explanation if rec.l7_result else "")
            reason8 = rec.l8_result.per_age_reasons.get(a, rec.l8_result.explanation or "") if rec.l8_result else ""
            citations = [e.model_dump(mode="json") for e in rec.l7_result.aoa_evidence] if rec.l7_result else []
            age_spectrum[a] = {
                "comprehension": comp.value if comp else "AOA_UNKNOWN",
                "appropriateness": appr.value if appr else "UNKNOWN",
                "desc": " ".join(x for x in (reason7, reason8, age_errors) if x) or "Age evidence is unavailable. Retry the assessment.",
                "dimensions": detail.model_dump(mode="json") if detail else {},
                "estimate": estimate.model_dump(mode="json") if estimate else None,
                "comprehension_summary": summary.model_dump(mode="json") if summary else None,
                "aoa_evidence": citations,
                "assessment_basis": rec.l7_result.assessment_basis if rec.l7_result else None,
            }
        target_eval = age_spectrum[target_age]
    else:
        target_eval = {"comprehension": "NOT_APPLICABLE", "appropriateness": "NOT_APPLICABLE",
                       "desc": "Age assessment applies to confirmed wordplay."}

    # 7. Empty issue lists cannot turn an unassessed axis into a pass.
    content_issues = rec.l8_result.content_issues if rec.l8_result else []
    inference_issues = rec.l8_result.inference_issues if rec.l8_result else []
    content = rec.l8_result.content_appropriate.get(target_age) if is_joke_result and rec.l8_result else None
    inference = rec.l8_result.inference_appropriate.get(target_age) if is_joke_result and rec.l8_result else None
    is_safe = False if content is False or inference is False else True if content is True and inference is True else None
    safety = {
        "surface_status": "PASS" if content is True else "FAIL" if content is False else "NOT_ASSESSED",
        "inferential_status": "PASS" if inference is True else "FAIL" if inference is False else "NOT_ASSESSED",
        "is_safe": is_safe, "content_issues": content_issues, "inference_issues": inference_issues,
        "notes": (rec.l8_result.per_age_reasons.get(target_age) if rec.l8_result else None) or "Appropriateness evidence is unavailable.",
    }

    # 8. Trace
    trace_summary = [
        {
            "layer": t.layer,
            "status": t.status,
            "duration_ms": t.duration_ms,
            "reason": t.reason,
        }
        for t in rec.trace
    ]

    return {
        "text": rec.text,
        "target_age": target_age,
        "genre": rec.l1_result.genre.value if rec.l1_result else "DECLARATIVE",
        "scope_label": rec.final.scope_label.value if rec.final else "NO_SCOPE_MECHANISM",
        "main_classification": classification.value,
        "detection_status": detection_status.value,
        "review_required": review_required,
        "review_reason": review_reason,
        "suggested_action": "RETRY_ANALYSIS" if detection_status == DetectionStatus.EXECUTION_FAILED else ("REVIEW_OR_ADD_CONTEXT" if review_required else None),
        "age_assessment_available": age_assessment_available,
        "confidence": rec.confidence if not review_required else None,
        "punchline": punchline,
        "tokens": annotated_tokens,
        "candidates": candidates,
        "sense_a": sense_a,
        "sense_b": sense_b,
        "resolution_explanation": resolution_explanation,
        "target_verdict": {
            "age": target_age,
            "comprehension": target_eval["comprehension"],
            "appropriateness": target_eval["appropriateness"],
            "description": target_eval["desc"],
            "aoa_evidence": target_eval.get("aoa_evidence", []),
            "dimensions": target_eval.get("dimensions", {}),
            "comprehension_summary": target_eval.get("comprehension_summary"),
        },
        "age_spectrum": age_spectrum,
        "safety": safety,
        "trace": trace_summary,
    }


# ---------------------------------------------------------------------------
# HTTP Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = _STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>CRACK Static Web File Missing.</h1>", status_code=500)


@app.post("/api/analyze")
async def analyze_joke(req: AnalyzeRequest):
    """Run full real pipeline synchronously and return complete payload."""
    clean_text = req.text.strip()
    settings = _get_configured_settings()

    record = AnalysisRecord(
        item_id=f"WEB_{int(time.time()*1000)}",
        text=clean_text,
        target_ages=[req.target_age],
    )

    loop = asyncio.get_event_loop()
    def _execute():
        rec = record
        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                rec = execute_layer(layer_name, layer_fn, rec, settings)
            except Exception as exc:
                rec.trace.append(LayerTrace(
                    layer=layer_name,
                    status="ERROR",
                    reason=str(exc),
                    duration_ms=round((time.monotonic() - start) * 1000, 1),
                    hints_used=0,
                ))
        return rec

    rec = await loop.run_in_executor(None, _execute)
    payload = _build_final_payload(rec, req.target_age)
    return JSONResponse(content=payload)


@app.get("/api/analyze/stream")
async def stream_analysis(text: str, target_age: int = 8):
    """Real-time SSE event stream executing each layer live."""
    clean_text = text.strip()
    settings = _get_configured_settings()
    loop = asyncio.get_event_loop()

    async def event_generator() -> AsyncGenerator[str, None]:
        rec = AnalysisRecord(
            item_id=f"WEB_{int(time.time()*1000)}",
            text=clean_text,
            target_ages=[target_age],
        )

        tokens = _tokenize_text(clean_text)
        yield f"event: start\ndata: {json.dumps({'message': 'Initializing real pipeline...', 'tokens': tokens})}\n\n"

        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                # Run the actual layer in thread pool to prevent blocking event loop
                layer_future = loop.run_in_executor(None, execute_layer, layer_name, layer_fn, rec, settings)
                while not layer_future.done():
                    done, _ = await asyncio.wait((layer_future,), timeout=15)
                    if not done:
                        # Keep proxies and browsers from treating a slow model call as a dead stream.
                        yield ": keep-alive\n\n"
                rec = layer_future.result()
            except Exception as exc:
                err_ms = round((time.monotonic() - start) * 1000, 1)
                rec.trace.append(LayerTrace(
                    layer=layer_name,
                    status="ERROR",
                    reason=str(exc),
                    duration_ms=err_ms,
                    hints_used=0,
                ))
            duration_ms = round((time.monotonic() - start) * 1000, 1)

            # Send real event payload corresponding to layer completion
            if layer_name == "L1":
                genre = rec.l1_result.genre.value if rec.l1_result else "DECLARATIVE"
                yield f"event: l1\ndata: {json.dumps({'layer': 'L1', 'genre': genre, 'duration_ms': duration_ms, 'message': f'L1 Surface: Detected genre {genre}'})}\n\n"
            elif layer_name == "L2":
                s_count = len(rec.l2_result.senses) if rec.l2_result else 0
                yield f"event: l2\ndata: {json.dumps({'layer': 'L2', 'senses_count': s_count, 'duration_ms': duration_ms, 'message': f'L2 Lexical: Loaded {s_count} WordNet synsets & AoA ratings'})}\n\n"
            elif layer_name == "L3":
                candidates = []
                if rec.l3_result and rec.l3_result.candidates:
                    candidates = [{"term": c.term, "score": round(c.score, 3)} for c in rec.l3_result.candidates[:5]]
                yield f"event: l3\ndata: {json.dumps({'layer': 'L3', 'candidates': candidates, 'duration_ms': duration_ms, 'message': f'L3 Ranking: Identified {len(candidates)} ambiguity candidates'})}\n\n"
            elif layer_name == "L4":
                anchored = rec.l4_result.anchoring_status.value if rec.l4_result else "SKIPPED"
                sense_a_text = rec.l4_result.sense_a if rec.l4_result else ""
                sense_b_text = rec.l4_result.sense_b if rec.l4_result else ""
                yield f"event: l4\ndata: {json.dumps({'layer': 'L4', 'status': anchored, 'sense_a': sense_a_text, 'sense_b': sense_b_text, 'duration_ms': duration_ms, 'message': f'L4 LLM Anchoring ({settings.L4_BACKEND}): {anchored}'})}\n\n"
            elif layer_name == "L5":
                res_status = rec.l5_result.resolution_status.value if rec.l5_result else "SKIPPED"
                score = getattr(rec.l5_result, "resolution_score", None) if rec.l5_result else None
                yield f"event: l5\ndata: {json.dumps({'layer': 'L5', 'status': res_status, 'score': score, 'duration_ms': duration_ms, 'message': f'L5 Incongruity Resolution: {res_status} (score: {score})'})}\n\n"
            elif layer_name == "L6":
                dist = rec.l6_result.distinctness_status.value if rec.l6_result else "SKIPPED"
                yield f"event: l6\ndata: {json.dumps({'layer': 'L6', 'distinctness': dist, 'duration_ms': duration_ms, 'message': f'L6 Distinctness Check: {dist}'})}\n\n"
            elif layer_name == "L7":
                comp = getattr(rec.l7_result.per_age_comprehension.get(target_age), "value", "NOT_ASSESSED") if (rec.l7_result and rec.l7_result.per_age_comprehension) else "UNKNOWN"
                yield f"event: l7\ndata: {json.dumps({'layer': 'L7', 'comprehension': comp, 'duration_ms': duration_ms, 'message': f'L7 Developmental: Age {target_age} -> {comp}'})}\n\n"
            elif layer_name == "L8":
                appr = getattr(rec.l8_result.per_age_verdict.get(target_age), "value", "NOT_ASSESSED") if (rec.l8_result and rec.l8_result.per_age_verdict) else "UNKNOWN"
                yield f"event: l8\ndata: {json.dumps({'layer': 'L8', 'verdict': appr, 'duration_ms': duration_ms, 'message': f'L8 Child Safety Guardrail: {appr}'})}\n\n"

        # Final complete payload
        try:
            payload = _build_final_payload(rec, target_age)
            yield f"event: complete\ndata: {json.dumps(payload)}\n\n"
        except Exception as exc:
            _LOG.error(f"Error building final payload: {exc}", exc_info=True)
            err_payload = {
                "text": clean_text,
                "target_age": target_age,
                "genre": "DECLARATIVE",
                "scope_label": "NO_SCOPE_MECHANISM",
                "main_classification": "EXECUTION_FAILED",
                "detection_status": "EXECUTION_FAILED",
                "review_required": True,
                "review_reason": "The analysis could not be completed. Retry or inspect the execution trace.",
                "suggested_action": "RETRY_ANALYSIS",
                "age_assessment_available": False,
                "confidence": None,
                "punchline": None,
                "tokens": tokens,
                "candidates": [],
                "sense_a": None,
                "sense_b": None,
                "resolution_explanation": "Analysis failed before a validated result could be produced.",
                "target_verdict": {
                    "age": target_age,
                    "comprehension": "UNKNOWN",
                    "appropriateness": "NOT_ASSESSED",
                    "description": "Evaluation could not be completed.",
                },
                "age_spectrum": {},
                "safety": {"surface_status": "NOT_ASSESSED", "inferential_status": "NOT_ASSESSED", "is_safe": None, "notes": "Safety has not been assessed."},
                "trace": [
                    {"layer": t.layer, "status": t.status, "duration_ms": t.duration_ms, "reason": t.reason}
                    for t in rec.trace
                ],
            }
            yield f"event: complete\ndata: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    import uvicorn
    env_port = int(os.environ.get("PORT", 8000))
    env_host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    parser = argparse.ArgumentParser(prog="crack.serve", description="Start CRACK Web UI server.")
    parser.add_argument("--port", type=int, default=env_port, help=f"Port to listen on (default: {env_port})")
    parser.add_argument("--host", default=env_host, help=f"Host address (default: {env_host})")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    args = parser.parse_args()

    print(f"\n✨ CRACK Web UI running at http://{args.host}:{args.port}")
    uvicorn.run("crack.serve:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
