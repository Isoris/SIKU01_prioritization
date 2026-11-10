#!/usr/bin/env python3
"""frame_check.py - is the frozen candidate frame what the capsule's own code rebuilds from the frozen tables?

ranking/04_tables/candidate_data_v02.tsv (9,162 rows = 1,527 pangenome_id x 6 routes, 69 columns) is a deposit: the capsule has no script
that expands ranking_inputs_by_pangenome_id to the route grain, and analysis.yaml marks it rebuildable: false. The ranking reads it.
This check compares it with ranking_inputs_by_pangenome_id_v01.tsv, which code_A6434_inputs_v01.py assembles from the 13 frozen tables:

  - every pangenome_id of the frame is in the rebuilt table, and every rebuilt orthogroup is in the frame with all 6 routes;
  - every column the two share (63 of 69) holds the same text, for all 9,162 rows.

The 6 columns of the frame that the rebuilt table does not have are named, not compared: candidate_id, route, route_id (the route expansion)
and score_m1_general, score_m1_protein, score_m2_pdna (pre-v27 scores; no v27 rule reads them - analysis.yaml says so).
This script produces nothing; it only compares.

Usage:  python3 postflight/frame_check.py --ranking-inputs FILE --candidate-data FILE
Exit:   0 only if there is no difference.
"""
import argparse, csv, sys

csv.field_size_limit(10**9)
EXPECTED_ONLY_IN_FRAME = ["candidate_id", "route", "route_id", "score_m1_general", "score_m1_protein", "score_m2_pdna"]
ROUTES = {"silica", "cellulose", "aex", "cex", "pdna_tilapia", "pdna_zebrafish"}


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--ranking-inputs", required=True)
    ap.add_argument("--candidate-data", required=True)
    a = ap.parse_args()
    ri, cd = rd(a.ranking_inputs), rd(a.candidate_data)
    idx = {r["pangenome_id"]: r for r in ri}
    shared = [c for c in cd[0] if c in ri[0]]
    only_frame = [c for c in cd[0] if c not in ri[0]]
    bad = 0
    if sorted(only_frame) != sorted(EXPECTED_ONLY_IN_FRAME):
        print("FAIL: columns only in the frame are %s, expected %s" % (only_frame, EXPECTED_ONLY_IN_FRAME)); bad += 1
    routes = {}
    mism = {}
    absent = set()
    for r in cd:
        routes.setdefault(r["pangenome_id"], set()).add(r["route"])
        o = idx.get(r["pangenome_id"])
        if o is None:
            absent.add(r["pangenome_id"]); continue
        for c in shared:
            if r[c] != o[c]:
                mism[c] = mism.get(c, 0) + 1
    notin_frame = sorted(set(idx) - set(routes))
    bad_routes = sorted(p for p, s in routes.items() if s != ROUTES)
    for label, items in (("frame pangenome_id absent from the rebuilt table", sorted(absent)),
                         ("rebuilt pangenome_id absent from the frame", notin_frame),
                         ("pangenome_id without exactly the 6 routes", bad_routes)):
        if items:
            print("FAIL: %d %s, e.g. %s" % (len(items), label, items[:5])); bad += 1
    if mism:
        print("FAIL: %d shared columns differ: %s" % (len(mism), dict(sorted(mism.items())))); bad += 1
    print("frame check: %d frame rows, %d rebuilt orthogroups, %d shared columns compared, %d only in the frame (%s): %s"
          % (len(cd), len(ri), len(shared), len(only_frame), ", ".join(only_frame), "PASS" if not bad else "FAIL"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
