"""Audit static prompt examples and development texts against known evaluation inputs.

Long phrase matches fail the audit. Short phrase and quoted target-word matches
are review hints, not automatic evidence of leakage. No provider calls are made.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.casefold()))


def phrase_overlap(left: str, right: str) -> tuple[str, str] | None:
    a, b = words(left), words(right)
    if len(a) < 3 or not b:
        return None
    right_text = " " + " ".join(b) + " "
    if " " + " ".join(a) + " " in right_text:
        return "FAIL", " ".join(a)
    for size in (8, 7, 6):
        for start in range(len(a) - size + 1):
            phrase = " ".join(a[start:start + size])
            if " " + phrase + " " in right_text:
                return ("FAIL" if size == 8 else "REVIEW"), phrase
    return None


def evaluation_rows(corpus_dir: Path, include_development: bool = False) -> list[dict]:
    result = []
    for blind in sorted(corpus_dir.rglob("*.jsonl")):
        if not include_development and "prompt_development" in blind.relative_to(corpus_dir).parts:
            continue
        gold = blind.with_name(blind.name.replace("blind.jsonl", "gold.jsonl"))
        targets = {}
        if gold.exists():
            targets = {row["id"]: row.get("ambiguous_term", "")
                       for row in (json.loads(line) for line in gold.read_text().splitlines() if line.strip())}
        for line in blind.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row.get("text"), str):
                continue
            result.append({"dataset": blind.relative_to(corpus_dir).as_posix(), "id": row["id"], "text": row["text"],
                           "target_term": targets.get(row["id"], "")})
    return result


def runtime_instruction_subjects(source_dir: Path) -> list[tuple[str, str, str]]:
    """Inspect literal instruction text in code, excluding comments and input data.

    An AST JoinedStr retains static f-string segments but never evaluates the
    runtime text, candidate, readings, quotes or word-level resource values.
    """
    subjects = []
    for filename, function in (("age_evidence.py", "compact_age_prompt"),
                               ("validation.py", "soundalike_note"),
                               ("l4_anchoring.py", "_anchor_shortlist")):
        path = source_dir / filename
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
        literals = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        subjects.append((f"{filename}:{function}", "\n".join(literals), "runtime_instruction"))
    return subjects


def audit(prompt_dir: Path, corpus_dir: Path, development_path: Path | None = None,
          *, extra_subjects: list[tuple[str, str, str]] | None = None) -> dict:
    references = evaluation_rows(corpus_dir)
    all_references = evaluation_rows(corpus_dir, include_development=True)
    subjects = [(path.name, path.read_text(), "prompt") for path in sorted(prompt_dir.glob("*.md"))]
    subjects.extend(extra_subjects or [])
    if development_path:
        for line in development_path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                subjects.append((row["id"], row["text"], "development"))
    findings = []
    for name, content, kind in subjects:
        for ref in references if kind == "development" else all_references:
            match = phrase_overlap(ref["text"], content)
            if kind == "development" and match is None:
                match = phrase_overlap(content, ref["text"])
            if match:
                severity, phrase = match
            else:
                term = ref["target_term"]
                # Words such as 'run' can be ordinary vocabulary in instructions.
                # A quoted word is surfaced for review, never prohibited outright.
                quoted = bool(term and kind != "development" and any(
                    f"{opening}{term.casefold()}{closing}" in content.casefold()
                    for opening, closing in (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))
                ))
                if not quoted:
                    continue
                severity, phrase = "TERM_REVIEW", term
            findings.append({"subject": name, "kind": kind, "dataset": ref["dataset"],
                             "id": ref["id"], "severity": severity, "matched_text": phrase})
    return {"evaluation_rows": len(references), "all_corpus_text_rows": len(all_references),
            "subjects": len(subjects),
            "subject_sha256": {name: hashlib.sha256(content.encode()).hexdigest() for name, content, _ in subjects},
            "failures": sum(f["severity"] == "FAIL" for f in findings),
            "review_hints": sum(f["severity"] != "FAIL" for f in findings), "findings": findings}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=ROOT / "src/crack/prompts")
    parser.add_argument("--corpus", type=Path, default=ROOT / "corpus")
    parser.add_argument("--development", type=Path, default=ROOT / "corpus/prompt_development/v1/examples.jsonl")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runtime-source", type=Path, default=ROOT / "src/crack")
    parser.add_argument("--experiments", type=Path, default=ROOT / "experiments")
    args = parser.parse_args()
    extra = runtime_instruction_subjects(args.runtime_source)
    extra.extend((path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                  path.read_text(), "experiment_prompt")
                 for path in sorted(args.experiments.rglob("*.md"))
                 if "prompt" in path.name or path.name.startswith("l6_"))
    report = audit(args.prompts, args.corpus, args.development, extra_subjects=extra)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"findings", "subject_sha256"}}))
    for item in report["findings"]:
        print(f"{item['severity']}: {item['subject']} / {item['dataset']}:{item['id']} / {item['matched_text']}")
    raise SystemExit(1 if report["failures"] else 0)


if __name__ == "__main__":
    main()
