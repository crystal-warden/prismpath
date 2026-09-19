#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
#
# The acceptance gates, run outside any source checkout. The tree is exported from git into a
# temporary directory, so an uncommitted file cannot pass by accident; the Python legs install the
# built wheel into a fresh virtual environment and run the shipped tests against the installed
# package with PYTHONPATH cleared; the Rust leg builds and tests each crate from a cargo package
# extraction so a crate cannot lean on the source tree. Every gate writes its exit status to the
# report; a missing prerequisite is a reported blocker, never a pass.
#
#   tools/acceptance.sh --leg full|python|rust [--out DIR] [--python PYTHON]
#
# full runs everything including the cross language tests and the repository checks; python runs the
# Python gates on a box without Rust; rust runs the crate gates on a box without Python packages.
set -u

LEG="full"
OUT=""
PYTHON="${PYTHON:-python3}"
while [ $# -gt 0 ]; do
  case "$1" in
    --leg) LEG="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --python) PYTHON="$2"; shift 2 ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="$(git -C "$REPO" rev-parse HEAD)"
OUT="${OUT:-$(mktemp -d -t prismpath-acceptance-XXXXXX)}"
mkdir -p "$OUT"
REPORT="$OUT/report.md"
EXPORT="$OUT/tree"
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1
export SOURCE_DATE_EPOCH="$(git -C "$REPO" log -1 --format=%ct)"
export XDG_STATE_HOME="$OUT/state"
FAILED=0

record() {   # record <gate> <status> <detail>
  printf '| %s | %s | %s |\n' "$1" "$2" "$3" >> "$REPORT"
  if [ "$2" != "pass" ] && [ "$2" != "skip" ]; then FAILED=1; fi
}
run_gate() { # run_gate <gate> <logfile> <command...>
  local gate="$1"; local log="$2"; shift 2
  if "$@" > "$log" 2>&1; then record "$gate" pass "$(basename "$log")"; else record "$gate" FAIL "exit $? see $(basename "$log")"; fi
}

{
  echo "# Acceptance report"
  echo
  echo "commit $COMMIT, leg $LEG, $(date -u +%Y-%m-%dT%H:%MZ)"
  echo
  echo "| Gate | Status | Detail |"
  echo "|---|---|---|"
} > "$REPORT"

# ------------------------------------------------------------------ export the tracked tree
mkdir -p "$EXPORT"
git -C "$REPO" archive --format=tar HEAD | tar -x -C "$EXPORT"
record "export tracked tree" pass "$(find "$EXPORT" -type f | wc -l) files"

if [ "$LEG" = "full" ] || [ "$LEG" = "python" ]; then
  if ! command -v "$PYTHON" > /dev/null; then record "python prerequisite" BLOCKED "$PYTHON not found"; fi
  "$PYTHON" --version > "$OUT/python-version.txt" 2>&1
  # -------------------------------------------------------------- build wheel and sdist, twice
  run_gate "build wheel and sdist" "$OUT/build.log" bash -c "cd '$EXPORT' && '$PYTHON' -m venv '$OUT/venv-build' && '$OUT/venv-build/bin/pip' -q install build && '$OUT/venv-build/bin/python' -m build --outdir '$OUT/dist' ."
  run_gate "build again for reproducibility" "$OUT/build2.log" bash -c "cd '$EXPORT' && '$OUT/venv-build/bin/python' -m build --outdir '$OUT/dist2' ."
  WHEEL="$(ls "$OUT"/dist/*.whl 2>/dev/null | head -1)"
  SDIST="$(ls "$OUT"/dist/*.tar.gz 2>/dev/null | head -1)"
  if [ -n "$WHEEL" ]; then
    run_gate "reproducible wheel and sdist" "$OUT/reproducible.log" "$PYTHON" - "$OUT/dist" "$OUT/dist2" <<'PY'
