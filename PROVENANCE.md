# Provenance

This tree is generated. It is the research repository crystal-warden/prism-path at one commit,
exported by `tools/export_clean.py`, and it is never edited by hand: a change to it is a change
to the research repository, made there and exported again.

Research commit: `3bf95260d2bdd62191c210988a0979c01a3abaab`
Research tree: `1d56c5e80274718573c7d8239967bdf3ec0f94e0`

`SHA256SUMS` holds the sha256 of every other file in this tree. Every file is the research file
of the same path byte for byte, except those that `tools/mirror/` and `tools/mirror_readme.md`
supply in research for this repository (the README, the packaging, the CI workflow, the
Dictionary subset and the product's wording of some docs), which are copied as written there. `python -m tools.provenance check`
verifies the hashes, and `python -m tools.provenance check --research PATH` also checks the tree
against a research checkout at the commit named above.
