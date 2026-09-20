# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
"""Three way promotion on two throwaway repositories: an upstream change over an unedited copy is taken,
a product edit survives an upstream change elsewhere in the file, a conflicting edit stops the whole
promotion with nothing written, an upstream deletion of an edited file is a conflict, a binary changed
on both sides is a conflict, and a new upstream file under a ship prefix is an addition that is never
written."""
import subprocess
from pathlib import Path

from tools import product_manifest, promote

MANIFEST = """
[meta]
adopted_revision = "{revision}"

[[rule]]
id = "engine"
kind = "ship"
purpose = "engine"
owner = "research"
prefix = "pkg/"
source_prefix = "src/"
reason = "the engine"

[[rule]]
id = "held"
kind = "hold"
purpose = "research"
owner = "research"
prefix = "pkg/research/"
reason = "research"

[[rule]]
id = "tools"
kind = "ship"
purpose = "tools"
owner = "product"
prefix = "tools/"
reason = "product owned"
"""


def _git(repo, *arguments, data=None):
    return subprocess.run(["git", "-C", str(repo), *arguments], input=data, capture_output=True, check=True)


def _init(repo):
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.decode().strip()


def _blob(repo, revision, path):
    return _git(repo, "rev-parse", f"{revision}:{path}").stdout.decode().strip()


def _setup(tmp_path):
    research = tmp_path / "research"
    product = tmp_path / "product"
    _init(research)
    (research / "src").mkdir()
    (research / "src" / "text.py").write_text("line one\nline two\nline three\n")
    (research / "src" / "gone.py").write_text("to be deleted\n")
    (research / "src" / "binary.bin").write_bytes(b"\x00\x01\x02")
    (research / "src" / "stable.py").write_text("stable\n")
    adopted = _commit(research, "adopted")
    _init(product)
    (product / "pkg").mkdir()
    for name in ("text.py", "gone.py", "binary.bin", "stable.py"):
        (product / "pkg" / name).write_bytes((research / "src" / name).read_bytes())
    (product / "tools").mkdir()
    (product / "tools" / "manifest.toml").write_text(MANIFEST.format(revision=adopted))
    entries = {f"pkg/{name}": {"path": f"pkg/{name}", "rule": "engine", "source_path": f"src/{name}", "source_blob": _blob(research, adopted, f"src/{name}"), "adopted_revision": adopted}
               for name in ("text.py", "gone.py", "binary.bin", "stable.py")}
    entries["tools/manifest.toml"] = {"path": "tools/manifest.toml", "rule": "tools", "source_path": "", "source_blob": "", "adopted_revision": ""}
    entries["tools/manifest.lock"] = {"path": "tools/manifest.lock", "rule": "tools", "source_path": "", "source_blob": "", "adopted_revision": ""}
    product_manifest.write_lock(entries, product / "tools" / "manifest.lock")
    _commit(product, "seed")
    # promotions are staged on a review branch, never on the default branch
    _git(product, "checkout", "-q", "-b", "promote/review")
    return research, product, adopted


