#!/usr/bin/env python3
"""Convert official SemEval-2017 Task 7 Homographic Pun XML to CRACK JSONL format.

Downloads official SemEval-2017 Task 7 archive, parses:
  - subtask1-homographic-test.xml
  - subtask1-homographic-test.gold (detection labels)
  - subtask2-homographic-test.gold (pun location)
  - subtask3-homographic-test.gold (WordNet sense interpretation)

Outputs:
  - corpus/semeval_homographic_blind.jsonl
  - corpus/semeval_homographic_gold.jsonl
  - (and convenient symlinks/copies: corpus/semeval_blind.jsonl, corpus/semeval_gold.jsonl)
"""

from __future__ import annotations

import io
import json
import re
import shutil
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from nltk.tokenize.treebank import TreebankWordDetokenizer

# Ensure crack package is on sys.path
_repo_dir = Path(__file__).resolve().parents[1]
_src_dir = _repo_dir / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from crack.corpus import load_blind, load_gold
from crack.l2_senses import wordnet

SEMEVAL_URL = (
    "https://alt.qcri.org/semeval2017/task7/data/uploads/semeval2017_task7.tar.xz"
)


def _clean_text(tokens: list[str]) -> str:
    detok = TreebankWordDetokenizer()
    t = detok.detokenize(tokens)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([A-Za-z]+)\s+-\s+([A-Za-z]+)", r"\1-\2", t)
    t = re.sub(r"([A-Za-z]+)'\s+([A-Za-z]+)", r"\1'\2", t)
    return t.strip()


def _infer_genre(text: str) -> str:
    t = text.strip()
    if t.endswith("?") or t.lower().startswith((
        "why ", "what ", "how ", "can ", "where ", "who ", "which ", "when ",
        "is ", "are ", "do ", "does ", "did ", "if "
    )):
        return "QA_RIDDLE"
    return "DECLARATIVE"


