#!/usr/bin/env python3
"""
code_A6434_production_v27_v01.py — current production evaluation of the v27 rule contract.

Capsule-native and authority-driven: every rule, route binding, operator and threshold is READ
from `capsule_brain/ranking_rules_v27.tsv`. Nothing about a rule is hard-coded here, so a rule cannot
drift from its owner, and the five M2D rules that had no production function need no bespoke code.

WHY NOT a6434_engine.py
    That module implements the superseded framework: NEG_WEIGHT / NEG_WEIGHT_FLOOR, a PENALTY_OF
    map, n_m1_protein / n_m2_pdna N-of-M retention counts, aex_z_max / cex_z_min gates and a
    silica floor written in the old orientation. The current contract (prompt §3) has no unique
    ranking, no negative additive penalty, no additive-score retention threshold and no N-of-M
    rule. It is kept as implementation source and provenance, not extended.

CURRENT SEMANTICS (prompt §3)
    hard gate        -> FAIL or PASS; eligibility only
    additive         -> 0 when not satisfied, +1 when satisfied; never alters hard eligibility
    declaration      -> M0.0, not executable
    A missing value never satisfies a condition and never contributes to a score.

GRAIN
    One candidate is one orthogroup on one route, keyed <pangenome_id>:<route>. The input table is
    already at that grain: 1,527 pangenome_id x 6 routes = 9,162 rows.

FINAL PASS
    final_pass is the order-independent intersection of the hard gates applicable to that route:
    every applicable hard gate PASS. It is not sequential survivor state; reporting may still show
    a sequential funnel, but the computation does not depend on rule order (§9).

OUTPUTS (01_analysis_output/derived/)
    candidate_rule_outcomes_v27_v01.tsv   candidate x rule, one row per evaluated rule
    candidate_route_state_v27_v01.tsv     candidate x route, hard state + additive score
    rule_outcome_counts_v27_v01.tsv       rule-level FAIL/PASS/0/+1 counts per route
"""
import csv, os, sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _provenance import record_output

CAP = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
T = os.path.join(CAP, "04_tables")          # records: the candidate measurements
BRAIN = os.path.join(CAP, "capsule_brain")  # declarations: rule, parameter and sweep owners
OUT = os.path.join(CAP, "01_analysis_output", "derived")

PASS, FAIL, NE = "PASS", "FAIL", "NOT_EVALUABLE"
MISSING = {"", "NA", "NaN", "nan", "None", "NULL"}


# %% ---------------------------------------------------------------- SETUP
def read_tsv(path):
    with open(path, newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh, delimiter="\t")]


def load_authority():
    rules = read_tsv(os.path.join(BRAIN, "ranking_rules_v27.tsv"))
    params = read_tsv(os.path.join(BRAIN, "rule_parameter_resolution_v02.tsv"))
    symbol = {p["declared_symbol"]: float(p["resolved_value"]) for p in params}
    # the contract must be exactly what §3 declares, or we stop
    roles = defaultdict(int)
    for r in rules:
        roles[r["role"]] += 1
    assert roles["declaration"] == 1 and roles["hard"] == 14 and roles["additive"] == 8, \
        f"rule contract is not 1 declaration + 14 hard + 8 additive: {dict(roles)}"
    for r in rules:
        if r.get("score_delta_penalty", "").strip() or r.get("penalty_condition", "").strip():
            raise SystemExit(f"PENALTY_PRESENT in authority for {r['rule_id']}: current contract has none")
    # missing values: ONE rule is implemented (a missing value never satisfies a condition and never adds to a score), so the
    # declaration must say exactly that, or we stop. 'fail' is a legal word in the vocabulary but nothing here implements it, and a
    # declaration that the code does not follow is worse than none: it reads as the rule that was applied.
    implemented = {"hard": "not_evaluable", "additive": "skip"}
    for r in rules:
        want = implemented.get(r["role"])
        if want and r.get("missing_policy", "").strip() != want:
            raise SystemExit(f"MISSING_POLICY_NOT_IMPLEMENTED for {r['rule_id']}: declared '{r.get('missing_policy', '')}', "
                             f"implemented '{want}' (hard: NOT_EVALUABLE; additive: contributes 0)")
    return rules, symbol


def routes_of(rule, all_routes):
    spec = rule["routes"].strip()
    if spec == "all":
        return list(all_routes)
    return [x.strip() for x in spec.split(";") if x.strip()]


def threshold_of(rule, symbol):
    raw = rule["threshold"].strip()
    if raw in symbol:
        return symbol[raw], raw          # symbolic, resolved from the parameter owner
    return raw, None


# %% ---------------------------------------------------------------- EVALUATION
def evaluate(value, op, thr):
    """Return True / False / None. None means not evaluable; it never satisfies."""
    if value is None or str(value).strip() in MISSING:
        return None
    v = str(value).strip()
    if op == "==":
        # categorical or integer equality; compare numerically when both sides are numeric
        try:
            return float(v) == float(thr)
        except (TypeError, ValueError):
            return v == str(thr).strip()
    try:
        x = float(v)
    except ValueError:
        return None
    if op == "BETWEEN":
        lo, hi = (float(t) for t in str(thr).split(";"))
        return lo <= x <= hi
    t = float(thr)
    return {"<": x < t, "<=": x <= t, ">": x > t, ">=": x >= t}[op]


