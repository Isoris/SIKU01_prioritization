#!/usr/bin/env bash
# run_all.sh - reproduce the candidate prioritization and check it against the deposited results. One command:
#
#   bash run_all.sh                 preflight, then the ranking twice, then every check (about 23 minutes with the tests, 70 s with --no-tests);
#                                   the checked run is kept in runs/<date-time>/ (see below)
#   bash run_all.sh --out DIR       the same, but keep the checked run in DIR instead of runs/<date-time>/
#   bash run_all.sh --no-tests      skip the unit tests of the first run (the one R test TST_conservation alone takes about 22 minutes)
#   PYTHON=/path/to/python bash run_all.sh      use a specific python (default: python)
#
# What a run leaves behind (runs/ is not tracked by git):
#   runs/<date-time>/  the 21 result tables of the checked run, its execution trace run_log.json (steps, versions, tests,
#                      output hashes), stage_run1.log / stage_run2.log (the ranking's own output), POSTFLIGHT_VERDICT.txt,
#                      and run_all.log (everything this script printed)
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
        -h|--help) sed -n 2,15p "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
    shift
done
cd "$HERE" || exit 2
[ -n "$OUT" ] || OUT="runs/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$OUT" || exit 2
OUT="$(cd "$OUT" && pwd)"
exec > >(tee "$OUT/run_all.log") 2>&1      # everything below is shown and also saved in run_all.log
echo "run_all: started $(date '+%Y-%m-%d %H:%M:%S'); this run is kept in $OUT"
echo
cat <<'TXT'
WHAT IS WHERE
  inputs/            INPUT   the 13 frozen *_by_pangenome_id tables (conservation/entropy, descriptors, gene data, epitopes, host similarity, InterPro,
                             M0 gate, coverage ...), the literature inputs, candidate_data_v02.tsv and route_manifest.tsv, the lock with every checksum
  rules/             RULES   ranking_rules_v27.tsv = the 23 prioritization rules (14 hard gates, 8 additive components); their thresholds, the sweep plan
  code/              CODE    the ranking code (the capsule's own); run_ranking.py runs it, workdir.py maps the folders
  tests/             TESTS   unit, robustness and known-answer suites
  expected_outputs/  TARGET  the 21 deposited result files a run is compared with. The final shortlists: candidate_route_state_v27_v01.tsv
  raw/               RAW     the Panaroo output, input genomes and core alignments the input tables were derived from (records; not re-run here)
  runs/              RUNS    one folder per run_all.sh: the checked run's tables, its trace run_log.json, the logs and the verdict (not in git)
  Six routes: silica, cellulose, anion exchange (AEX), cation exchange (CEX), and pDNA for Nile tilapia and for zebrafish.
TXT
echo
echo "== step 1/2  preflight: is everything unchanged and the environment right?"
"$PY" preflight/preflight.py || { echo "run_all: stopped at the preflight"; exit 1; }
echo
echo "== step 2/2  postflight --run: run the ranking twice and check the result"
"$PY" postflight/postflight.py --run --keep "$OUT" $NOTESTS
rc=$?
STATE="$OUT/candidate_route_state_v27_v01.tsv"
[ -f "$STATE" ] || STATE="expected_outputs/candidate_route_state_v27_v01.tsv"
echo
echo "== final shortlists (candidates with final_pass = PASS, by route; from $STATE)"
"$PY" - "$STATE" <<'PYEOF'
import csv, collections, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig"), delimiter="\t"))
c = collections.Counter(r["route"] for r in rows if r["final_pass"] == "PASS")
for k in ("silica", "cellulose", "aex", "cex", "pdna_tilapia", "pdna_zebrafish"):
    print("   %-16s %4d" % (k, c.get(k, 0)))
print("   %-16s %4d   (%d candidate x route rows)" % ("total", sum(c.values()), len(rows)))
PYEOF
echo
echo "   kept: $OUT  (21 tables, run_log.json, stage_run1.log, stage_run2.log, POSTFLIGHT_VERDICT.txt, run_all.log)"
if [ "$rc" = 0 ]; then echo "run_all: PASS"; else echo "run_all: FAIL (see the FAIL lines above)"; fi
exit $rc
