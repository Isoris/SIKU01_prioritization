#!/usr/bin/env bash
# Reproduce the SIKU01 candidate prioritization and check it. One command:
#
#   bash run_all.sh            the prioritization twice + every check + the unit tests           (about 2 minutes)
#   bash run_all.sh --full     the same, and the R test suites of the upstream gate definitions   (about 25 minutes, needs Rscript)
#   PYTHON=/path/to/python bash run_all.sh       use a specific python (default: python)
#
# It ends with "run_all: PASS" only if every part passed. The run is kept in results/<date-time>/ (see README.md).
# On Windows without bash, the same two steps are:  python prioritize.py reproduce   and   python prioritize.py test
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2
PY="${PYTHON:-python}"
FULL=0
case "${1:-}" in
  --full) FULL=1 ;;
  -h|--help) sed -n 2,9p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
esac
rc=0
echo "== 1. reproduce: run the prioritization twice and compare with the deposited results"
"$PY" prioritize.py reproduce || rc=1
echo
echo "== 2. unit tests"
"$PY" prioritize.py test || rc=1
if [ $FULL -eq 1 ]; then
  echo
  echo "== 3. R test suites (upstream gate definitions)"
  bash tests/r/run_r_tests.sh || rc=1
fi
echo
if [ $rc -eq 0 ]; then echo "run_all: PASS"; else echo "run_all: FAIL (see the FAIL lines above)"; fi
exit $rc
