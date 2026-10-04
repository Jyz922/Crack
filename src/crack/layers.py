"""Typed execution wrappers for pipeline layers L1–L8.

Layer contract
--------------
    (record: AnalysisRecord, settings: Settings) -> AnalysisRecord

The function receives the current record, populates its corresponding
layer-result field (e.g. record.l1_result), appends a LayerTrace, and
returns the updated record. The runner catches exceptions per item and records
failures without converting them into successful semantic findings.
"""

from __future__ import annotations

import re
import time

from .config import Settings
from .enums import (
    AgeAppropriatenessVerdict,
    ComprehensionStatus,
    AnchoringStatus,
    DistinctnessStatus,
    ResolutionStatus,
    Genre,
)
from .l1_surface import analyze
from .l2_senses import retrieve
from .l3_candidates import rank
from .l4_anchoring import anchor_l4
from .l5_resolution import resolve_l5
from .l6_distinctness import distinctness_l6
from .l7_comprehension import assess_l7
from .l8_appropriateness import assess_l8
from .schema import AnalysisRecord, L2Result, LayerTrace


def run_l1(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L1: Surface analysis and genre routing."""
    start = time.monotonic()
    record.l1_result = analyze(record.text)
    record.trace.append(LayerTrace(
        layer="L1",
        status="PASS",
        reason=f"genre={record.l1_result.genre}",
        duration_ms=round((time.monotonic() - start) * 1000, 3),
        hints_used=0,
    ))
    return record


def run_l2(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L2: Sense retrieval from lexical resources."""
    if record.l1_result is None:
        raise ValueError("L1 must run before L2: l1_result is None")
    start = time.monotonic()
    senses = retrieve(record.l1_result.tokens, text=record.text)
    record.l2_result = L2Result(senses=senses)
    misses = sum(s.aoa_match == "miss" for s in senses)
    record.trace.append(LayerTrace(
        layer="L2",
        status="PASS" if senses else "UNKNOWN",
        reason=f"senses={len(senses)} aoa_miss={misses}",
        duration_ms=round((time.monotonic() - start) * 1000, 3),
        hints_used=0,
    ))
    return record


def run_l3(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L3: Age-free candidate ranking, with a top-k queue and retained tail."""
    if record.l2_result is None:
        raise ValueError("L2 must run before L3: l2_result is None")
    start = time.monotonic()
    preferred: str | None = None
    if record.l1_result and record.l1_result.genre == Genre.DEFINITIONAL_ONELINER:
        m = re.match(r"^\s*([A-Za-z]+)\s*:", record.text)
        if m:
            preferred = m.group(1).lower()
    elif record.l1_result and record.l1_result.tokens and record.l2_result:
        from collections import Counter
        from .l2_senses import PUN_POSSIBLE_STOPWORDS, STOPWORDS
        counts = Counter(re.sub(r"['’]s?$", "", t.lower()) for t in record.l1_result.tokens if t.isalpha())
        l2_terms = {s.term for s in record.l2_result.senses}
        repeats = [
            w for w, c in counts.items()
            if c >= 2 and w in l2_terms and (w not in STOPWORDS or w in PUN_POSSIBLE_STOPWORDS)
        ]
        if repeats:
            preferred = repeats[0]
    record.l3_result = rank(record.l2_result.senses, settings.L3_TOP_K, preferred_term=preferred)
    record.trace.append(LayerTrace(
        layer="L3",
        status="PASS" if record.l3_result.candidates else "UNKNOWN",
        reason="top=" + ",".join(c.term for c in record.l3_result.candidates)
        + f"; deferred={len(record.l3_result.deferred_candidates)}",
        duration_ms=round((time.monotonic() - start) * 1000, 3),
        hints_used=0,
    ))
    return record


def run_l4(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L4: Sense anchoring — evidence that two meanings are active in the text."""
    return _run_l4(record, settings, continue_search=False)


def resume_l4(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """Historical entry point; continuation now raises before any model call."""
    return _run_l4(record, settings, continue_search=True)


def _run_l4(record: AnalysisRecord, settings: Settings, *, continue_search: bool) -> AnalysisRecord:
    if record.l1_result is None:
        raise ValueError("L1 must run before L4: l1_result is None")
    start = time.monotonic()
    result = anchor_l4(record, settings, continue_search=continue_search)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.l4_result = result
    search = record.l4_search
    search_summary = (
        f" assessed={len(search.findings)}/{search.retrieved_terms} stop={search.stop_reason}"
        if search else ""
    )
    record.trace.append(LayerTrace(
        layer="L4",
        status=("PASS" if result.anchoring_status == AnchoringStatus.PASS else
                "UNKNOWN" if result.anchoring_status == AnchoringStatus.INSUFFICIENT_EVIDENCE else "FAIL"),
        reason=f"status={result.anchoring_status} rel={result.anchor_relation}" + search_summary,
        duration_ms=duration_ms,
        hints_used=0,
        candidate_term=result.target_term or None,
    ))
    return record


def run_l5(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L5: Form-specific semantic resolution."""
    start = time.monotonic()
    result = resolve_l5(record, settings)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.l5_result = result
    record.trace.append(LayerTrace(
        layer="L5",
        status=("PASS" if result.resolution_status == ResolutionStatus.RESOLUTION_PASS else
                "FAIL" if result.resolution_status == ResolutionStatus.RESOLUTION_FAIL else
                "UNKNOWN" if result.resolution_status == ResolutionStatus.INSUFFICIENT_CONTEXT else "ERROR"),
        reason=f"resolution_status={result.resolution_status}",
        duration_ms=duration_ms,
        hints_used=0,
        candidate_term=record.l4_result.target_term if record.l4_result else None,
    ))
    return record


def run_l6(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L6: Sense-distinctness and lexical-granularity check."""
    start = time.monotonic()
    result = distinctness_l6(record, settings)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.l6_result = result
    record.trace.append(LayerTrace(
        layer="L6",
        status=("PASS" if result.distinctness_status == DistinctnessStatus.SENSES_DISTINCT else
                "FAIL" if result.distinctness_status == DistinctnessStatus.SENSES_TOO_CLOSE else "UNKNOWN"),
        reason=f"status={result.distinctness_status} ablation={result.ambiguity_ablation}",
        duration_ms=duration_ms,
        hints_used=0,
        candidate_term=record.l4_result.target_term if record.l4_result else None,
    ))
    return record


def run_l7(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L7: Comprehension assessment (evaluated per target age)."""
    start = time.monotonic()
    result = assess_l7(record, settings)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.l7_result = result
    record.trace.append(LayerTrace(
        layer="L7",
        status=("PASS" if all(v == ComprehensionStatus.FULLY_COMPREHENSIBLE
                              for v in result.per_age_comprehension.values()) else
                "UNKNOWN" if ComprehensionStatus.AOA_UNKNOWN in result.per_age_comprehension.values() else "FAIL"),
        reason=f"ages={list(result.per_age_comprehension.keys())}",
        duration_ms=duration_ms,
        hints_used=0,
    ))
    return record


def run_l8(record: AnalysisRecord, settings: Settings) -> AnalysisRecord:
    """L8: Two-axis appropriateness assessment (evaluated per target age)."""
    start = time.monotonic()
    result = assess_l8(record, settings)
    duration_ms = round((time.monotonic() - start) * 1000, 3)
    record.l8_result = result

    record.trace.append(LayerTrace(
        layer="L8",
        status=("UNKNOWN" if AgeAppropriatenessVerdict.UNKNOWN in result.per_age_verdict.values() else
                "PASS" if all(v == AgeAppropriatenessVerdict.FULLY_AGE_APPROPRIATE
                              for v in result.per_age_verdict.values()) else "FAIL"),
        reason=f"ages={list(result.per_age_verdict.keys())}",
        duration_ms=duration_ms,
        hints_used=0,
    ))
    return record
