# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
"""The lock is the review gate: a path that matches a ship rule but is not locked is unclassified, a
path under a hold rule is unclassified even when a broad ship prefix would also match, and a stale
lock entry is reported. The real manifest must classify the real tree completely."""
from pathlib import Path

from tools import product_manifest

MANIFEST = """
[meta]
adopted_revision = "0000000000000000000000000000000000000000"

[[rule]]
id = "engine"
kind = "ship"
purpose = "engine"
owner = "research"
prefix = "prismpath/"
source_prefix = "prismpath/"
reason = "everything"

[[rule]]
id = "held"
kind = "hold"
purpose = "research"
owner = "research"
prefix = "prismpath/comparisons/"
reason = "research"

[[rule]]
id = "one-file"
kind = "ship"
purpose = "docs"
owner = "product"
path = "README.md"
reason = "the readme"
"""


def _rules(tmp_path):
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(MANIFEST)
    return product_manifest.load_rules(manifest)


def test_narrow_rule_wins_over_broad_prefix(tmp_path):
    rules = _rules(tmp_path)
    assert product_manifest.classify("prismpath/kernel/engine.py", rules).identifier == "engine"
    assert product_manifest.classify("prismpath/comparisons/x.json", rules).identifier == "held"
    assert product_manifest.classify("README.md", rules).identifier == "one-file"
    assert product_manifest.classify("elsewhere.txt", rules) is None


def test_unlocked_and_held_paths_are_unclassified(tmp_path):
    rules = _rules(tmp_path)
    lock = {"prismpath/kernel/engine.py": {"path": "prismpath/kernel/engine.py", "rule": "engine", "source_path": "", "source_blob": ""}}
    paths = ["prismpath/kernel/engine.py", "prismpath/kernel/new_module.py", "prismpath/comparisons/x.json", "elsewhere.txt"]
    findings = dict(product_manifest.unclassified(paths, rules, lock))
    assert "prismpath/kernel/engine.py" not in findings
    assert "not in the lock" in findings["prismpath/kernel/new_module.py"]
    assert "hold rule held" in findings["prismpath/comparisons/x.json"]
    assert findings["elsewhere.txt"] == "no rule matches"


def test_stale_lock_entries_are_reported():
    lock = {"gone.py": {"path": "gone.py", "rule": "engine", "source_path": "", "source_blob": ""}}
    assert product_manifest.stale_lock_entries(["present.py"], lock) == ["gone.py"]


def test_lock_round_trips(tmp_path):
    lock_path = tmp_path / "manifest.lock"
    entries = {"b.py": {"path": "b.py", "rule": "engine", "source_path": "b.py", "source_blob": "abc"},
               "a.py": {"path": "a.py", "rule": "engine", "source_path": "", "source_blob": ""}}
    product_manifest.write_lock(entries, lock_path)
    assert list(product_manifest.load_lock(lock_path)) == ["a.py", "b.py"]
    assert product_manifest.load_lock(lock_path)["b.py"]["source_blob"] == "abc"


def test_the_real_tree_is_fully_classified():
    rules = product_manifest.load_rules()
    lock = product_manifest.load_lock()
    paths = product_manifest.tracked_paths()
    assert product_manifest.unclassified(paths, rules, lock) == []
    assert product_manifest.stale_lock_entries(paths, lock) == []
