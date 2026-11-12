"""Apply the 22 executable rules to every orthogroup on every route.

One candidate is one orthogroup on one route, keyed <pangenome_id>:<route>.

final_pass is the intersection of the hard gates that apply to the route, and does not depend on the order of the rules:

    any gate FAIL                        -> FAIL
    no FAIL, at least one NOT_EVALUABLE  -> NOT_EVALUABLE
    every gate PASS                      -> PASS

additive_score is the number of additive components satisfied on that route. It ranks nothing out: it never changes final_pass.

Tables written
    candidate_rule_outcomes_v27_v01.tsv   one row per candidate and rule (122,160 rows), with the observed value and the threshold
    candidate_route_state_v27_v01.tsv     one row per candidate (9,162 rows): the gate counts, final_pass, the additive score
    rule_outcome_counts_v27_v01.tsv       one row per rule and route: how many passed, failed, were not evaluable, scored +1 or 0
"""
from collections import OrderedDict, defaultdict

from . import layout
from .rules import FAIL, NOT_EVALUABLE, PASS, evaluate, executable, routes_of, threshold_of
from .tables import write_tsv


def final_pass_of(hard_states):
    """The eligibility of one candidate from the states of its hard gates."""
    if FAIL in hard_states:
        return FAIL
    if NOT_EVALUABLE in hard_states:
        return NOT_EVALUABLE
    return PASS


def apply_rules(rules, symbol, frame):
    """Evaluate every applicable rule on every candidate row. Returns (outcomes, states, counts); writes nothing."""
    all_routes = sorted({r["route"] for r in frame})
    todo = executable(rules)
    outcomes, states = [], []
    counts = defaultdict(lambda: defaultdict(int))
    for row in frame:
        route = row["route"]
        key = f"{row['pangenome_id']}:{route}"
        hard_states, score, applicable_additive = [], 0, 0
        for rule in todo:
            if route not in routes_of(rule, all_routes):
                continue
            thr, sym = threshold_of(rule, symbol)
            res = evaluate(row.get(rule["variable"]), rule["operator"], thr)
            if rule["role"] == "hard":
                outcome = NOT_EVALUABLE if res is None else (PASS if res else FAIL)
                hard_states.append(outcome)
            else:
                applicable_additive += 1
                contribution = 1 if res is True else 0   # a missing value adds 0
                score += contribution
                outcome = f"+{contribution}" if contribution else "0"
            counts[(rule["rule_id"], route)][outcome] += 1
            outcomes.append(OrderedDict(
                candidate_key=key, pangenome_id=row["pangenome_id"], route=route,
                rule_id=rule["rule_id"], layer_position=rule["layer_position"], role=rule["role"],
                variable=rule["variable"], operator=rule["operator"],
                threshold_resolved=thr, threshold_symbol=sym or "",
                observed_value=row.get(rule["variable"], ""), outcome=outcome))
        states.append(OrderedDict(
            candidate_key=key, pangenome_id=row["pangenome_id"], route=route,
            n_hard_applicable=len(hard_states), n_hard_pass=hard_states.count(PASS),
            n_hard_fail=hard_states.count(FAIL), n_hard_not_evaluable=hard_states.count(NOT_EVALUABLE),
            final_pass=final_pass_of(hard_states), n_additive_applicable=applicable_additive, additive_score=score))
    return outcomes, states, counts


def count_rows(rules, counts):
    by_id = {r["rule_id"]: r for r in rules}
    rows = []
    for (rid, route), c in sorted(counts.items()):
        rows.append(OrderedDict(
            rule_id=rid, layer_position=by_id[rid]["layer_position"], role=by_id[rid]["role"], route=route,
            n_evaluated=sum(c.values()), n_pass=c.get(PASS, 0), n_fail=c.get(FAIL, 0),
            n_not_evaluable=c.get(NOT_EVALUABLE, 0), n_plus1=c.get("+1", 0), n_zero=c.get("0", 0)))
    return rows


def run(rules, symbol, frame, out_dir):
    """Apply the rules and write the three tables. Returns (outcomes, states)."""
    outcomes, states, counts = apply_rules(rules, symbol, frame)
    write_tsv(out_dir / layout.T_OUTCOMES, outcomes)
    write_tsv(out_dir / layout.T_STATE, states)
    write_tsv(out_dir / layout.T_COUNTS, count_rows(rules, counts))
    return outcomes, states


def final_pass_counts(states):
    """{route: {PASS: n, FAIL: n, NOT_EVALUABLE: n}} in the order of layout.ROUTES."""
    by = {route: {PASS: 0, FAIL: 0, NOT_EVALUABLE: 0} for route in layout.ROUTES}
    for s in states:
        by[s["route"]][s["final_pass"]] += 1
    return by