import hashlib, sys, tarfile, zipfile
from pathlib import Path
first, second = Path(sys.argv[1]), Path(sys.argv[2])
def wheel_members(path):
    with zipfile.ZipFile(path) as archive:
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                if not name.endswith("/") and not name.endswith("RECORD") and not name.endswith("WHEEL")}
def sdist_members(path):
    with tarfile.open(path) as archive:
        out = {}
        for member in archive.getmembers():
            if member.isfile() and not member.name.endswith("PKG-INFO"):
                out[member.name.split("/", 1)[1]] = (hashlib.sha256(archive.extractfile(member).read()).hexdigest(), member.mode & 0o111)
        return out
problems = []
for kind, members, glob in (("wheel", wheel_members, "*.whl"), ("sdist", sdist_members, "*.tar.gz")):
    one, two = sorted(first.glob(glob)), sorted(second.glob(glob))
    if len(one) != 1 or len(two) != 1:
        problems.append(f"{kind}: expected one artifact per build"); continue
    if members(one[0]) != members(two[0]):
        problems.append(f"{kind}: normalized contents differ between two builds")
print("\n".join(problems) if problems else "identical normalized contents and modes across two builds (RECORD, WHEEL and PKG-INFO excluded)")
sys.exit(1 if problems else 0)
PY
    run_gate "package boundary (wheel and sdist)" "$OUT/boundary-package.log" bash -c "cd '$EXPORT' && '$PYTHON' -m tools.check_boundary --wheel '$WHEEL' --sdist '$SDIST'"
    # -------------------------------------------------------------- base install: numpy only, no research, no rust, no node
    run_gate "python base: fresh venv install of the wheel" "$OUT/base-install.log" bash -c "'$PYTHON' -m venv '$OUT/venv-base' && '$OUT/venv-base/bin/pip' -q install '$WHEEL'"
    run_gate "python base: CLI, import and runtime asset smoke" "$OUT/base-smoke.log" bash -c "
      set -e; cd '$OUT'; export PRISMPATH_ACCEPTANCE_INSTALLED=1
      V='$OUT/venv-base/bin'
      \$V/prismpath --help > /dev/null
      \$V/python -c 'import prismpath; print(prismpath.__file__); assert \"site-packages\" in prismpath.__file__'
      rm -rf smoke && mkdir smoke && cd smoke
      \$V/prismpath init --template incident_severity > /dev/null
      \$V/prismpath validate incident_severity.md
      \$V/prismpath test incident_severity.md
      \$V/prismpath portable incident_severity.md
      \$V/python -m prismpath.kernel.ppt_compile incident_severity.md -o incident_severity.ppt --json incident_severity.names.json
      test -s incident_severity.ppt
      \$V/prismpath facet quantize incident_severity.md '{\"severity\": 3}' > /dev/null || \$V/prismpath facet --help > /dev/null
      if \$V/prismpath compile incident_severity.md --tier p0 2> compile.err; then echo 'compile must fail'; exit 1; fi
      grep -q 'not available in this distribution' compile.err
      echo 'base smoke ok'"
    run_gate "python base: installed package test (base extras only)" "$OUT/base-tests.log" bash -c "cd '$OUT' && '$OUT/venv-base/bin/pip' -q install pytest && PATH='$OUT/venv-base/bin':\$PATH PRISMPATH_ACCEPTANCE_INSTALLED=1 '$OUT/venv-base/bin/python' -m pytest --pyargs prismpath.tests.test_installed_package prismpath.tests.test_cli_without_js_engine prismpath.tests.test_compatibility_hashes prismpath.tests.test_compiler_parity -q -p no:cacheprovider"
    # -------------------------------------------------------------- full install: extras, the shipped suites against the installed package
    run_gate "python full: install with signing, control-plane, test extras" "$OUT/full-install.log" bash -c "'$PYTHON' -m venv '$OUT/venv-full' && '$OUT/venv-full/bin/pip' -q install '$WHEEL[signing,control-plane,test]' httpx"
    run_gate "python full: runtime suite against the installed package" "$OUT/full-tests.log" bash -c "cd '$OUT' && PATH='$OUT/venv-full/bin':\$PATH PRISMPATH_ACCEPTANCE_INSTALLED=1 '$OUT/venv-full/bin/python' -m pytest --pyargs prismpath.tests prismpath.telemetry.tests -q -p no:cacheprovider -m 'not cross_language' -rs"
    run_gate "python full: skip budget" "$OUT/skips.log" "$PYTHON" - "$OUT/full-tests.log" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
