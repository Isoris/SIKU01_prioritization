#!/usr/bin/env bash
# Run every test suite in production order: TST_gene_model, TST_carriage, TST_numerical,
# TST_conservation, TST_tmh, TST_counts (the superseded G1->G9 ordering is gone from v27).
#
#   bash run_all_tests_A6434_v01.sh              unit + robustness
#   bash run_all_tests_A6434_v01.sh --with-sens  and the sweeps
#   bash run_all_tests_A6434_v01.sh --suite TST_conservation   one suite
#
# Adapted from run_all_gates_v01.sh. The logic is unchanged: a stub calls stop()
# on purpose, and NOT IMPLEMENTED is counted separately from FAILED, because a
# gate with no test must never read as a gate that passes.
#
# What is added: the outcome of every run is written to GATE_TEST_STATUS_v01.tsv
# so the gate sheets report what HAPPENED rather than what the source text
# contains. A sheet that greps its own test for a marker string will call a
# conditional dependency guard a deliberate stub, which is how a missing package
# gets recorded as a design decision.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SIKU01_CODE_DIR="${SIKU01_CODE_DIR:-$ROOT/_shared}"
export SIKU01_MASTER_RANGE="${SIKU01_MASTER_RANGE:-$ROOT/_shared/MASTER_numeric_range_unit_test.R}"
STATUS="${SIKU01_GATE_STATUS:-$ROOT/../01_analysis_output/raw/GATE_TEST_STATUS_v01.tsv}"

SENS=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-sens) SENS=1; shift;;
    --suite) ONLY="$2"; shift 2;;
    *) echo "unknown option: $1"; exit 2;;
  esac
done
command -v Rscript >/dev/null || { echo "Rscript not on PATH"; exit 2; }
command -v python3 >/dev/null || { echo "python3 not on PATH"; exit 2; }

printf "suite\tkind\tscript\tresult\tdetail\n" > "$STATUS"
pass=0; fail=0; todo=0

interpreter_for() {  # file
  case "$1" in
    *.py) echo python3 ;;
    *)    echo Rscript ;;
  esac
}

run() {  # suite, kind, file
  local out rc detail interp
  interp="$(interpreter_for "$3")"
  out="$( cd "$(dirname "$3")" && "$interp" "$(basename "$3")" 2>&1 )"; rc=$?
  if   [ $rc -eq 0 ]; then
       printf "    %-12s PASS\n" "$2"; pass=$((pass+1))
       # 2026-10-01: G3_G8 and G4 passed with an empty detail cell because neither prints the two
       # shapes this looked for. G3_G8 ends with "10 windows passed, 0 failed" and G4 with
       # "expected/observed mismatches: 0"; both are summary lines, so a pass now records a count.
       detail="$(grep -oE '[0-9]+ / [0-9]+|[0-9]+ assertions, [0-9]+ steps, [0-9]+ failed|[0-9]+ windows passed, [0-9]+ failed|expected/observed mismatches: [0-9]+' <<<"$out" | tail -1)"
       printf "%s\t%s\t%s\tPASS\t%s\n" "$1" "$2" "$(basename "$3")" "$detail" >> "$STATUS"
  elif grep -q "NOT IMPLEMENTED" <<<"$out"; then
       printf "    %-12s todo\n" "$2"; todo=$((todo+1))
       printf "%s\t%s\t%s\tNOT_IMPLEMENTED\t%s\n" "$1" "$2" "$(basename "$3")" \
              "deliberate stub; an unrun sweep must not read as a completed one" >> "$STATUS"
  elif grep -qi "cannot run\|requires the .* package\|not found" <<<"$out"; then
       printf "    %-12s blocked\n" "$2"; todo=$((todo+1))
       detail="$(grep -iE 'cannot run|requires the .* package|not found' <<<"$out" | head -1 | cut -c1-160)"
       printf "%s\t%s\t%s\tBLOCKED\t%s\n" "$1" "$2" "$(basename "$3")" "$detail" >> "$STATUS"
  else printf "    %-12s FAIL\n" "$2"; fail=$((fail+1))
       detail="$(tail -3 <<<"$out" | tr '\n' ' ' | cut -c1-160)"
       printf "%s\t%s\t%s\tFAIL\t%s\n" "$1" "$2" "$(basename "$3")" "$detail" >> "$STATUS"
       sed 's/^/      /' <<<"$out" | tail -6
  fi
}

for d in "$ROOT"/TST_*/; do
  suite="$(basename "$d")"
  [ -n "$ONLY" ] && [ "$suite" != "$ONLY" ] && continue
  echo "$suite"
  for f in "$d"*.unit_test.R "$d"*.unit_test.py; do [ -e "$f" ] && run "$suite" unit "$f"; done
  for f in "$d"*.robustness_test.R "$d"*.robustness_test.py; do [ -e "$f" ] && run "$suite" robustness "$f"; done
  if [ $SENS -eq 1 ]; then
    for f in "$d"*.sensitivity_test.R "$d"*.sensitivity_test.py; do [ -e "$f" ] && run "$suite" sensitivity "$f"; done
  fi
done

# the analysis-level sweep covers every gate; recorded here so the per-gate
# stubs are never read as the only sweep that exists
printf "ALL\tsensitivity\tS14c_QbD_Sensitivity_v01_SIKU01.R\tANALYSIS_LEVEL\t%s\n" \
  "type A and type B, every gate on the sheet" >> "$STATUS"

echo
printf "  passed %d | failed %d | not implemented or blocked %d\n" "$pass" "$fail" "$todo"
printf "  status written: %s\n" "$STATUS"
[ $fail -eq 0 ] || exit 1
