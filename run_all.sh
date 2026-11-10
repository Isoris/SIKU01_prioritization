#!/usr/bin/env bash
# run_all.sh - reproduce the candidate prioritization and check it against the deposited results. One command:
#
#   bash run_all.sh                 preflight, then the ranking twice, then every check (about 2-3 minutes)
#   bash run_all.sh --out DIR       the same, and also keep one run's 21 output tables in DIR
#   bash run_all.sh --no-tests      skip the unit tests of the first run
#   PYTHON=/path/to/python bash run_all.sh      use a specific python (default: python)
#
# Needs the environment in environment.yml (python 3.11, pandas 2.3.3; Rscript only for the four R test suites).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python}"
OUT=""; NOTESTS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --out) shift; OUT="${1:?--out needs a directory}" ;;
        --no-tests) NOTESTS="--no-tests" ;;
        -h|--help) sed -n 2,9p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done
cd "$HERE" || exit 2
cat <<'TXT'
WHAT IS WHERE
  inputs/            INPUT   the 13 frozen *_by_pangenome_id tables (conservation/entropy, descriptors, gene data, epitopes, host similarity, InterPro,
                             M0 gate, coverage ...), the literature inputs, candidate_data_v02.tsv and route_manifest.tsv, the lock with every checksum
  rules/             RULES   ranking_rules_v27.tsv = the 23 prioritization rules (14 hard gates, 8 additive components); their thresholds, the sweep plan
  code/              CODE    the ranking code (unchanged); run_ranking.py runs it, workdir.py maps the folders
  tests/             TESTS   unit, robustness and known-answer suites
  expected_outputs/  TARGET  the 21 deposited result files a run is compared with. The final shortlists: candidate_route_state_v27_v01.tsv
  raw/               RAW     the Panaroo output, input genomes and core alignments the input tables were derived from (records; not re-run here)
  Six routes: silica, cellulose, anion exchange (AEX), cation exchange (CEX), and pDNA for Nile tilapia and for zebrafish.
TXT
echo
echo "== step 1/2  preflight: is everything unchanged and the environment right?"
"$PY" preflight/preflight.py || { echo "run_all: stopped at the preflight"; exit 1; }
echo
echo "== step 2/2  postflight --run: run the ranking twice and check the result"
"$PY" postflight/postflight.py --run $NOTESTS
rc=$?
if [ -n "$OUT" ] && [ "$rc" = 0 ]; then
    echo; echo "== keeping one run's tables in $OUT"; "$PY" run_ranking.py --out-dir "$OUT" --tests none > /dev/null && echo "   written: $OUT (21 tables, run_log.json)"
fi
echo
echo "== final shortlists (candidates with final_pass = PASS, by route; from expected_outputs/, which the run was just checked against)"
"$PY" - <<'PYEOF'
import csv, collections
rows = list(csv.DictReader(open("expected_outputs/candidate_route_state_v27_v01.tsv", encoding="utf-8-sig"), delimiter="\t"))
c = collections.Counter(r["route"] for r in rows if r["final_pass"] == "PASS")
for k in ("silica", "cellulose", "aex", "cex", "pdna_tilapia", "pdna_zebrafish"):
    print("   %-16s %4d" % (k, c.get(k, 0)))
print("   %-16s %4d   (%d candidate x route rows)" % ("total", sum(c.values()), len(rows)))
PYEOF
echo
if [ "$rc" = 0 ]; then echo "run_all: PASS"; else echo "run_all: FAIL (see the FAIL lines above)"; fi
exit $rc