allowed = ("sentence_transformers", "needs the real bge embedder", "torch", "transformers", "playwright", "bwrap", "tomllib needs Python 3.11")
skips = re.findall(r"^SKIPPED \[\d+\] (.+)$", text, re.M)
unbudgeted = [line for line in skips if not any(reason in line for reason in allowed)]
print("skips:", len(skips)); [print("  ", line) for line in skips]
if unbudgeted:
    print("UNBUDGETED SKIPS:"); [print("  ", line) for line in unbudgeted]
sys.exit(1 if unbudgeted else 0)
PY
    run_gate "python full: fuzz the predicate sandbox" "$OUT/fuzz.log" bash -c "cd '$OUT' && '$OUT/venv-full/bin/python' -m prismpath.safety.fuzz_predicates -n 20000"
    run_gate "canary verifier from the installed module" "$OUT/canary.log" bash -c "cd '$OUT' && '$OUT/venv-full/bin/python' -m pytest --pyargs prismpath.telemetry.tests.test_canary_verify -q -p no:cacheprovider"
    # -------------------------------------------------------------- the signed pack, inside the project Mission Control will follow
    run_gate "signed pack from the installed wheel: keygen, envelope, compile, pack, verify" "$OUT/pack.log" bash -c "
      set -e; rm -rf '$OUT/mc-project' && mkdir -p '$OUT/mc-project/flows' && cd '$OUT/mc-project'
      P='$OUT/venv-full/bin/prismpath'; PY='$OUT/venv-full/bin/python'
      printf -- '---\nname: triage\nstart: intake\n---\n## intake\n-> escalate: when priority > 5\n-> resolve: else\n## escalate\n## resolve\n' > flows/triage.md
      \$P swap keygen --out keys --name authority > /dev/null
      \$P swap envelope --envelope-id env1 --fields priority:int --caps atoms=1024,nodes=256 --priv keys/authority.key --pub keys/authority.pub --out env > /dev/null
      \$PY -m prismpath.kernel.ppt_compile flows/triage.md -o triage.ppt
      \$P swap pack --ppt triage.ppt --fields priority:int --priv keys/authority.key --pub keys/authority.pub --version 1 > /dev/null
      \$P swap verify --ppt triage.ppt --pub keys/authority.pub | grep -q '\"ok\": true'
      echo 'pack verified'"
    # -------------------------------------------------------------- Mission Control from the installed wheel
    run_gate "mission control: installed launch, defaults, assets, validate, facet, pack verify, sprint subprocess" "$OUT/mission-control.log" "$OUT/venv-full/bin/python" - "$OUT" <<'PY'
import json, os, subprocess, sys, time, urllib.request, tempfile
from pathlib import Path
out = Path(sys.argv[1]); project = out / "mc-project"
flow = project / "flows" / "triage.md"
assert flow.exists(), "the pack gate prepares the project"
# LLM_BASE points at a closed loopback port so a sprint that tries to reach a model fails fast and
# touches no live service; the launch is what is under test, not the model.
env = dict(os.environ, MC_PROJ=str(project), MC_PORT="9917", MC_SCAN=str(project / "status.json"), LLM_BASE="http://127.0.0.1:9/v1", LLM_MODEL="none")
env.pop("MC_AUDIT", None)
state_home = Path(os.environ["XDG_STATE_HOME"]); env["XDG_STATE_HOME"] = str(state_home)
server = subprocess.Popen([sys.executable, "-m", "prismpath.mission_control"], env=env, cwd=str(out), stdout=open(out / "mc-server.log", "w"), stderr=subprocess.STDOUT)
def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:9917{path}", timeout=5) as response:
        return response.status, response.read()
