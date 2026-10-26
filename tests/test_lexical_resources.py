"""Resource provenance, failed downloads, and cross-inventory count integrity."""
import hashlib
import json
import runpy
from pathlib import Path

import pytest

from crack import lexical_resources as resources
from crack.l2_senses import _legacy_wordnet, wordnet
from crack.phonetics.lexicon import _parse_cmu


def test_current_inventory_and_historical_counts_are_separate():
    current, historical = wordnet(), _legacy_wordnet()
    assert current.get_version() == "2025"
    assert historical.get_version() == "3.0"
    assert current.synsets("covid-19") and not historical.synsets("covid-19")
    animal = next(s for s in current.synsets("cat") if s.lexname() == "noun.animal")
    lemma = next(l for l in animal.lemmas() if l.name() == "cat")
    assert lemma.count() == historical.lemma_from_key(lemma.key()).count()
    # The name cat.n.01 changed meaning. Counts must not be joined by that name.
    assert current.synset("cat.n.01").lexname() != historical.synset("cat.n.01").lexname()


def test_official_parser_preserves_variants_and_excludes_comments():
    text = "word W ER1 D # comment\nword(2) W AO1 R D\n;;; header\n"
    assert _parse_cmu(text) == {"word": [["W", "ER1", "D"], ["W", "AO1", "R", "D"]]}


def test_modified_data_is_rejected_without_network(monkeypatch, tmp_path):
    directory = tmp_path / "cmudict"
    directory.mkdir()
    (directory / "cmudict.dict").write_text("modified")
    monkeypatch.setattr(resources, "CACHE_DIR", tmp_path)
    resources.resource_directory.cache_clear()
    try:
        with pytest.raises(LookupError, match="Missing or modified"):
            resources.resource_directory("cmudict")
    finally:
        resources.resource_directory.cache_clear()


def test_bad_download_does_not_install_partial_data(monkeypatch, tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/fetch_lexical_resources.py"
    install = runpy.run_path(str(script))["install_resource"]
    monkeypatch.setitem(install.__globals__, "CACHE_DIR", tmp_path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        install("cmudict", b"invalid download")
    assert list(tmp_path.iterdir()) == []


def test_resume_rejects_different_resource_provenance(tmp_path):
    from crack.config import DEFAULT_SETTINGS
    from crack.runner import _check_resume_fingerprint, _run_fingerprint

    blind = tmp_path / "blind.jsonl"
    blind.write_text("{}\n")
    frozen = _run_fingerprint(blind, DEFAULT_SETTINGS)
    assert frozen["lexical_resources"]["resources"]["oewn"]["version"] == "2025"
    assert "resource_data/manifest.json" in frozen["source_sha256"]
    metadata = json.loads(json.dumps(frozen))
    metadata["lexical_resources"]["phonetic_calibration_sha256"] = "0" * 64
    (tmp_path / "run_meta.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="lexical resources"):
        _check_resume_fingerprint(tmp_path / "records.jsonl", frozen)


def test_reference_category_file_is_integrity_checked():
    root = resources.resource_directory("oewn")
    assert resources.sha256(root / "lexnames") == hashlib.sha256(
        (resources.RESOURCE_DATA / "lexnames.txt").read_bytes()
    ).hexdigest()


def test_calibration_cannot_silently_use_an_old_lexicon(monkeypatch, tmp_path):
    from crack.phonetics import calibration

    path = tmp_path / "calibration.json"
    path.write_text(json.dumps({"lexicon_version": "old", "lexicon_sha256": "old"}))
    monkeypatch.setattr(calibration, "CALIBRATION_PATH", path)
    calibration.calibration_table.cache_clear()
    try:
        with pytest.raises(ValueError, match="different lexicon"):
            calibration.calibration_table()
    finally:
        calibration.calibration_table.cache_clear()
