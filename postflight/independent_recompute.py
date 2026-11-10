#!/usr/bin/env python3
"""independent_recompute.py - recompute the ranking outcome from the rule table alone and compare it with a run's output.

This is the check that the stage does what the rules SAY, not merely what it did last time. It imports nothing from code/:
the rules are read from rules/ranking_rules_v27.tsv, the data from inputs/candidate_data_v02.tsv.

  1. The five population thresholds (Q3 of CAI E. coli / CAI Nile tilapia / CAI zebrafish / GC3, median CDS length) are recomputed
     from the 1,527 entry orthogroups and compared with the values stamped in rule_parameter_resolution_v02.tsv.
  2. Every (pangenome_id, route) row is evaluated against the hard and additive rules that bind to its route. A missing value never
     satisfies a condition (the semantics the production script states). Counts of hard rules passed / failed / not evaluable, the
     additive score and final_pass are compared with candidate_route_state_v27_v01.tsv from the run.

Usage:  python3 postflight/independent_recompute.py --out-dir DIR [--brain DIR]      (DIR holds the run's candidate_route_state_v27_v01.tsv)
Exit:   0 only if the thresholds reproduce and no row differs.
The rule table's missing_policy column now says what the code applies (hard rules: not_evaluable; additive rules: skip); production stops if it does not.
"""
import argparse, collections, csv, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RK = ROOT
csv.field_size_limit(10**9)


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def quantile7(xs, p):  # linear interpolation between order statistics (R type 7, numpy default)
    xs = sorted(xs)
    h = (len(xs) - 1) * p
    lo, hi = math.floor(h), math.ceil(h)
    return xs[lo] + (xs[hi] - xs[lo]) * (h - lo)


MISSING = ("", "NA", "NaN", "nan", "None", "NULL")
SYMBOLS = {"Q3_cai_ec": ("rep__cai_ec", .75), "Q3_gc3": ("rep__gc3", .75), "Q3_cai_on": ("rep__cai_on", .75),
           "Q3_cai_dr": ("rep__cai_dr", .75), "median_cds_length_nt": ("rep__cds_length_nt", .5)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--brain", default=None, help="a tuned copy of the brain tables; files it lacks fall back to rules/")
    a = ap.parse_args()
    def bf(name):
        return os.path.join(a.brain, name) if a.brain and os.path.isfile(os.path.join(a.brain, name)) else os.path.join(RK, "rules", name)

    rules = [r for r in rd(bf("ranking_rules_v27.tsv")) if r["role"] in ("hard", "additive")]
    cd = rd(os.path.join(RK, "inputs", "candidate_data_v02.tsv"))
    out = {r["candidate_key"]: r for r in rd(os.path.join(a.out_dir, "candidate_route_state_v27_v01.tsv"))}
    stamped = {r["declared_symbol"]: float(r["resolved_value"]) for r in rd(bf("rule_parameter_resolution_v02.tsv"))}

    entry = {}
    for r in cd:
        entry.setdefault(r["pangenome_id"], r)
    resolved, thr_bad = {}, []
    for s, (col, p) in SYMBOLS.items():
        xs = [num(r[col]) for r in entry.values() if num(r[col]) is not None]
        resolved[s] = quantile7(xs, p)
        if abs(resolved[s] - stamped[s]) >= 1e-12:
            thr_bad.append(s)
    print("  thresholds: %d of %d recomputed from the %d entry orthogroups equal the stamped values%s"
          % (len(SYMBOLS) - len(thr_bad), len(SYMBOLS), len(entry), "" if not thr_bad else " (differ: " + ", ".join(thr_bad) + ")"))

    def evaluate(rule, row):
        raw = row[rule["variable"]].strip()
        op, th = rule["operator"], rule["threshold"]
        if raw in MISSING:
            return None
        x = num(raw)
        if op == "==":
            return (x == float(th)) if (x is not None and num(th) is not None) else raw == th
        if x is None:
            return None
        if op == "BETWEEN":
            lo, hi = (float(t) for t in th.split(";"))
            return lo <= x <= hi
        t = resolved[th] if th in resolved else float(th)
        return {">=": x >= t, ">": x > t, "<=": x <= t, "<": x < t}[op]

    rows = differ = missing_rows = 0
    examples = []
    for r in cd:
        key = "%s:%s" % (r["pangenome_id"], r["route"])
        app = [x for x in rules if x["routes"] == "all" or r["route"] in [t.strip() for t in x["routes"].split(";")]]
        hp = hf = hn = add = nadd = 0
        for x in app:
            v = evaluate(x, r)
            if x["role"] == "hard":
                if v is None:
                    hn += 1
                elif v:
                    hp += 1
                else:
                    hf += 1
            else:
                nadd += 1
                add += 1 if v else 0
        nhard = sum(1 for x in app if x["role"] == "hard")
        fin = "FAIL" if hf else ("NOT_EVALUABLE" if hn else "PASS")
        o = out.get(key)
        if o is None:
            missing_rows += 1
            continue
        rows += 1
        mine = (str(nhard), str(hp), str(hf), str(hn), str(add), str(nadd), fin)
        theirs = (o["n_hard_applicable"], o["n_hard_pass"], o["n_hard_fail"], o["n_hard_not_evaluable"], o["additive_score"], o["n_additive_applicable"], o["final_pass"])
        if mine != theirs:
            differ += 1
            if len(examples) < 3:
                examples.append((key, mine, theirs))
    extra = len(set(out) - {"%s:%s" % (r["pangenome_id"], r["route"]) for r in cd})
    for e in examples:
        print("  DIFF", e)
    print("  rows: %d recomputed, %d differ from the run, %d absent from the run, %d in the run but not in the data" % (rows, differ, missing_rows, extra))
    ok = not thr_bad and differ == 0 and missing_rows == 0 and extra == 0 and rows == len(cd)
    print("independent recompute: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
