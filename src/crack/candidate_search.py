"""Compatibility entry point for the retired cross-layer candidate search.

Current pipelines search only inside L4's shortlist. L5/L6 rejection or
uncertainty terminates detection instead of starting another candidate.
Historical experiments must use their saved source snapshots.
"""


def finish_candidate_search(*args, **kwargs):
    raise ValueError("Cross-layer candidate continuation is disabled; use the bounded L4 shortlist")