def run(rules, symbol, cand):
    all_routes = sorted({r["route"] for r in cand})
    executable = [r for r in rules if r["role"] in ("hard", "additive")]
    assert len(executable) == 22, f"expected 22 executable rules, got {len(executable)}"

    outcomes, states = [], []
    counts = defaultdict(lambda: defaultdict(int))

    for row in cand:
        route = row["route"]
        key = f"{row['pangenome_id']}:{route}"
        hard_states, score, applicable_additive = [], 0, 0
        for rule in executable:
            if route not in routes_of(rule, all_routes):
                continue
            thr, sym = threshold_of(rule, symbol)
            res = evaluate(row.get(rule["variable"]), rule["operator"], thr)
            if rule["role"] == "hard":
                state = NE if res is None else (PASS if res else FAIL)
                hard_states.append(state)
                outcome = state
            else:
                applicable_additive += 1
                contribution = 1 if res is True else 0   # missing contributes 0, never +1
                score += contribution
                outcome = f"+{contribution}" if contribution else "0"
            counts[(rule["rule_id"], route)][outcome] += 1
            outcomes.append(OrderedDict(
                candidate_key=key, pangenome_id=row["pangenome_id"], route=route,
                rule_id=rule["rule_id"], layer_position=rule["layer_position"], role=rule["role"],
                variable=rule["variable"], operator=rule["operator"],
                threshold_resolved=thr, threshold_symbol=sym or "",
                observed_value=row.get(rule["variable"], ""), outcome=outcome))
        # order-independent intersection
        if FAIL in hard_states:
            final = "FAIL"
        elif NE in hard_states:
            final = "NOT_EVALUABLE"
        else:
            final = "PASS"
        states.append(OrderedDict(
            candidate_key=key, pangenome_id=row["pangenome_id"], route=route,
            n_hard_applicable=len(hard_states), n_hard_pass=hard_states.count(PASS),
            n_hard_fail=hard_states.count(FAIL), n_hard_not_evaluable=hard_states.count(NE),
            final_pass=final, n_additive_applicable=applicable_additive, additive_score=score))
    return outcomes, states, counts, all_routes


# %% ---------------------------------------------------------------- COMPOSE
# the declared inputs and code of every output of this script, for the produced_from record
INPUTS = ["04_tables/candidate_data_v02.tsv",
          "capsule_brain/ranking_rules_v27.tsv",
          "capsule_brain/rule_parameter_resolution_v02.tsv"]
CODE = ["02_code/code_A6434_production_v27_v01.py", "02_code/_provenance.py"]
UNRECORDED = []


def write_tsv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    # recorded at the moment of writing: without it the output is UNRECORDED and staleness, which is
    # a comparison of recorded hashes, cannot be computed for it at all
    if record_output(CAP, path, INPUTS, CODE) is None:
        UNRECORDED.append(os.path.relpath(path, CAP))


def main():
    rules, symbol = load_authority()
    cand = read_tsv(os.path.join(T, "candidate_data_v02.tsv"))
    outcomes, states, counts, all_routes = run(rules, symbol, cand)

    write_tsv(os.path.join(OUT, "candidate_rule_outcomes_v27_v01.tsv"), outcomes)
    write_tsv(os.path.join(OUT, "candidate_route_state_v27_v01.tsv"), states)

    crows = []
    for (rid, route), c in sorted(counts.items()):
        rule = next(r for r in rules if r["rule_id"] == rid)
        crows.append(OrderedDict(
            rule_id=rid, layer_position=rule["layer_position"], role=rule["role"], route=route,
            n_evaluated=sum(c.values()), n_pass=c.get(PASS, 0), n_fail=c.get(FAIL, 0),
            n_not_evaluable=c.get(NE, 0), n_plus1=c.get("+1", 0), n_zero=c.get("0", 0)))
    write_tsv(os.path.join(OUT, "rule_outcome_counts_v27_v01.tsv"), crows)

    print(f"candidates {len(states)} = {len({s['pangenome_id'] for s in states})} pangenome_id x {len(all_routes)} routes")
    print(f"rule outcomes {len(outcomes)} | rule x route rows {len(crows)}")
    print("\nfinal_pass by route (order-independent hard intersection):")
    by = defaultdict(lambda: defaultdict(int))
    for s in states:
        by[s["route"]][s["final_pass"]] += 1
    for route in all_routes:
        d = by[route]
        print(f"  {route:<16} PASS {d['PASS']:>5} | FAIL {d['FAIL']:>5} | NOT_EVALUABLE {d['NOT_EVALUABLE']:>4}")
    print("\nadditive score distribution by route:")
    dist = defaultdict(lambda: defaultdict(int))
    for s in states:
        dist[s["route"]][s["additive_score"]] += 1
    for route in all_routes:
        d = dist[route]
        print(f"  {route:<16} " + "  ".join(f"{k}:{d[k]}" for k in sorted(d)))
    print(f"\nwrote -> {os.path.relpath(OUT, CAP)}/")


if __name__ == "__main__":
    rc = main()
    if UNRECORDED:
        print(f"\nWARNING: {len(UNRECORDED)} output(s) carry no produced_from record, so "
              f"`research_os stale` will report them UNRECORDED:")
        for x in UNRECORDED:
            print(f"  {x}")
    else:
        print("\nprovenance: every output carries a produced_from record")
    sys.exit(rc)
