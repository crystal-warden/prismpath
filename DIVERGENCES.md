# Intentional differences from research

One line per difference the product keeps on purpose, with the reason. A promotion from research must
preserve every entry here; `tools/promote.py` merges three ways so an upstream file never overwrites
one of these by existing. Anything not listed is either identical to the adopted revision or a
difference nobody intended, which is a defect.

| Product | Research at the adopted revision | Why |
|---|---|---|
| `prismpath/kernel/ppt_compile.py`, run as `python -m prismpath.kernel.ppt_compile` | `prismpath-hw/ppt_compile.py`, a loose script beside the hardware tree | a developer must compile an image from the installed package without the hardware checkout; flags and output bytes unchanged |
| `prismpath/telemetry/canary_verify.py`, run as `python -m prismpath.telemetry.canary_verify` | `integrations/vector/canary_verify.py` | the verifier depends only on the kernel and the telemetry package; the Vector deployment files are not carried |
| `prismpath compile` withdrawn: registered, unadvertised, exits 2 with a message | builds a single file JavaScript bundle | the JavaScript engine it bundles is not carried; a call must fail clearly, not succeed misleadingly |
| `prismpath portable` text names any conformant kernel | names `portable/prismpath.mjs` | the file is not carried |
| Mission Control audit log defaults to the platform state directory | defaults to a path beside the package | site-packages is not writable after a wheel install; `MC_AUDIT` still overrides |
| Mission Control launches `sys.executable -m prismpath.orchestration.run_sprint` with the followed project as cwd | `python prismpath/run_sprint.py` from the repo root | works from an installed package; the old form only worked from a source checkout |
| `prismpath/portable/flow_fixtures.py` holds the engine fixtures | the fixtures live inside the JavaScript port's parity test | the port's test is not carried; the generator still has one fixture source |
| each crate reads corpora from its own `tests/fixtures/` | crate tests read `../prismpath/.../conformance` | a packaged crate must test itself with no Python tree beside it |
| `prismpath/tests/fixtures/kappa_dataset.jsonl` | the routing benchmark (301 cases) | the benchmark is research; the kappa code only needs a valid small dataset |
| `prismpath/tests/fixtures/alert_router.md` | `prismpath/examples/code_nodes_gemma/alert_router.md` | the example needs a local model server; the lint test needs only the flow |
| 24 tests not carried (list in `CHANGELOG.md`) | present | each tests something not carried |
| `docs/DICTIONARY.md` is the product subset | the whole Dictionary | substrate and GRC entries describe code that is not carried |
| `pyproject.toml`: readme, extras, package data, doc files, URLs | research packaging | the product is its own distribution; the comparisons extra and the JavaScript package data have no subject here |
| README, CONTRIBUTING, GETTING_STARTED, docs index, guides | research wording and links | the product is a self contained developer download; research links are pinned to the adopted revision |
| `CHANGELOG.md` separates product changes from the imported research history | one history | a reader must tell shipped product changes from research changes |
| `prismpath/hotswap/policy_host.py` commits intent, floor, evidence, then flips; recovers an interrupted commit | flips first, then persists the floor and appends the evidence | a persistence failure left a policy active that the floor and the audit log did not know about; applied to research at 7693db5 |
| `prismpath/ledgers/audit_log.py` writes and fsyncs before committing a leaf, raises `AuditWriteError`, offers `verify_persisted` | commits to memory first, silent on a failed write | an event that was never persisted must not verify as evidence; applied to research at 7693db5 |
| `prismpath/telemetry/canary_verify.py` strict identity mode (`--id-field`) | route parity only | a duplicate standing in for a lost event escaped route parity; applied to research at 7693db5 |
| `prismpath/hotswap/policy_host.py` persists the active policy (`active.ppt`, `active_policy.json`) and restores it in a new process | the active policy lives in the process that swapped | `swap attest` and the console build a fresh host and attested nothing after a real swap; applied to research, commit noted in `CHANGELOG.md` when pushed |
| `prismpath/mission_control/attest.py` reads the size limit from the settings object | reads a constant the module does not define | the model check and trail panels answered 500 on every call; applied to research |
| `prismpath/telemetry/selfheal.py` and `README.md` describe the audit log as the real Merkle primitive | call it a stub | the description was stale |
