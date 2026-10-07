import json
import re

import pytest

from pgw.manifest import ROOT, check_frozen, freeze_record, script_hashes, sha256_lf, versions, write_manifest


def test_hash_ignores_crlf(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(b"x = 1\ny = 2\n")
    b.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert sha256_lf(a) == sha256_lf(b)


def test_check_frozen_names_changed_added_and_deleted_scripts(tmp_path):
    (tmp_path / "pgw").mkdir()
    (tmp_path / "pgw" / "x.py").write_text("A = 1\n", encoding="utf-8")
    frozen = tmp_path / "FROZEN.json"
    frozen.write_text(json.dumps(freeze_record(tmp_path)), encoding="utf-8")
    assert check_frozen(frozen, tmp_path) == []
    (tmp_path / "pgw" / "x.py").write_text("A = 2\n", encoding="utf-8")
    (tmp_path / "pgw" / "y.py").write_text("B = 1\n", encoding="utf-8")
    assert check_frozen(frozen, tmp_path) == ["pgw/x.py", "pgw/y.py"]
    (tmp_path / "pgw" / "x.py").unlink()
    assert check_frozen(frozen, tmp_path) == ["pgw/x.py", "pgw/y.py"]


def test_a_malformed_freeze_record_fails_closed(tmp_path):
    f = tmp_path / "FROZEN.json"
    for bad in ({}, [], {"scripts": {"pgw/x.py": None}, "versions": {"python": "3"}},
                {"scripts": {}, "versions": {}}, {"pgw/x.py": "0" * 64}):
        f.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            check_frozen(f, tmp_path)


def test_dependency_drift_is_a_mismatch(tmp_path):
    (tmp_path / "pgw").mkdir()
    (tmp_path / "pgw" / "x.py").write_text("A = 1\n", encoding="utf-8")
    record = freeze_record(tmp_path)
    record["versions"]["spacy"] = "0.0.0"
    f = tmp_path / "FROZEN.json"
    f.write_text(json.dumps(record), encoding="utf-8")
    assert check_frozen(f, tmp_path) == ["version:spacy"]


def test_write_manifest_never_overwrites_or_clobbers(tmp_path):
    p = tmp_path / "m.json"
    write_manifest(p, seed=1)
    with pytest.raises(FileExistsError):
        write_manifest(p, seed=1)
    with pytest.raises(ValueError):
        write_manifest(tmp_path / "n.json", versions={})


def test_installed_versions_match_the_lock():
    v = versions()
    assert v["presidio-analyzer"] == "2.2.364" and v["presidio-anonymizer"] == "2.2.364"
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    m = re.search(r"en_core_web_lg-(\d+\.\d+\.\d+)", lock)
    assert m, "requirements.lock does not record the spaCy model"
    assert v["en-core-web-lg"] == m.group(1)


def test_versions_record_regex_as_locked():
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    m = re.search(r"^regex==(\S+)$", lock, re.MULTILINE)
    assert m, "requirements.lock does not record regex"
    assert versions()["regex"] == m.group(1)
