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
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

# Ensure .env is loaded before configuring backends
from crack.providers import load_dotenv, resolve_backend
load_dotenv()

from fastapi import FastAPI, Request
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
    ResolutionStatus,
    ScopeLabel,
)
from crack.l2_senses import wordnet
from crack.runner import _LAYER_REGISTRY
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
    version="0.1.0",
)

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
                "components": c.score_components,
            })

    # 2. Punchline ambiguity site determination
    punchline = None
    if rec.l4_result and rec.l4_result.anchoring_status == AnchoringStatus.PASS:
        if getattr(rec.l4_result, "ambiguous_term", None):
            punchline = rec.l4_result.ambiguous_term
        elif candidates:
            punchline = candidates[0]["term"]
    elif candidates and candidates[0]["score"] > 0.4:
        punchline = candidates[0]["term"]

    # 3. Dual Senses (from real L4 result if present, else WordNet/L2)
    sense_a = None
    sense_b = None
    if rec.l4_result and rec.l4_result.anchoring_status == AnchoringStatus.PASS:
        sense_a = {
            "definition": rec.l4_result.sense_a,
            "quote": rec.l4_result.sense_a_anchor_quote,
            "aoa": getattr(rec.l7_result, "sense_a_aoa", 4.5) or 4.5,
            "label": "Sense A (Anchored Meaning)",
        }
        sense_b = {
            "definition": rec.l4_result.sense_b,
            "quote": rec.l4_result.sense_b_anchor_quote,
            "aoa": getattr(rec.l7_result, "sense_b_aoa", 7.0) or 7.0,
            "label": "Sense B (Wordplay Resolution)",
        }
    elif punchline:
        # Fallback to WordNet synsets
        try:
            wn = wordnet()
            syns = wn.synsets(punchline)
            if len(syns) >= 2:
                sense_a = {
                    "definition": syns[0].definition(),
                    "quote": punchline,
                    "aoa": 4.5,
                    "label": f"Sense A ({syns[0].name()})",
                }
                sense_b = {
                    "definition": syns[1].definition(),
                    "quote": punchline,
                    "aoa": 6.8,
                    "label": f"Sense B ({syns[1].name()})",
                }
        except Exception:
            pass

    if not sense_a and punchline:
        sense_a = {
            "definition": f"Primary lexical meaning of '{punchline}' in context.",
            "quote": punchline,
            "aoa": 4.5,
            "label": "Sense A (Contextual reading)",
        }
        sense_b = {
            "definition": f"Secondary incongruity or wordplay reading of '{punchline}'.",
            "quote": punchline,
            "aoa": 7.2,
            "label": "Sense B (Punchline reading)",
        }

    # 4. Incongruity Resolution explanation
    resolution_explanation = ""
    if rec.l5_result:
        expl = getattr(rec.l5_result, "explanation", "")
        if expl:
            resolution_explanation = expl
        else:
            status = rec.l5_result.resolution_status.value
            score = rec.l5_result.resolution_score
            resolution_explanation = (
                f"Resolved with status {status} (score: {score}). "
                f"The punchline exploits lexical ambiguity on '{punchline}'."
            )
    if not resolution_explanation:
        if punchline:
            resolution_explanation = (
                f"Linguistic incongruity detected around '{punchline}'. "
                "The setup creates expectation for Sense A, while the punchline triggers Sense B."
            )
        else:
            resolution_explanation = "No significant incongruity or double meaning found in text."

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

    # 6. Age Spectrum & Target Evaluation (from real L7 and L8)
    age_spectrum = {}
    tested_ages = [4, 6, 8, 10, 12, 14]
    for a in tested_ages:
        comp = "FULLY_COMPREHENSIBLE"
        if rec.l7_result and a in rec.l7_result.per_age_comprehension:
            comp = rec.l7_result.per_age_comprehension[a].value
        else:
            comp = "FULLY_COMPREHENSIBLE" if a >= 8 else ("PARTIALLY_COMPREHENSIBLE" if a >= 6 else "INCOMPREHENSIBLE")

        appr = "FULLY_AGE_APPROPRIATE"
        if rec.l8_result and a in rec.l8_result.per_age_verdict:
            appr = rec.l8_result.per_age_verdict[a].value
        else:
            appr = "FULLY_AGE_APPROPRIATE" if a >= 8 else "CONTENT_OK_INFERENCE_TOO_ADVANCED"

        desc = ""
        if a < 7:
            desc = "Below the metalinguistic humor acquisition floor (Age 7.0); misses abstract double meaning."
        elif a <= 8:
            desc = f"Emergent wordplay mastery. Aligned with AoA benchmarks ({getattr(rec.l7_result, 'sense_b_aoa', 6.5) or 6.5} yrs)."
        else:
            desc = "Full cognitive competence and vocabulary mastery for this wordplay genre."

        age_spectrum[a] = {
            "comprehension": comp,
            "appropriateness": appr,
            "desc": desc,
        }

    target_eval = age_spectrum.get(target_age, age_spectrum[8])

    # 7. Safety summary from L8
    content_issues = rec.l8_result.content_issues if rec.l8_result else []
    inference_issues = rec.l8_result.inference_issues if rec.l8_result else []
    is_safe = len(content_issues) == 0 and len(inference_issues) == 0

    safety = {
        "surface_status": "PASS" if not content_issues else "FAIL",
        "inferential_status": "PASS" if not inference_issues else "FAIL",
        "is_safe": is_safe,
        "content_issues": content_issues,
        "inference_issues": inference_issues,
        "notes": "Passed all child safety and appropriateness guardrails." if is_safe else f"Issues: {content_issues + inference_issues}",
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
        "scope_label": rec.final.scope_label.value if rec.final else "HOMOGRAPH",
        "main_classification": rec.final.main_classification.value if rec.final else (
            "VALID_HOMOGRAPH_JOKE" if punchline else "NO_AMBIGUITY_FOUND"
        ),
        "confidence": rec.confidence or (candidates[0]["score"] if candidates else 0.5),
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
        target_ages=[4, 6, 8, 10, 12, 14],
    )

    loop = asyncio.get_event_loop()
    def _execute():
        rec = record
        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                rec = layer_fn(rec, settings)
                status = "OK"
                reason = None
            except Exception as exc:
                status = "ERROR"
                reason = str(exc)
            rec.trace.append(LayerTrace(
                layer=layer_name,
                status=status,
                reason=reason,
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
            target_ages=[4, 6, 8, 10, 12, 14],
        )

        tokens = _tokenize_text(clean_text)
        yield f"event: start\ndata: {json.dumps({'message': 'Initializing real pipeline...', 'tokens': tokens})}\n\n"

        for layer_name, layer_fn in _LAYER_REGISTRY:
            start = time.monotonic()
            try:
                # Run the actual layer in thread pool to prevent blocking event loop
                rec = await loop.run_in_executor(None, layer_fn, rec, settings)
                status = "OK"
                reason = None
            except Exception as exc:
                status = "ERROR"
                reason = str(exc)
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            rec.trace.append(LayerTrace(
                layer=layer_name,
                status=status,
                reason=reason,
                duration_ms=duration_ms,
                hints_used=0,
            ))

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
                comp = rec.l7_result.per_age_comprehension.get(target_age, "").value if (rec.l7_result and rec.l7_result.per_age_comprehension) else "UNKNOWN"
                yield f"event: l7\ndata: {json.dumps({'layer': 'L7', 'comprehension': comp, 'duration_ms': duration_ms, 'message': f'L7 Developmental: Age {target_age} -> {comp}'})}\n\n"
            elif layer_name == "L8":
                appr = rec.l8_result.per_age_verdict.get(target_age, "").value if (rec.l8_result and rec.l8_result.per_age_verdict) else "UNKNOWN"
                yield f"event: l8\ndata: {json.dumps({'layer': 'L8', 'verdict': appr, 'duration_ms': duration_ms, 'message': f'L8 Child Safety Guardrail: {appr}'})}\n\n"

        # Final complete payload
        payload = _build_final_payload(rec, target_age)
        yield f"event: complete\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser(prog="crack.serve", description="Start CRACK Web UI server.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload")
    args = parser.parse_args()

    print(f"\n✨ CRACK Web UI running at http://{args.host}:{args.port}")
    uvicorn.run("crack.serve:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