def test_update_merge_addition_and_lock_advance(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (product / "pkg" / "text.py").write_text("line one\nline two\nline three\nproduct line\n")
    _commit(product, "product edit at the end")
    (research / "src" / "text.py").write_text("research line\nline one\nline two\nline three\n")
    (research / "src" / "stable.py").write_text("stable, changed upstream\n")
    (research / "src" / "new_module.py").write_text("new\n")
    (research / "src" / "research" ).mkdir()
    (research / "src" / "research" / "held.py").write_text("held\n")
    proposed = _commit(research, "upstream changes")
    plan = promote.build_plan(product, research, proposed, None)
    kinds = {decision.product_path: decision.kind for decision in plan.decisions}
    assert kinds["pkg/text.py"] == "merge"
    assert kinds["pkg/stable.py"] == "update"
    assert kinds["pkg/gone.py"] == "unchanged" and kinds["pkg/binary.bin"] == "unchanged"
    assert kinds["pkg/new_module.py"] == "addition"
    assert "pkg/research/held.py" not in kinds
    promote.apply_plan(product, plan, update_lock=True, revision=proposed)
    merged = (product / "pkg" / "text.py").read_text()
    assert merged == "research line\nline one\nline two\nline three\nproduct line\n"
    assert (product / "pkg" / "stable.py").read_text() == "stable, changed upstream\n"
    assert not (product / "pkg" / "new_module.py").exists()
    lock = product_manifest.load_lock(product / "tools" / "manifest.lock")
    assert lock["pkg/text.py"]["source_blob"] == _blob(research, proposed, "src/text.py")
    assert lock["pkg/stable.py"]["source_blob"] == _blob(research, proposed, "src/stable.py")
    assert lock["pkg/text.py"]["adopted_revision"] == proposed and lock["pkg/stable.py"]["adopted_revision"] == proposed
    assert lock["pkg/gone.py"]["adopted_revision"] == adopted, "an untouched path keeps the revision it was adopted from"
    staged = _git(product, "diff", "--cached", "--name-only").stdout.decode().split()
    assert "pkg/text.py" in staged and "pkg/stable.py" in staged and "tools/manifest.lock" in staged


def test_conflicts_stop_everything_and_write_nothing(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (product / "pkg" / "text.py").write_text("line one\nproduct two\nline three\n")
    (product / "pkg" / "gone.py").write_text("edited before upstream deleted it\n")
    (product / "pkg" / "binary.bin").write_bytes(b"\x00\x09\x02")
    _commit(product, "product edits")
    (research / "src" / "text.py").write_text("line one\nresearch two\nline three\n")
    (research / "src" / "gone.py").unlink()
    (research / "src" / "binary.bin").write_bytes(b"\x00\x01\x07")
    (research / "src" / "stable.py").write_text("changed upstream\n")
    proposed = _commit(research, "conflicting upstream")
    plan = promote.build_plan(product, research, proposed, None)
    kinds = {decision.product_path: decision.kind for decision in plan.decisions}
    assert kinds["pkg/text.py"] == "conflict"
    assert kinds["pkg/gone.py"] == "conflict"
    assert kinds["pkg/binary.bin"] == "conflict"
    assert kinds["pkg/stable.py"] == "update"
    code = promote.main(["--research", str(research), "--revision", proposed, "--repo", str(product)])
    assert code == 1
    assert (product / "pkg" / "stable.py").read_text() == "stable\n", "a conflict elsewhere must leave every file untouched"
    assert not _git(product, "diff", "--cached", "--name-only").stdout.strip()


def test_removal_of_an_unedited_file(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (research / "src" / "gone.py").unlink()
    proposed = _commit(research, "delete upstream")
    plan = promote.build_plan(product, research, proposed, None)
    kinds = {decision.product_path: decision.kind for decision in plan.decisions}
    assert kinds["pkg/gone.py"] == "remove"
    promote.apply_plan(product, plan, update_lock=True, revision=proposed)
    assert not (product / "pkg" / "gone.py").exists()
    assert "pkg/gone.py" not in product_manifest.load_lock(product / "tools" / "manifest.lock")


def test_dirty_tree_and_bad_inputs_are_refused(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (product / "pkg" / "text.py").write_text("uncommitted\n")
    assert promote.main(["--research", str(research), "--revision", adopted, "--repo", str(product)]) == 2
    assert promote.main(["--research", str(tmp_path / "nowhere"), "--revision", adopted, "--repo", str(product)]) == 2
    assert promote.main(["--research", str(research), "--revision", "no-such-ref", "--repo", str(product)]) == 2


def test_product_deletion_is_a_conflict_when_upstream_changed_and_stands_otherwise(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (product / "pkg" / "text.py").unlink()
    (product / "pkg" / "stable.py").unlink()
    _commit(product, "product deleted two files")
    (research / "src" / "text.py").write_text("")
    proposed = _commit(research, "upstream emptied text.py, left stable.py alone")
    plan = promote.build_plan(product, research, proposed, None)
    kinds = {decision.product_path: decision.kind for decision in plan.decisions}
    assert kinds["pkg/text.py"] == "conflict", "an upstream change to a file the product deleted is a review decision, not a merge over nothing"
    assert kinds["pkg/stable.py"] == "unchanged", "the product's deletion stands when upstream did not touch the file"


def test_promotion_refuses_the_default_branch(tmp_path):
    research, product, adopted = _setup(tmp_path)
    (research / "src" / "stable.py").write_text("changed\n")
    proposed = _commit(research, "upstream change")
    default_branch = _git(product, "rev-list", "--max-parents=0", "--format=%D", "HEAD").stdout.decode()
    _git(product, "checkout", "-q", "-")
    assert promote.current_branch(product) in promote.PROTECTED_BRANCHES
    assert promote.main(["--research", str(research), "--revision", proposed, "--repo", str(product)]) == 2
    assert (product / "pkg" / "stable.py").read_text() == "stable\n"
    assert promote.main(["--research", str(research), "--revision", proposed, "--repo", str(product), "--dry-run"]) == 0
    _git(product, "checkout", "-q", "promote/review")
    assert promote.main(["--research", str(research), "--revision", proposed, "--repo", str(product)]) == 0
    assert (product / "pkg" / "stable.py").read_text() == "changed\n"

