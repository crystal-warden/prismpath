# The maintenance tools

This directory is the small system that keeps the product compatible with the research revision it
adopted and lets research changes in only by review. Every tool reads files in this repository, none
pushes, none merges, none publishes.

| Tool | What it is for |
|---|---|
| `manifest.toml` | the rules: what may be in the product (`ship`) and what never enters (`hold`), each with a purpose, an owner and a reason |
| `manifest.lock` | every classified path with its rule, its research source path, the source blob and the research revision it was last adopted from; the review gate for new paths |
| `product_manifest.py` | loads both; `check` fails on any tracked path that is unclassified or unlocked, `update-lock` adds new paths under their rule |
| `provenance.py` | writes `PROVENANCE.md` and `SHA256SUMS` from the tracked tree and defines the tree digest; `check` recomputes and compares |
| `check_compatibility.py` | adopted corpus hashes, the cause registry, the frozen compiler references recompiled into temporary output, crate fixture equality |
| `check_boundary.py` | no held path present, no dangling local link, research links pinned to a commit; with `--wheel` or `--sdist`, the same over a built artifact plus the required members |
| `fixture_sync.py` | each crate's `tests/fixtures` corpora byte identical to the product corpora |
| `compare_upstream.py` | on request only: what changed in research since the adopted revision, per rule, and which product copies were edited; a report, never a build step |
| `promote.py` | a three way integration of one research revision into the product; stages the result for `git diff --cached`, stops on conflicts, never commits |
| `acceptance.sh` | the acceptance gates, run from an exported copy of the tree outside any checkout; `--leg full`, `python`, or `rust`; refuses any other leg and fails when a defined gate recorded no status |
| `release_policy.md` | a PrismPath flow, every edge deterministic, that decides release eligibility over the acceptance facts: eligible, refused, or missing evidence |
| `release_eligibility.py` | runs the flow over an acceptance output directory and writes `release_receipt.json`, bound to the revision, the artifact hashes, the policy flow and image hashes and the report hashes, appended to a Merkle committed `release_receipts.log`; advisory during adoption, the script's exit status decides |
| `tests/` | the repository maintenance suite for the tools above; needs the source tree |

## The suites, selected explicitly

| Suite | Command | Needs |
|---|---|---|
| Product runtime | `python -m pytest --pyargs prismpath.tests prismpath.telemetry.tests -m "not cross_language"` | the installed package, numpy; the signing and control-plane extras and git to run every case |
| Cross language | `python -m pytest --pyargs prismpath.tests -m cross_language` | cargo and rustc on the PATH, and the crate sources; runs only in the combined gate |
| Crates | `cargo test --workspace` and `cargo clippy --workspace --all-targets -- -D warnings` | the Rust toolchain; no Python |
| Repository maintenance | `python -m pytest tools/tests` | the source tree and git |
| Compatibility | `python -m tools.check_compatibility` | the source tree or the installed package; no network |
| Boundary | `python -m tools.check_boundary` | the source tree |

The product runtime suite ships in the wheel. Cases that need an optional extra skip with a stated
reason when it is absent; the acceptance run installs the extras and treats any other skip as a
failure. The skips that remain legitimate, by test and reason, are listed in the acceptance report.

## Promotion, only on request

1. Compare first: `python -m tools.compare_upstream --research ../prism-path --revision <commit>`.
   Read what changed, what the product had edited, and what research added under a shipped prefix.
2. Additions are classification decisions: add each wanted path to `manifest.lock` under its rule,
   with its source path, in a reviewed commit. A held path never enters; a path nobody adds does not.
3. On a clean tree and a review branch (the tool refuses main and master),
   `python -m tools.promote --research ../prism-path --revision <commit> --update-lock`.
   The tool takes upstream changes over unedited copies, merges three ways where the product had
   edited, removes what upstream deleted and the product had not touched, treats a file the product
   deleted and upstream changed as a conflict, and stops with nothing written if any file conflicts. Review the staged diff, resolve conflicts by hand where it stopped,
   and commit on a review branch.
4. The lock now records the promoted revision on each promoted path; `manifest.toml` keeps the seed
   revision. Update `COMPATIBILITY.md` in the same review, and update
   `DIVERGENCES.md` for every difference kept on purpose, then `python -m tools.provenance write`.
5. Run `acceptance.sh --leg full`. The pull request carries the report.

Nothing flows the other way by itself. A product fix research would also want is proposed there as
its own change. A research ledger update is not a promotion trigger.

## What the checksums are

`SHA256SUMS` and the tree digest in `PROVENANCE.md` let two trees be compared and let a hand edit be
noticed. They are not signatures and prove nothing about who produced the tree.
