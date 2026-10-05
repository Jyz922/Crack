"""Validate the actual homepage examples through the production web pipeline.

This command makes live provider requests. Expected labels and targets are
evaluation data only; the request supplies just the example text and age.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

from crack.serve import AnalyzeRequest, _get_configured_settings, analyze_joke


async def validate(repeat: int, output_dir: Path) -> bool:
    source = Path(__file__).resolve().parents[1] / "src/crack/static/index.html"
    match = re.search(r"const presets = (\[.*?\]);", source.read_text(), re.DOTALL)
    if not match:
        raise ValueError("Homepage preset definitions were not found.")
    examples = json.loads(match.group(1))
    settings = _get_configured_settings()
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    print(f"Testing {len(examples)} homepage examples, {repeat} round(s); backend={settings.L4_BACKEND}.", flush=True)
    for round_number in range(1, repeat + 1):
        for example in examples:
            started = time.monotonic()
            # Do not pass the expected classification, target or kind to inference.
            response = await analyze_joke(AnalyzeRequest(text=example["text"], target_age=example["age"]))
            payload = json.loads(response.body)
            status_ok = payload["detection_status"] == example["expected_detection_status"]
            expected_target = example["expected_punchline"]
            target_ok = (payload.get("punchline") or "").casefold() == (expected_target or "").casefold()
            result = {"round": round_number, "example_id": example["id"], "passed": status_ok and target_ok,
                      "expected_detection_status": example["expected_detection_status"],
                      "expected_punchline": expected_target, "elapsed_s": round(time.monotonic() - started, 3),
                      "payload": payload}
            results.append(result)
            (output_dir / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
            print(f"Round {round_number} {example['id']}: {'PASS' if result['passed'] else 'FAIL'} — "
                  f"{payload['detection_status']}, target={payload.get('punchline')!r}, {result['elapsed_s']}s", flush=True)
    passed = sum(item["passed"] for item in results)
    summary = {"passed": passed, "total": len(results), "backend": settings.L4_BACKEND,
               "expected_labels_supplied_to_model": False, "repeat": repeat}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Homepage examples: {passed}/{len(results)} passed. Report: {output_dir}", flush=True)
    return passed == len(results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output_dir = args.output_dir or Path("runs/web_examples") / timestamp
    raise SystemExit(0 if asyncio.run(validate(args.repeat, output_dir)) else 1)


if __name__ == "__main__":
    main()