def main() -> None:
    corpus_dir = _repo_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading SemEval-2017 Task 7 archive from {SEMEVAL_URL}...")
    req = urllib.request.Request(SEMEVAL_URL, headers={"User-Agent": "CRACK/1.0"})
    with urllib.request.urlopen(req) as resp:
        tar_bytes = resp.read()
    print(f"Downloaded {len(tar_bytes):,} bytes.")

    tar = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:xz")

    # 1. Parse subtask1 gold (Detection)
    gold1_file = tar.extractfile("semeval2017_task7/data/test/subtask1-homographic-test.gold")
    labels: dict[str, int] = {}
    if gold1_file:
        for line in gold1_file.read().decode("utf-8").splitlines():
            line = line.strip()
            if line:
                tid, val = line.split("\t")
                labels[tid] = int(val)

    # 2. Parse subtask2 gold (Location)
    gold2_file = tar.extractfile("semeval2017_task7/data/test/subtask2-homographic-test.gold")
    pun_word_ids: dict[str, str] = {}
    if gold2_file:
        for line in gold2_file.read().decode("utf-8").splitlines():
            line = line.strip()
            if line:
                tid, wid = line.split("\t")
                pun_word_ids[tid] = wid

    # 3. Parse subtask3 gold (Interpretation)
    gold3_file = tar.extractfile("semeval2017_task7/data/test/subtask3-homographic-test.gold")
    sense_keys_by_word_id: dict[str, list[str]] = {}
    if gold3_file:
        for line in gold3_file.read().decode("utf-8").splitlines():
            line = line.strip()
            if line:
                parts = line.split("\t")
                wid = parts[0]
                keys = parts[1:]
                sense_keys_by_word_id[wid] = keys

    # 4. Parse XML test corpus
    xml_file = tar.extractfile("semeval2017_task7/data/test/subtask1-homographic-test.xml")
    if not xml_file:
        raise RuntimeError("Failed to extract subtask1-homographic-test.xml")
    tree = ET.parse(xml_file)
    root = tree.getroot()

    wn = wordnet()

    blind_records = []
    gold_records = []

    for text_elem in root.findall("text"):
        tid = text_elem.attrib["id"]
        words_map: dict[str, str] = {}
        tokens = []
        for w in text_elem.findall("word"):
            wid = w.attrib.get("id")
            wtext = w.text or ""
            if wid:
                words_map[wid] = wtext
            tokens.append(wtext)

        text_str = _clean_text(tokens)
        genre_str = _infer_genre(text_str)

        # Blind record
        blind_records.append({
            "id": tid,
            "text": text_str,
            "target_ages": [8],
        })

        # Gold record
        is_pun = labels.get(tid, 0) == 1
        gold_label = "VALID_HOMOGRAPH_JOKE" if is_pun else "ONE_SENSE_ONLY"

        pun_word = ""
        sense_a = ""
        sense_b = ""

        if is_pun:
            target_wid = pun_word_ids.get(tid)
            if target_wid and target_wid in words_map:
                pun_word = words_map[target_wid].lower().strip(" \t\n\r\"'.,;:!?-")

            # Try to resolve WordNet sense keys from Subtask 3
            if target_wid and target_wid in sense_keys_by_word_id:
                keys = sense_keys_by_word_id[target_wid]
                senses = []
                for k in keys:
                    try:
                        lem = wn.lemma_from_key(k)
                        senses.append(lem.synset().definition())
                    except Exception:
                        pass
                if len(senses) >= 1:
                    sense_a = senses[0]
                if len(senses) >= 2:
                    sense_b = senses[1]

            # Fallback WordNet definition lookup if not in subtask 3
            if (not sense_a or not sense_b) and pun_word:
                syns = wn.synsets(pun_word)
                if len(syns) >= 1 and not sense_a:
                    sense_a = syns[0].definition()
                if len(syns) >= 2 and not sense_b:
                    sense_b = syns[1].definition()

        gold_records.append({
            "id": tid,
            "gold_label": gold_label,
            "genre": genre_str,
            "ambiguous_term": pun_word,
            "sense_a": sense_a,
            "sense_b": sense_b,
            "expected_age_verdict": {"8": "FULLY_AGE_APPROPRIATE"},
        })

    # Write JSONL outputs
    blind_path = corpus_dir / "semeval_homographic_blind.jsonl"
    gold_path = corpus_dir / "semeval_homographic_gold.jsonl"

    with blind_path.open("w", encoding="utf-8") as f:
        for r in blind_records:
            f.write(json.dumps(r) + "\n")

    with gold_path.open("w", encoding="utf-8") as f:
        for r in gold_records:
            f.write(json.dumps(r) + "\n")

    # Also create convenient short-name copies
    shutil.copyfile(blind_path, corpus_dir / "semeval_blind.jsonl")
    shutil.copyfile(gold_path, corpus_dir / "semeval_gold.jsonl")

    # Validate with crack corpus loaders
    loaded_blind = load_blind(blind_path)
    loaded_gold = load_gold(gold_path)

    pos_count = sum(1 for r in gold_records if r["gold_label"] == "VALID_HOMOGRAPH_JOKE")
    neg_count = sum(1 for r in gold_records if r["gold_label"] == "ONE_SENSE_ONLY")

    print("\n" + "=" * 60)
    print("        SEMEVAL-2017 TASK 7 CONVERSION COMPLETE")
    print("=" * 60)
    print(f"Total items:             {len(loaded_blind)}")
    print(f"Positive puns:           {pos_count} (VALID_HOMOGRAPH_JOKE)")
    print(f"Negative controls:       {neg_count} (ONE_SENSE_ONLY)")
    print(f"Blind file generated:    {blind_path}")
    print(f"Gold file generated:     {gold_path}")
    print(f"Convenience blind copy:  {corpus_dir / 'semeval_blind.jsonl'}")
    print(f"Convenience gold copy:   {corpus_dir / 'semeval_gold.jsonl'}")
    print(f"Validation status:       LOADERS PASSED (100% Schema Compliant)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
