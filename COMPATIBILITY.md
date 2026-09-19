# Compatibility

What this product adopted from research, at which revision, and what it promises about it. A check
that passes here means the product is compatible with the adopted revision. It does not mean the
product is current with research; `tools/compare_upstream.py` answers that, on request, and never as
part of a build.

## Adopted revision

Research source: crystal-warden/prism-path at commit `40a9b05b3523cb4943b583b77c6fb86f93d795ee`, adopted 2026-09-19.
Every file this product copied from research came from that commit, byte for byte, and
`PROVENANCE.md` records the source blob of each. Adopted hashes below are the hashes of the research
files at that commit. The hashes of the product's own copies, which may be edited afterwards, are in
`SHA256SUMS` and are a different thing.

## Specifications

| Document | Adopted version | Adopted sha256 | Product copy |
|---|---|---|---|
| SPEC.md, the flow format | spec version 1 (draft) | `6f17371550921258fc60325d9fb1c90bd6c0fa167593394359d594d88ecd012f` | unedited copy |
| PROTOCOL.md, the Facet wire | Facet/1 (draft) | `9e81b0421af4a29c184378c8df5dcf97c1ae99b30cf0e8cea2b88b971badb464` | unedited copy |
| TABLE_FORMAT.md, the PPT v1 image | PPT v1 | `f0561aaeef21e7494f63cf363b23d425417b904bcf655c67e69b7a6751dd017c` | not carried, [read it at the adopted revision](https://github.com/crystal-warden/prism-path/blob/40a9b05b3523cb4943b583b77c6fb86f93d795ee/prismpath-hw/TABLE_FORMAT.md) |
| docs/DICTIONARY.md, the vocabulary | as of the adopted revision | `407c44cb5a7e34de2c626bce86bb294355d8e02f87c2e7473bf2fbefc4115ee1` | product subset, meanings preserved, see below |

The supported subset: the product implements spec version 1 in Python and Rust and carries the
frozen vectors for it; the JavaScript kernel, the Go kernel, the C target, the fabric, the
microcontroller firmware and the kernel programs implement the same spec in research and are not
carried. Facet/1 is implemented in Python and Rust here. The PPT v1 image is produced by the carried
compiler and consumed by the carried pack, verify, swap and attest machinery; the substrates that
execute it are not carried.

## Formats and shared identifiers

| Item | Value | Where it is checked |
|---|---|---|
| Cause registry | sha256 `74f1b33c52f426159612c9f16e32e5f798939715fe212001b726b89ef1125ffe` over the registry, every identifier and meaning frozen | `prismpath/tests/test_causes.py` |
| Pack format | `ppt-pack/1` | `prismpath/tests/test_policy_pack.py` |
| Signing suites | the crypto agility registry | `prismpath/tests/test_crypto_registry.py`, `test_crypto_agility.py` |
| Wire framing | Facet/1 packed records, epochs, receipts | `prismpath/telemetry/tests` and `prismpath-telemetry-rs/tests` |

A shared cause identifier keeps its research meaning. The product never repurposes one to report
product only behavior; a new condition would need a new identifier, proposed to research first.

## Frozen conformance corpora

Adopted byte for byte. Each crate carries the files its tests read as byte identical copies under
`tests/fixtures/`, checked by `tools/fixture_sync.py`.

| Corpus | Adopted sha256 |
|---|---|
| `prismpath/portable/conformance/capability.json` | `aae25200a171935e0b044d5a6d30189255779416eeb2e33fa03bbf2af9f1c166` |
| `prismpath/portable/conformance/connector.json` | `e1630ab948fed8dce08588a43f70a1dbcd931c487bea54c97a04955ea25ee5e4` |
| `prismpath/portable/conformance/context.json` | `425e6bf4fe819d54b80c38c7b319324e5fc2ca42ef6fb2da84362ddfccfd0968` |
| `prismpath/portable/conformance/crypto_agility.json` | `4354755c20963f38497dbcd85b69678835403ce0fcf1ebe88e0cb16c04af589c` |
| `prismpath/portable/conformance/crypto_migration.json` | `6d333b40433256f83526909f83dd7502ddced9cfc4b91fefde6e8e7d74297b6d` |
| `prismpath/portable/conformance/durable.json` | `eed49418e33d86ca9700cd771e715a7178b65efc92b13d3c20466b9d95d84866` |
| `prismpath/portable/conformance/flows.json` | `5c294462e9ef1a0ae040791af8c9f98653f6d1bf27822947f66bd62dbe238a6f` |
| `prismpath/portable/conformance/hotswap.json` | `2ab87cc2e406accb39deb82577ddd461fd33dda87d18b95b3be70f92028afe09` |
| `prismpath/portable/conformance/level_m.json` | `58b811a0ba277b359508ca15eed690415b0e0751ccbe76037001ad967bcb8d1d` |
| `prismpath/portable/conformance/locked_flows.json` | `4da0192c4209b44b17bfddecb8edc78347093d82f876d234dd98642efc4595e6` |
| `prismpath/portable/conformance/predicates.json` | `49e17b9ceb45b25fa47b8b2ac93c7c3b3a074c8ce843276eaf9a92894a0aba7b` |
| `prismpath/portable/conformance/reach.json` | `98f00afc250f68dc8b552905236fdca221e0e4ee31bc306644c290cd017ff9d6` |
| `prismpath/portable/conformance/safety.json` | `c1a5c7e5bbe3ada30a275d9c803572497bf9c8f2a0f240a0e8aea208ef6febe1` |
| `prismpath/telemetry/conformance/boundary.json` | `47de3f16d1593a3607f7be642bd1878ec6d39f4e44f3dfc0f9e87220b144c209` |
| `prismpath/telemetry/conformance/decisions.json` | `6b68a08de7f57cdd11bee07bd256587094dc353b959d1195473c6880472479c8` |
| `prismpath/telemetry/conformance/receipts.json` | `78181a5873ed88e5cd17ccae216641a09f9ec3bd79fcc3562fc4de452c539974` |
| `prismpath/telemetry/conformance/spiral.json` | `050b031bf5c55cbf0fbd88a562ad80a58446b1466a10d1126fc974bb9a0dc444` |

Checks that run on them: `prismpath/tests/test_conformance_vectors.py` (the Python engine regenerates
`flows.json` and the predicate vectors identically), `test_level_m_conformance.py`,
`test_reach_conformance.py`, `test_capability_conformance.py`, `test_safety_vectors.py`,
`test_crypto_agility.py`, `test_crypto_migration.py`, `test_rust_conformance.py` (cross language),
the crate tests, and `prismpath/telemetry/tests` with `prismpath-telemetry-rs/tests` for the wire.

## Compiler references

`prismpath/tests/fixtures/compiler/` holds thirteen regression pairs, each an image and its names
sidecar, plus one historical image, with `SHA256SUMS` over all of them except itself.
`prismpath/tests/test_compiler_parity.py` compiles each source flow into temporary output and
compares bytes against these references. It never regenerates them.

compiler references generated 2026-09-19T16:12Z
source: crystal-warden/prism-path 40a9b05b3523cb4943b583b77c6fb86f93d795ee, materialized with git archive into scratch (prismpath/ and prismpath-hw/ppt_compile.py), never the working tree
tool: prismpath-hw/ppt_compile.py at that commit, run as: python prismpath-hw/ppt_compile.py prismpath/<flow>.md -o <stem>.ppt --json <stem>.names.json (max-steps default 25)
interpreter: Python 3.12.3, numpy 2.5.1, PYTHONDONTWRITEBYTECODE=1
determinism: each pair compiled twice, both outputs byte identical
sidecar serialization: json.dumps(dbg, indent=1) + newline, as written by ppt_compile --json; compared byte for byte
historical image: git show 40a9b05:prismpath-hw/evidence/incident_severity.ppt, sha256 314b033cd1251b6da7671cbd8a209be0b46d3babd77e254bed1b669ea4d83065, equal to the pinned recompile of gallery/incident_severity/incident_severity.md; anchored in prismpath-hw/evidence/SHA256SUMS at that commit

The thirteen pairs are regression evidence for the carried flows. They are not a proof over the
whole supported compiler domain. The historical image carries its own provenance, the research
hardware evidence manifest at the adopted revision
([`prismpath-hw/evidence/SHA256SUMS`](https://github.com/crystal-warden/prism-path/blob/40a9b05b3523cb4943b583b77c6fb86f93d795ee/prismpath-hw/evidence/SHA256SUMS)); its presence
here establishes nothing new about FPGA, microcontroller, eBPF, timing or field behavior.

## Dictionary

The product Dictionary is generated from the research Dictionary at the adopted revision by keeping
every entry whose layer is flow authoring, kernel evaluation, wire and transport, evidence and
receipts, control plane, or all, plus `image`, and dropping the substrate execution and GRC entries.
Entry text is unchanged; the preamble is the product's. A term shared with research keeps its
meaning here.

## What the research evidence does and does not cover

The research evidence ledger at the adopted revision
([`docs/research/supporting-evidence.md`](https://github.com/crystal-warden/prism-path/blob/40a9b05b3523cb4943b583b77c6fb86f93d795ee/docs/research/supporting-evidence.md)) supports
the adopted behavior of the code as it was at that commit. Once a product file is edited, only the
checks run on the shipped version speak for it: the product CI and the acceptance gates listed in
`tools/README.md`. A pinned evidence link certifies the adopted revision, not modified code.

## Running the checks

```bash
python tools/check_compatibility.py      # adopted hashes, registry, compiler references, crate fixture equality
python tools/fixture_sync.py             # crate fixtures byte equal to the product corpora
```

Both read only files in this repository. Neither needs the network or a research checkout.