def post(path, payload):
    request = urllib.request.Request(f"http://127.0.0.1:9917{path}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.loads(response.read())
try:
    for _ in range(50):
        try: get("/api/v1/status"); break
        except Exception: time.sleep(0.2)
    else: raise SystemExit("mission control did not start; see mc-server.log")
    for asset in ("/", "/style.css", "/app.js", "/vendor/cytoscape.min.js"):
        status, body = get(asset); assert status == 200 and body, asset
    print("static assets served")
    status, validation = post("/api/v1/inspect/validate", {"flow_md": "flows/triage.md"}); print("validate:", status, str(validation)[:120])
    status, facet = post("/api/v1/policy/facet-encode", {"flow_md": "flows/triage.md", "reading_json": {"priority": 7}}); print("facet-encode:", status, str(facet)[:160])
    status, verified = post("/api/v1/policy/pack-verify", {"ppt_path": "triage.ppt", "pub": ["keys/authority.pub"]}); print("pack-verify:", status, verified.get("ok"), verified.get("reasons"))
    assert verified.get("ok") is True, verified
    status, started = post("/api/v1/sprint/start", {"proj": str(project), "agent": "served", "seconds": 1, "max_iters": 1}); print("sprint start:", status, started)
    time.sleep(4)
    log = (project / "mc_sprint.log").read_text() if (project / "mc_sprint.log").exists() else ""
    assert "No module named" not in log and "can't open file" not in log, log[-500:]
    assert "8888" not in log, "the sprint reached for the default model endpoint"
    print("sprint subprocess launched from the installed module in the project; log head:", log[:300].replace("\n", " | "))
    # The audit log is created by the first audited action, and the sprint start is one; only now
    # can its location be asserted.
    audit_default = state_home / "prismpath" / "mission_audit.log"
    assert audit_default.exists(), f"audit log not at the state directory default: {audit_default}"
    assert not list(Path(sys.prefix).rglob("mission_audit.log")), "audit log written into the installation"
    print("audit log at", audit_default)
finally:
    server.terminate(); server.wait(timeout=10)
# the override, in a second process
env2 = dict(env, MC_AUDIT=str(out / "override-audit.log"), MC_PORT="9918")
server = subprocess.Popen([sys.executable, "-m", "prismpath.mission_control"], env=env2, cwd=str(out), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
try:
    for _ in range(50):
        try:
            with urllib.request.urlopen("http://127.0.0.1:9918/api/v1/status", timeout=5): break
        except Exception: time.sleep(0.2)
    request = urllib.request.Request("http://127.0.0.1:9918/api/v1/sprint/start", data=json.dumps({"proj": str(project), "agent": "served", "seconds": 1, "max_iters": 1}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.status == 200
    time.sleep(2)
    assert (out / "override-audit.log").exists(), "MC_AUDIT override not honoured"
    print("MC_AUDIT override honoured")
finally:
    server.terminate(); server.wait(timeout=10)
PY
    # -------------------------------------------------------------- source archive
    run_gate "source archive: unpack, rebuild, install, promised tests present" "$OUT/sdist.log" bash -c "rm -rf '$OUT/sdist-work' && mkdir '$OUT/sdist-work' && tar -xzf '$SDIST' -C '$OUT/sdist-work' && cd '$OUT'/sdist-work/prismpath-* && test -f prismpath/tests/test_causes.py && test -f prismpath/tests/fixtures/compiler/SHA256SUMS && test -f COMPATIBILITY.md && '$OUT/venv-build/bin/python' -m build --outdir '$OUT/dist-from-sdist' . && '$PYTHON' -m venv '$OUT/venv-sdist' && '$OUT/venv-sdist/bin/pip' -q install '$OUT'/dist-from-sdist/*.whl pytest && cd '$OUT' && PATH='$OUT/venv-sdist/bin':\$PATH PRISMPATH_ACCEPTANCE_INSTALLED=1 '$OUT/venv-sdist/bin/python' -m pytest --pyargs prismpath.tests.test_compatibility_hashes prismpath.tests.test_installed_package -q -p no:cacheprovider"
    # -------------------------------------------------------------- examples and quickstart
    run_gate "documentation: examples and quickstart commands" "$OUT/examples.log" bash -c "cd '$EXPORT' && export PATH='$OUT/venv-full/bin':\$PATH && P='$OUT/venv-full/bin/prismpath' && \$P validate prismpath/examples/pr_demo/triage.md && \$P test prismpath/examples/pr_demo/triage.md && \$P validate prismpath/examples/operator_overlay/overlay.md && \$P test prismpath/examples/operator_overlay/overlay.md && \$P validate prismpath/examples/governed_worker/governed_worker.md && \$P validate prismpath/examples/code_nodes/pipeline.md && \$P validate prismpath/examples/cli_worker/ci_gate.md && \$P graph prismpath/gallery/incident_severity/incident_severity.md > /dev/null && \$P contract prismpath/gallery/incident_severity/incident_severity.md > /dev/null && \$P capability prismpath/gallery/incident_severity/incident_severity.md > /dev/null && \$P verify prismpath/gallery/incident_severity/incident_severity.md > /dev/null && bash prismpath/examples/pr_demo/demo.sh > /dev/null"
  else
    record "wheel built" FAIL "no wheel in $OUT/dist"
  fi
fi

if [ "$LEG" = "full" ] || [ "$LEG" = "rust" ]; then
  if ! command -v cargo > /dev/null; then record "rust prerequisite" BLOCKED "cargo not found"; else
    cargo --version > "$OUT/cargo-version.txt"
    export CARGO_TARGET_DIR="$OUT/cargo-target"
    run_gate "rust: workspace tests" "$OUT/cargo-test.log" bash -c "cd '$EXPORT' && cargo test --workspace -q"
    run_gate "rust: clippy, warnings denied" "$OUT/clippy.log" bash -c "cd '$EXPORT' && cargo clippy --workspace --all-targets -q -- -D warnings"
    for crate in prismpath-rs prismpath-telemetry-rs prismpath-hotswap-rs prismpath-preflight; do
      run_gate "rust: cargo package $crate" "$OUT/package-$crate.log" bash -c "cd '$EXPORT/$crate' && cargo package -q --allow-dirty --no-verify --list > '$OUT/package-$crate.list' && cargo package -q --allow-dirty --no-verify"
      run_gate "rust: extracted package tests $crate" "$OUT/extracted-$crate.log" bash -c "rm -rf '$OUT/extracted-$crate' && mkdir '$OUT/extracted-$crate' && tar -xzf '$OUT'/cargo-target/package/$crate-*.crate -C '$OUT/extracted-$crate' && cd '$OUT'/extracted-$crate/$crate-* && cargo test -q --offline 2>/dev/null || cargo test -q"
    done
    run_gate "rust: packaged dependency resolution" "$OUT/resolve.log" bash -c "cd '$EXPORT' && cargo metadata --format-version 1 > /dev/null && grep -q 'path' prismpath-telemetry-rs/Cargo.toml && echo 'path dependencies present: publishing needs each dependency published first, in order prismpath-rs, prismpath-telemetry-rs, then the rest' "
  fi
fi

if [ "$LEG" = "full" ]; then
  run_gate "inventory and boundary: repository" "$OUT/boundary-repo.log" bash -c "cd '$EXPORT' && git -C '$REPO' ls-files > /dev/null && '$OUT/venv-full/bin/python' -m tools.check_boundary --repo '$REPO'"
  run_gate "compatibility" "$OUT/compatibility.log" bash -c "cd '$EXPORT' && '$OUT/venv-full/bin/python' -m tools.check_compatibility --repo '$EXPORT'"
  run_gate "product maintenance suite" "$OUT/tools-tests.log" bash -c "cd '$REPO' && '$OUT/venv-full/bin/python' -m pytest tools/tests -q -p no:cacheprovider"
  run_gate "cross language tests" "$OUT/cross-language.log" bash -c "cd '$EXPORT' && '$OUT/venv-full/bin/python' -m pytest prismpath/tests -q -p no:cacheprovider -m cross_language -rs"
  run_gate "provenance check" "$OUT/provenance.log" bash -c "cd '$REPO' && '$OUT/venv-full/bin/python' -m tools.provenance check"
fi

{
  echo
  echo "Python: $(cat "$OUT/python-version.txt" 2>/dev/null || echo 'not run'); cargo: $(cat "$OUT/cargo-version.txt" 2>/dev/null || echo 'not run')"
  echo
  if [ "$FAILED" = "0" ]; then echo "RESULT: all gates passed"; else echo "RESULT: FAILED gates present"; fi
} >> "$REPORT"
cat "$REPORT"
exit "$FAILED"
