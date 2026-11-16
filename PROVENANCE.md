# Provenance

This tree is generated. It is the research repository crystal-warden/prism-path at one commit,
exported by `tools/export_clean.py`, and it is never edited by hand: a change to it is a change
to the research repository, made there and exported again.

Research commit: `48c8e74b966579c8cfb8e50c86e4ee9c88310885`
Research tree: `f619bd57b1f38c98abb20b33cbf99e1f4f00a0ea`

`SHA256SUMS` holds the sha256 of every other file in this tree. Every file is the research file
of the same path byte for byte, except those that `tools/mirror/` and `tools/mirror_readme.md`
supply in research for this repository (the README, the packaging, the CI workflow, the
Dictionary subset and the product's wording of some docs), which are copied as written there. `python -m tools.provenance check`
verifies the hashes, and `python -m tools.provenance check --research PATH` also checks the tree
against a research checkout at the commit named above.
