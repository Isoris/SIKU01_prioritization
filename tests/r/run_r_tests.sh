#!/usr/bin/env bash
# Run the R test suites of the upstream gate definitions (needs Rscript with bio3d, Biostrings, digest, dplyr).
#
#   bash tests/r/run_r_tests.sh           all suites (about 22 minutes: TST_conservation simulates 4,000 alignments)
#   bash tests/r/run_r_tests.sh --fast    everything except the long TST_conservation unit test (a few seconds)
#
# A test that cannot run (missing package or helper) is reported BLOCKED and counts as a failure: it is never read as a pass.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SIKU01_CODE_DIR="$HERE/_shared"
export SIKU01_MASTER_RANGE="$HERE/_shared/MASTER_numeric_range_unit_test.R"
FAST=0
case "${1:-}" in
  --fast) FAST=1 ;;
  "") ;;
  *) echo "unknown option: $1 (use --fast or nothing)"; exit 2 ;;
esac
command -v Rscript >/dev/null || { echo "Rscript is not on the PATH: the R suites cannot run (create the environment in environment.yml)"; exit 2; }

pass=0; fail=0; skipped=0
for f in "$HERE"/TST_*/*.unit_test.R "$HERE"/TST_*/*.robustness_test.R; do
  name="$(basename "$(dirname "$f")")/$(basename "$f")"
  if [ $FAST -eq 1 ] && [ "$(basename "$f")" = "TST_conservation.unit_test.R" ]; then
    printf "  SKIPPED  %s (--fast)\n" "$name"; skipped=$((skipped+1)); continue
  fi
  out="$(cd "$(dirname "$f")" && Rscript "$(basename "$f")" 2>&1)"; rc=$?
  if [ $rc -eq 0 ]; then
    printf "  PASS     %s\n" "$name"; pass=$((pass+1))
  else
    if grep -qi "cannot run\|requires the .* package\|not found\|there is no package" <<<"$out"; then label=BLOCKED; else label=FAIL; fi
    printf "  %-8s %s\n" "$label" "$name"; fail=$((fail+1))
    tail -6 <<<"$out" | sed 's/^/           /'
  fi
done
echo "R tests: $pass passed, $fail failed or blocked, $skipped skipped"
[ $fail -eq 0 ]
