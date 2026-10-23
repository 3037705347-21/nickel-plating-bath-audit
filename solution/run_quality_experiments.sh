#!/usr/bin/env bash
set -euo pipefail

task_dir="$(cd "$(dirname "$0")/.." && pwd)"
evidence_dir="$task_dir/solution/evidence"
image="harbor-nickel-bath-quality:$$"
mkdir -p "$evidence_dir"

docker build -q -t "$image" "$task_dir/environment" >/dev/null

prepare_workspace() {
  local name="$1"
  shift
  local directory
  directory="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-${name}.XXXXXX")"
  cp -R "$task_dir/environment/workspace/." "$directory"/
  for module in "$@"; do
    cp "$task_dir/solution/$module" "$directory/bath_audit/$module"
  done
  printf '%s\n' "$directory"
}

run_case() {
  local name="$1"
  local workspace="$2"
  local logs
  logs="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-logs-${name}.XXXXXX")"
  chmod 0777 "$logs"
  {
    printf '$ docker run --rm -v %s:/workspace -v %s/tests:/tests:ro -v %s:/logs %s bash /tests/test.sh\n' \
      "$workspace" "$task_dir" "$logs" "$image"
    docker run --rm \
      -v "$workspace:/workspace" \
      -v "$task_dir/tests:/tests:ro" \
      -v "$logs:/logs" \
      "$image" \
      bash /tests/test.sh
    printf 'reward=%s\n' "$(cat "$logs/verifier/reward.txt")"
    printf 'summary='
    python3 - "$logs/verifier/ctrf.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    summary = json.load(handle)["results"]["summary"]
print(
    f"tests={summary['tests']} passed={summary['passed']} "
    f"failed={summary['failed']}"
)
PY
  } >"$evidence_dir/$name.log" 2>&1
}

baseline_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-baseline.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$baseline_workspace"/
run_case baseline "$baseline_workspace"

oracle_workspace="$(prepare_workspace oracle nickel.py boric_acid.py chloride.py forecast.py makeup.py packaging.py release_state.py cli.py)"
run_case oracle "$oracle_workspace"

partial_c1_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-c1.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$partial_c1_workspace"/
cp "$task_dir/solution/partials/c1/nickel.py" "$partial_c1_workspace/bath_audit/nickel.py"
run_case partial-c1 "$partial_c1_workspace"

partial_c2_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-c2.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$partial_c2_workspace"/
cp "$task_dir/solution/partials/c2/boric_acid.py" "$partial_c2_workspace/bath_audit/boric_acid.py"
run_case partial-c2 "$partial_c2_workspace"

partial_c3_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-c3.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$partial_c3_workspace"/
cp "$task_dir/solution/partials/c3/makeup.py" "$partial_c3_workspace/bath_audit/makeup.py"
run_case partial-c3 "$partial_c3_workspace"

partial_c4_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-c4.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$partial_c4_workspace"/
cp "$task_dir/solution/forecast.py" "$partial_c4_workspace/bath_audit/forecast.py"
run_case partial-c4 "$partial_c4_workspace"

partial_c5_workspace="$(mktemp -d "${TMPDIR:-/tmp}/nickel-bath-c5.XXXXXX")"
cp -R "$task_dir/environment/workspace/." "$partial_c5_workspace"/
cp "$task_dir/solution/packaging.py" "$partial_c5_workspace/bath_audit/packaging.py"
run_case partial-c5 "$partial_c5_workspace"

empty_workspace="$(prepare_workspace empty nickel.py boric_acid.py chloride.py forecast.py makeup.py packaging.py release_state.py cli.py)"
cp "$task_dir/solution/bypasses/empty/cli.py" "$empty_workspace/bath_audit/cli.py"
run_case bypass-empty "$empty_workspace"

malformed_workspace="$(prepare_workspace malformed nickel.py boric_acid.py chloride.py forecast.py makeup.py packaging.py release_state.py cli.py)"
cp "$task_dir/solution/bypasses/malformed/cli.py" "$malformed_workspace/bath_audit/cli.py"
run_case bypass-malformed "$malformed_workspace"

hardcoded_workspace="$(prepare_workspace hardcoded nickel.py boric_acid.py chloride.py forecast.py makeup.py packaging.py release_state.py cli.py)"
cp "$task_dir/solution/bypasses/hardcoded/cli.py" "$hardcoded_workspace/bath_audit/cli.py"
run_case bypass-hardcoded "$hardcoded_workspace"

docker image rm -f "$image" >/dev/null 2>&1 || true
