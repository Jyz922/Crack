"""Compare a frozen local L4 validator with the current one on saved replies.

No model calls. Original records are read-only; acceptance is not a new final
classification. The baseline path must be a trusted repository source snapshot.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from crack import validation
from crack.schema import CandidateEntry


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(module, response, record, percentile, *, audit=None):
    target = response.get("target_term") if isinstance(response, dict) else None
    candidates = [CandidateEntry.model_validate(c) for c in (record.get("l3_result") or {}).get("candidates", [])]
    candidate = next((c for c in candidates if isinstance(target, str)
                      and c.term.strip().casefold() == target.strip().casefold()), None)
    if candidate is None:
        return {"outcome": "REJECTED", "error": "Target is not a supplied candidate"}
    kwargs = {"alternates": candidate.soundalike_alternates, "verify_percentile": percentile}
    if audit is not None:
        kwargs["anchor_audit"] = audit
    try:
        accepted = module.validate_l4_response(copy.deepcopy(response), record["text"], candidate.term,
            candidate.score_components.get("compound_split") == 1.0, candidate.split_options, **kwargs)
        return {"outcome": "VALID", "response": accepted}
    except Exception as exc:
        outcome = "PHONETIC_REJECTION" if type(exc).__name__ == "AlternateNotVerified" else "REJECTED"
        return {"outcome": outcome, "error": f"{type(exc).__name__}: {exc}"}


def replay(baseline_path: Path, record_paths: list[Path], output: Path) -> dict:
    spec = importlib.util.spec_from_file_location("crack._frozen_anchor_validator", baseline_path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    report = {"baseline_contract": baseline.RESPONSE_CONTRACT_VERSION,
              "current_contract": validation.RESPONSE_CONTRACT_VERSION,
              "baseline_source_sha256": sha(baseline_path),
              "current_source_sha256": sha(Path(validation.__file__)),
              "input_records_sha256": {str(p): sha(p) for p in record_paths},
              "scope": "Parsed L4 reply validation only. No API calls or downstream decisions.",
              "attempts": [], "newly_valid": [], "previously_valid_changed": []}
    new_inputs = {}
    for records in record_paths:
        metadata = json.loads((records.parent / "run_meta.json").read_text(encoding="utf-8"))
        percentile = metadata["config"]["PHONETIC_VERIFY_PERCENTILE"]
        for line in records.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for index, attempt in enumerate(record.get("l4_attempts", [])):
                raw = attempt.get("parsed_response")
                audit = []
                old = evaluate(baseline, raw, record, percentile)
                new = evaluate(validation, raw, record, percentile, audit=audit)
                key = {"records": str(records), "item_id": record["item_id"], "attempt_index": index}
                report["attempts"].append({**key, "before": old, "after": new, "anchor_audit": audit})
                if old["outcome"] == "VALID" and old != new:
                    report["previously_valid_changed"].append(key)
                if old["outcome"] != "VALID" and new["outcome"] == "VALID":
                    report["newly_valid"].append(key)
                    row = {"id": record["item_id"], "text": record["text"], "target_ages": record["target_ages"]}
                    if row["id"] in new_inputs and new_inputs[row["id"]] != row:
                        raise ValueError("Different newly valid inputs share an ID; replay datasets separately")
                    new_inputs[row["id"]] = row
    output.mkdir(parents=True, exist_ok=True)
    (output / "replay.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "newly_valid_blind.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in new_inputs.values()), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-validator", type=Path, required=True)
    parser.add_argument("--records", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.baseline_validator, args.records, args.output)
    print(json.dumps({"attempts": len(report["attempts"]), "newly_valid": report["newly_valid"],
                      "previously_valid_changed": report["previously_valid_changed"]}, indent=2))


if __name__ == "__main__":
    main()
