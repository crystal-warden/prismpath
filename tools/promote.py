# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
"""Promote a research change into the product: a three way integration, never an overwrite.

For every product path the lock traces to a research source, three versions exist: the research
version last adopted (the lock's source blob), the research version proposed (the same source path
at --revision), and the current product file. The tool decides per path:

- unchanged upstream: nothing to do, whatever the product did to its copy;
- changed upstream, product copy still the adopted bytes: take the upstream bytes;
- changed upstream, product copy edited: merge the two changes over the adopted base with
  git merge-file; a clean merge is written, a conflict stops the whole promotion;
- deleted upstream, product copy unedited: remove the product file; edited: a conflict for review;
- deleted in the product while upstream changed it: a conflict for review, never a merge over an
  empty file; deleted in the product while upstream left it alone: the deletion stands;
- a binary file (a NUL byte in its first 8000 bytes) that is changed upstream and edited in the
  product is a conflict for review, never a guessed merge;
- a research file under a ship rule's source prefix that no lock entry traces to is an addition; it
  is reported and never written, because adding a path is a classification decision for the lock.

The tool refuses to write on main or master, so a promotion is always staged on a review branch;
it refuses a dirty working tree, computes every decision before touching a file, applies nothing
when any conflict exists, and otherwise writes the results and stages them so `git diff --cached`
is the complete review. It never commits, never pushes, never merges to main. The lock's adopted
blobs and per path adopted revisions advance only with --update-lock and only when the promotion had
no conflict; provenance is regenerated separately, by a person, after review (tools/provenance.py).

Research is read through git plumbing on a local clone at a pinned revision; its working tree is
never read and never written.

    python -m tools.promote --research ../prism-path --revision <commit> [--rule <id>] [--dry-run] [--update-lock]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tools import product_manifest

REPO_ROOT = product_manifest.REPO_ROOT


@dataclass
class Decision:
    product_path: str
    source_path: str
    kind: str                       # unchanged, update, merge, remove, conflict, addition
    detail: str = ""
    new_blob: str | None = None
    merged: bytes | None = None


@dataclass
class Plan:
    decisions: list[Decision] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[Decision]:
        return [decision for decision in self.decisions if decision.kind == kind]


def git(repo: Path, *arguments: str, data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *arguments], input=data, capture_output=True)


def blob_at(research: Path, revision: str, path: str) -> str | None:
    completed = git(research, "rev-parse", "--verify", "--quiet", f"{revision}:{path}")
    return completed.stdout.decode().strip() if completed.returncode == 0 else None


def blob_bytes(research: Path, blob: str) -> bytes:
    completed = git(research, "cat-file", "blob", blob)
    if completed.returncode != 0:
        raise RuntimeError(f"cannot read blob {blob} from {research}")
    return completed.stdout


def product_blob(product: Path, path: str) -> str | None:
    target = product / path
    if not target.exists():
        return None
    return git(product, "hash-object", "--", path).stdout.decode().strip()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


def merge_three_ways(base: bytes, ours: bytes, theirs: bytes, label: str) -> bytes | None:
    """git merge-file over temporary files; None on conflict."""
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for name, data in (("base", base), ("ours", ours), ("theirs", theirs)):
            (directory / name).write_bytes(data)
        completed = subprocess.run(["git", "merge-file", "-p", "-L", f"product {label}", "-L", "adopted", "-L", "research",
                                    str(directory / "ours"), str(directory / "base"), str(directory / "theirs")],
                                   capture_output=True)
        if completed.returncode != 0:
            return None
        return completed.stdout


def source_additions(research: Path, revision: str, rules: list[product_manifest.Rule],
                     lock: dict[str, dict[str, str]], selected: set[str] | None) -> list[Decision]:
    traced = {entry["source_path"] for entry in lock.values() if entry["source_path"]}
    additions = []
    for rule in rules:
        if rule.kind != "ship" or not rule.source_prefix or not rule.prefix:
            continue
        if selected and rule.identifier not in selected:
            continue
        completed = git(research, "ls-tree", "-r", "--name-only", revision, "--", rule.source_prefix)
        if completed.returncode != 0:
            continue
        for source_path in completed.stdout.decode().splitlines():
            if source_path in traced:
                continue
            product_path = rule.prefix + source_path[len(rule.source_prefix):]
            holding = product_manifest.classify(product_path, rules)
            # A held destination is not an addition, a product owned area takes nothing from research
            # by path, and a path already in the lock without a source is product authored on purpose.
            if holding is None or holding.kind == "hold" or holding.owner == "product" or product_path in lock:
                continue
            additions.append(Decision(product_path, source_path, "addition",
                                      f"new under {rule.identifier}; add to tools/manifest.lock to promote"))
    return additions


def build_plan(product: Path, research: Path, revision: str, selected: set[str] | None) -> Plan:
    rules = product_manifest.load_rules(product / "tools" / "manifest.toml")
    lock = product_manifest.load_lock(product / "tools" / "manifest.lock")
    plan = Plan()
    for entry in sorted(lock.values(), key=lambda item: item["path"]):
        if not entry["source_path"]:
            continue
        if selected and entry["rule"] not in selected:
            continue
        adopted = entry["source_blob"]
        proposed = blob_at(research, revision, entry["source_path"])
        current = product_blob(product, entry["path"])
        if proposed == adopted:
            plan.decisions.append(Decision(entry["path"], entry["source_path"], "unchanged"))
            continue
        if current is None:
            # The product removed its copy. An upstream change to a file the product no longer has is
            # a decision for a person, and an upstream deletion of it changes nothing.
            kind = "unchanged" if proposed is None else "conflict"
            plan.decisions.append(Decision(entry["path"], entry["source_path"], kind,
                                           "" if proposed is None else "deleted in the product but changed upstream"))
            continue
        edited = current != adopted
        if proposed is None:
            if not edited:
                plan.decisions.append(Decision(entry["path"], entry["source_path"], "remove", "deleted upstream, product copy unedited"))
            else:
                plan.decisions.append(Decision(entry["path"], entry["source_path"], "conflict", "deleted upstream but edited in the product"))
            continue
        theirs = blob_bytes(research, proposed)
        if not edited:
            plan.decisions.append(Decision(entry["path"], entry["source_path"], "update", "changed upstream, product copy unedited", proposed, theirs))
            continue
        base = blob_bytes(research, adopted)
        ours = (product / entry["path"]).read_bytes()
        if is_binary(base) or is_binary(ours) or is_binary(theirs):
            plan.decisions.append(Decision(entry["path"], entry["source_path"], "conflict", "binary changed upstream and edited in the product"))
            continue
        merged = merge_three_ways(base, ours, theirs, entry["path"])
        if merged is None:
            plan.decisions.append(Decision(entry["path"], entry["source_path"], "conflict", "textual conflict between the product edit and the upstream change"))
        else:
            plan.decisions.append(Decision(entry["path"], entry["source_path"], "merge", "changed upstream and edited in the product, merged cleanly", proposed, merged))
    plan.decisions += source_additions(research, revision, rules, lock, selected)
    return plan


PROTECTED_BRANCHES = ("main", "master")


def current_branch(product: Path) -> str:
    return git(product, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()


def apply_plan(product: Path, plan: Plan, update_lock: bool, revision: str) -> None:
    lock = product_manifest.load_lock(product / "tools" / "manifest.lock")
    for decision in plan.decisions:
        if decision.kind in ("update", "merge"):
            target = product / decision.product_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(decision.merged or b"")
            git(product, "add", "--", decision.product_path)
            if update_lock:
                lock[decision.product_path]["source_blob"] = decision.new_blob or ""
                lock[decision.product_path]["adopted_revision"] = revision
        elif decision.kind == "remove":
            git(product, "rm", "-q", "--", decision.product_path)
            if update_lock:
                del lock[decision.product_path]
    if update_lock:
        product_manifest.write_lock(lock, product / "tools" / "manifest.lock")
        git(product, "add", "--", "tools/manifest.lock")


def report(plan: Plan) -> str:
    lines = []
    for kind in ("update", "merge", "remove", "conflict", "addition"):
        decisions = plan.of_kind(kind)
        lines.append(f"{kind}: {len(decisions)}")
        for decision in decisions:
            lines.append(f"  {decision.product_path}  ({decision.detail})")
    lines.append(f"unchanged: {len(plan.of_kind('unchanged'))}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--research", required=True, help="a local clone of the research repository")
    parser.add_argument("--revision", required=True, help="the research commit to promote from")
    parser.add_argument("--rule", action="append", help="limit to one manifest rule id; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="compute and print the plan, write nothing")
    parser.add_argument("--update-lock", action="store_true", help="advance the lock's adopted blobs for the promoted paths")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    args = parser.parse_args(argv)
    product = Path(args.repo).resolve()
    research = Path(args.research).resolve()
    if git(research, "rev-parse", "--git-dir").returncode != 0:
        print(f"promote: {research} is not a git repository", file=sys.stderr)
        return 2
    if git(research, "rev-parse", "--verify", "--quiet", f"{args.revision}^{{commit}}").returncode != 0:
        print(f"promote: revision {args.revision} does not resolve in {research}", file=sys.stderr)
        return 2
    if not args.dry_run and current_branch(product) in PROTECTED_BRANCHES:
        print(f"promote: refusing to stage on {current_branch(product)}; create a review branch first", file=sys.stderr)
        return 2
    if not args.dry_run and git(product, "status", "--porcelain").stdout.strip():
        print("promote: the product working tree is dirty; commit or stash first", file=sys.stderr)
        return 2
    plan = build_plan(product, research, args.revision, set(args.rule) if args.rule else None)
    print(report(plan))
    if plan.of_kind("conflict"):
        print("promote: conflicts need review; nothing was written", file=sys.stderr)
        return 1
    if args.dry_run:
        return 0
    full_revision = git(research, "rev-parse", f"{args.revision}^{{commit}}").stdout.decode().strip()
    apply_plan(product, plan, args.update_lock, full_revision)
    staged = git(product, "diff", "--cached", "--stat").stdout.decode()
    print(staged if staged.strip() else "nothing staged")
    print("review with: git diff --cached ; then commit on this review branch. COMPATIBILITY.md and DIVERGENCES.md are reviewed edits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
