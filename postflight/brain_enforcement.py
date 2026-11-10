#!/usr/bin/env python3
"""brain_enforcement.py - did the run apply the rules the capsule brain declares, and nothing else?

The capsule's method is table-driven: the rules (rules/ranking_rules_v27.tsv), their resolved population thresholds
(rule_parameter_resolution_v02.tsv) and the sweep contract (ST_A6434_03_parameter_sweep_contract_v02.tsv) are the authority; the code
hard-codes none of them. This check reads the run's OUTPUT and compares what was applied with what the brain declares.

  RULES    every row of candidate_rule_outcomes_v27_v01.tsv names a rule of the brain, with the brain's variable and operator and the
           brain's threshold (a symbol such as Q3_cai_ec is compared with its resolved value); the rule is applied only on routes the
           brain binds it to; no declared (rule, route, candidate) is missing or doubled. Count: executable rules per route x 1,527.
  COUNTS   rule_outcome_counts_v27_v01.tsv adds up to the outcomes file, rule by rule and route by route.
  SWEEPS   every row of the executed sweep table (ST_A6434_03_parameter_sweeps_v02.tsv) is a row of the sweep contract with the same
           rule, variable, operator, reference value and sweep family, and every contract row was executed.

Usage:  python3 postflight/brain_enforcement.py --out-dir DIR [--brain DIR]   (--brain: a tuned copy of the brain tables; files it lacks fall back to rules/)
Exit:   0 only if there is no deviation. Standard library only.
"""
import argparse, collections, csv, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRAIN = os.path.join(ROOT, "rules")
csv.field_size_limit(10**9)


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def same_number(a, b):
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--brain", default=None)
    a = ap.parse_args()
    def bf(name):
        return os.path.join(a.brain, name) if a.brain and os.path.isfile(os.path.join(a.brain, name)) else os.path.join(BRAIN, name)

    rules = {r["rule_id"]: r for r in rd(bf("ranking_rules_v27.tsv")) if r["role"] in ("hard", "additive")}
    resolved = {r["declared_symbol"]: r["resolved_value"] for r in rd(bf("rule_parameter_resolution_v02.tsv"))}
    contract = rd(bf("ST_A6434_03_parameter_sweep_contract_v02.tsv"))
    out = rd(os.path.join(a.out_dir, "candidate_rule_outcomes_v27_v01.tsv"))
    counts = rd(os.path.join(a.out_dir, "rule_outcome_counts_v27_v01.tsv"))
    sweeps = rd(os.path.join(a.out_dir, "ST_A6434_03_parameter_sweeps_v02.tsv"))
    problems = []

    def routes_of(rule):
        return None if rule["routes"].strip() == "all" else {t.strip() for t in rule["routes"].split(";")}

    # RULES
    seen = collections.Counter()
    all_routes = {r["route"] for r in out}
    for o in out:
        rule = rules.get(o["rule_id"])
        if rule is None:
            problems.append("outcome for a rule not in the brain: " + o["rule_id"]); continue
        rts = routes_of(rule)
        if rts is not None and o["route"] not in rts:
            problems.append("%s applied on route %s, which the brain does not bind it to" % (o["rule_id"], o["route"]))
        if o["variable"] != rule["variable"] or o["operator"] != rule["operator"]:
            problems.append("%s applied as %s %s, brain says %s %s" % (o["rule_id"], o["variable"], o["operator"], rule["variable"], rule["operator"]))
        want = resolved.get(rule["threshold"], rule["threshold"])
        got = o["threshold_resolved"]
        if rule["operator"] == "BETWEEN":
            ok = [x.strip() for x in got.split(";")] == [x.strip() for x in want.split(";")] or all(same_number(x, y) for x, y in zip(got.split(";"), want.split(";")))
        else:
            ok = same_number(got, want)
        if not ok:
            problems.append("%s threshold applied %s, brain resolves to %s" % (o["rule_id"], got, want))
        seen[(o["rule_id"], o["route"], o["pangenome_id"])] += 1
    n_cand = len({o["pangenome_id"] for o in out})
    expected = {(rid, rt, "*") for rid, r in rules.items() for rt in (all_routes if routes_of(r) is None else routes_of(r))}
    got_pairs = {(k[0], k[1], "*") for k in seen}
    if expected != got_pairs:
        problems.append("rule/route pairs differ: missing %s, extra %s" % (sorted(expected - got_pairs)[:4], sorted(got_pairs - expected)[:4]))
    doubled = [k for k, v in seen.items() if v != 1]
    if doubled:
        problems.append("%d (rule, route, candidate) applied more than once, e.g. %s" % (len(doubled), doubled[:2]))
    per_pair = collections.Counter((k[0], k[1]) for k in seen)
    short = [k for k, v in per_pair.items() if v != n_cand]
    if short:
        problems.append("%d rule/route pairs do not cover all %d candidates, e.g. %s" % (len(short), n_cand, short[:2]))
    print("  RULES    %d outcome rows; %d rules x routes as the brain binds them (%d rule/route pairs) x %d orthogroups; deviations: %d"
          % (len(out), len(rules), len(expected), n_cand, sum(1 for p in problems)))

    # COUNTS
    tally = collections.defaultdict(collections.Counter)
    for o in out:
        tally[(o["rule_id"], o["route"])][o["outcome"]] += 1
    cbad = 0
    for c in counts:
        t = tally.get((c["rule_id"], c["route"]), collections.Counter())
        plus1 = t.get("+1", 0)
        pass_, fail, ne = t.get("PASS", 0), t.get("FAIL", 0), t.get("NOT_EVALUABLE", 0)
        if (str(pass_), str(fail), str(ne), str(plus1)) != (c["n_pass"], c["n_fail"], c["n_not_evaluable"], c["n_plus1"]) or str(sum(t.values())) != c["n_evaluated"]:
            cbad += 1
            problems.append("counts table disagrees with the outcomes for %s on %s" % (c["rule_id"], c["route"]))
    print("  COUNTS   %d rows of rule_outcome_counts reconciled with the outcomes, %d disagree" % (len(counts), cbad))

    # SWEEPS
    key = lambda r: r["sweep_id"]
    cmap = {key(r): r for r in contract}
    sbad = 0
    for s in sweeps:
        c = cmap.get(key(s))
        if c is None:
            problems.append("executed sweep not in the contract: " + key(s)); sbad += 1; continue
        for col in ("rule_id", "variable", "operator", "reference_value", "sweep_family", "sweep_value_expression", "is_reference"):
            if s[col] != c[col]:
                problems.append("sweep %s: %s is %r, contract says %r" % (key(s), col, s[col], c[col])); sbad += 1
    notrun = sorted(set(cmap) - {key(s) for s in sweeps})
    if notrun:
        problems.append("%d contract sweeps not executed, e.g. %s" % (len(notrun), notrun[:3])); sbad += len(notrun)
    print("  SWEEPS   %d executed sweeps against %d contract rows, %d deviations" % (len(sweeps), len(contract), sbad))

    for p in problems[:12]:
        print("  DEVIATION " + p)
    if len(problems) > 12:
        print("  ... and %d more" % (len(problems) - 12))
    print("brain enforcement: %s" % ("PASS" if not problems else "FAIL"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
