"""Leave-one-out analyses: how much does each single rule matter?

    hard-gate leave-one-out (LOO)     remove ONE hard gate, keep the others: how many more candidates become eligible on each route?
    additive leave-one-out (LOCO)     remove ONE additive component: how do the scores of the eligible candidates change?

Both are computed from the rule outcomes of the reference run (ranking.py); no rule is evaluated a second time. Three quantities are
kept apart and never called just "delta":

    delta_step_reference   a gate inside the ordered funnel: candidates passing minus candidates arriving (depends on rule order)
    delta_final_pass_LOO   a route with one gate removed: change in the number of eligible candidates (order-independent)
    score_delta            a candidate with one additive component removed: perturbed score minus reference score

No tier or membership definition is declared for this rule set, so the tier columns say NOT_DECLARED / NOT_APPLICABLE.

Tables written (11): the reference sets and states, the sequential funnel, the LOO definition / per-candidate / summary tables, the
additive reference execution and score distribution, and the LOCO definition / per-candidate / summary tables.
"""
from collections import OrderedDict, defaultdict

from . import layout
from .rules import FAIL, NOT_EVALUABLE, PASS
from .tables import write_tsv

# Provenance labels kept exactly as in the deposited tables (they name the outcome table and the script of the deposit's layout).
SOURCE_OUTCOMES_PATH = "01_analysis_output/derived/candidate_rule_outcomes_v27_v01.tsv"
SOURCE_OUTCOMES = "candidate_rule_outcomes_v27_v01.tsv"
SOURCE_FINAL_AUDIT = "code_A6434_production_v27_v01.py"


def final_pass(outcome_by_rule, hard_ids, omit=None):
    """Eligibility from one candidate's outcomes, optionally ignoring one hard gate."""
    sts = [v for k, v in outcome_by_rule.items() if k in hard_ids and k != omit]
    if FAIL in sts:
        return FAIL
    return NOT_EVALUABLE if NOT_EVALUABLE in sts else PASS


def score(outcome_by_rule, additive_ids, omit=None):
    """Additive score from one candidate's outcomes, optionally ignoring one component."""
    return sum(1 for k, v in outcome_by_rule.items() if k in additive_ids and k != omit and v == "+1")


def _jaccard(a, b):
    u = a | b
    return (len(a & b) / len(u)) if u else 1.0


def spearman(xs, ys):
    """Spearman correlation with average ranks for ties; None when either side is constant."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    n = len(xs)
    if n < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def analyse(rules, outcomes):
    """All eleven tables, as {file name: rows}."""
    hard = {r["rule_id"]: r for r in rules if r["role"] == "hard"}
    additive = {r["rule_id"]: r for r in rules if r["role"] == "additive"}
    fp = lambda d, omit=None: final_pass(d, hard, omit)       # noqa: E731
    sc = lambda d, omit=None: score(d, additive, omit)        # noqa: E731
    order = lambda table: (lambda rid: float(table[rid]["rule_order"]))   # noqa: E731

    state = defaultdict(dict)   # (pangenome_id, route) -> {rule_id: outcome}
    for o in outcomes:
        state[(o["pangenome_id"], o["route"])][o["rule_id"]] = o["outcome"]
    routes = sorted({r for _, r in state})
    applicable_hard, applicable_add = defaultdict(set), defaultdict(set)
    for (_cid, route), d in state.items():
        for rid in d:
            (applicable_hard if rid in hard else applicable_add)[route].add(rid)
    ref_pass = {route: {cid for (cid, r), d in state.items() if r == route and fp(d) == PASS} for route in routes}
    ref_set_id = {route: f"REFSET_{route.upper()}" for route in routes}
    out = {}

    # 1. the reference set of each route: the candidates that pass every hard gate
    out[layout.T_REFERENCE_SET] = [OrderedDict(
        reference_set_id=ref_set_id[route], route_binding=route, ruleset_id=layout.RULESET_ID,
        execution_order_id="rule_order", source_final_pass_field="final_pass",
        n_candidates=len(ref_pass[route]),
        hard_gate_expression=" AND ".join(sorted(applicable_hard[route], key=order(hard))),
        source_table=SOURCE_OUTCOMES_PATH, status="EXECUTED") for route in routes]

    # 2. the reference state of every candidate
    rows = []
    for (cid, route), d in sorted(state.items()):
        hv = [v for k, v in d.items() if k in hard]
        r = OrderedDict(candidate_id=cid, route_id=route, reference_set_id=ref_set_id[route],
                        final_pass_reference=fp(d), reference_score=sc(d), reference_tier="NOT_DECLARED",
                        n_hard_pass=hv.count(PASS), n_hard_fail=hv.count(FAIL),
                        n_additive_plus1=sum(1 for k, v in d.items() if k in additive and v == "+1"))
        for rid in sorted(additive):
            r[f"score_{rid}"] = (1 if d.get(rid) == "+1" else 0) if rid in d else ""
        r["source_final_audit"] = SOURCE_FINAL_AUDIT
        rows.append(r)
    out[layout.T_REFERENCE_STATE] = rows

    # 3. the sequential funnel (order-dependent; reported for reading, not used for eligibility)
    rows = []
    for route in routes:
        arriving = {cid for (cid, r) in state if r == route}
        for rid in sorted(applicable_hard[route], key=order(hard)):
            passed = {cid for cid in arriving if state[(cid, route)].get(rid) == PASS}
            rows.append(OrderedDict(
                route_id=route, rule_id=rid, layer_position=hard[rid]["layer_position"],
                rule_order=hard[rid]["rule_order"], n_arriving=len(arriving), n_pass=len(passed),
                n_fail=len(arriving) - len(passed), delta_step_reference=len(passed) - len(arriving),
                note="order-dependent sequential step effect; not the LOO quantity"))
            arriving = passed
    out[layout.T_STEP_REFERENCE] = rows

    # 4. hard-gate leave-one-out
    defs, cand_rows, summ, invalid = [], [], [], []
    for rid in sorted(hard, key=order(hard)):
        pid = f"LOO_{rid}"
        routes_for = sorted(r for r in routes if rid in applicable_hard[r])
        if not routes_for:
            continue
        defs.append(OrderedDict(
            perturbation_id=pid, perturbation_class="hard_gate_leave_one_rule_out",
            omitted_rule_id=rid, applicable_routes="; ".join(routes_for),
            reference_ruleset_id=layout.RULESET_ID, reference_execution_order_id="rule_order",
            description=f"omit only {rid}; every remaining hard rule stays at its reference specification",
            status="EXECUTED"))
        for route in routes_for:
            pert = set()
            # candidates in numeric order, so the table is written in the same row order on every run
            for cid in sorted({c for (c, r) in state if r == route}, key=lambda c: (int(c) if str(c).isdigit() else 0, str(c))):
                d = state[(cid, route)]
                rf, pf = fp(d), fp(d, rid)
                if pf == PASS:
                    pert.add(cid)
                changed = rf != pf
                if rf == PASS and pf != PASS:
                    direction = "INVALID_TRUE_TO_FALSE"
                    invalid.append((cid, route, rid))
                elif changed and pf == PASS:
                    # admitted because the removed gate failed it, or because the removed gate could not be evaluated
                    direction = "newly_admitted_not_evaluable" if d.get(rid) == NOT_EVALUABLE else "newly_admitted"
                elif rf == PASS:
                    direction = "stable_pass"
                else:
                    direction = "stable_fail"
                cand_rows.append(OrderedDict(
                    candidate_id=cid, route_id=route, perturbation_id=pid, omitted_rule_id=rid,
                    reference_final_pass=rf, perturbed_final_pass=pf,
                    eligibility_changed=str(changed).upper(), eligibility_direction=direction,
                    reference_set_id=ref_set_id[route], source_reference_execution=SOURCE_OUTCOMES, status="EXECUTED"))
            ref = ref_pass[route]
            summ.append(OrderedDict(
                route_id=route, perturbation_id=pid, omitted_rule_id=rid, layer_position=hard[rid]["layer_position"],
                n_final_pass_reference=len(ref), n_final_pass_perturbed=len(pert),
                delta_final_pass_LOO=len(pert) - len(ref), n_newly_admitted=len(pert - ref),
                n_newly_admitted_not_evaluable=sum(1 for c in (pert - ref) if state[(c, route)].get(rid) == NOT_EVALUABLE),
                n_reference_preserved=len(ref & pert),
                final_pass_jaccard=round(_jaccard(ref, pert), 6), status="EXECUTED"))
    assert not invalid, f"removing a gate made {len(invalid)} eligible candidate(s) ineligible, which cannot happen"
    out[layout.T_LOO_DEFINITION], out[layout.T_LOO_CANDIDATES], out[layout.T_LOO_SUMMARY] = defs, cand_rows, summ

    # 5. the additive components among the eligible candidates of each route
    rows = []
    for route in routes:
        pop = ref_pass[route]
        for rid in sorted(applicable_add[route], key=order(additive)):
            n1 = sum(1 for cid in pop if state[(cid, route)].get(rid) == "+1")
            n0 = len(pop) - n1
            rows.append(OrderedDict(
                route_id=route, reference_set_id=ref_set_id[route], rule_id=rid,
                layer_position=additive[rid]["layer_position"], n_final_pass_reference=len(pop),
                n_zero=n0, pct_zero=round(100 * n0 / len(pop), 2) if pop else "",
                n_plus1=n1, pct_plus1=round(100 * n1 / len(pop), 2) if pop else "", status="EXECUTED"))
    out[layout.T_ADDITIVE_REFERENCE] = rows
    rows = []
    for route in routes:
        pop = ref_pass[route]
        dist = defaultdict(int)
        for cid in pop:
            dist[sc(state[(cid, route)])] += 1
        for s in sorted(dist):
            rows.append(OrderedDict(
                route_id=route, reference_set_id=ref_set_id[route], additive_score=s, n_candidates=dist[s],
                pct_candidates=round(100 * dist[s] / len(pop), 2) if pop else "",
                n_additive_applicable=len(applicable_add[route])))
    out[layout.T_SCORE_DISTRIBUTION] = rows

    # 6. additive leave-one-out, on the eligible candidates (eligibility itself cannot change)
    defs, cand_rows, summ = [], [], []
    for rid in sorted(additive, key=order(additive)):
        pid = f"LOCO_{rid}"
        routes_for = sorted(r for r in routes if rid in applicable_add[r])
        if not routes_for:
            continue
        defs.append(OrderedDict(
            perturbation_id=pid, perturbation_class="additive_component_leave_one_component_out",
            omitted_rule_id=rid, layer_position=additive[rid]["layer_position"],
            applicable_routes="; ".join(routes_for),
            description=f"omit only the {rid} component and recompute the realized score on the fixed "
                        f"hard-gate final-pass reference set; hard eligibility is untouched",
            status="EXECUTED"))
        for route in routes_for:
            pop = sorted(ref_pass[route])
            rs, ps, changed = [], [], 0
            for cid in pop:
                d = state[(cid, route)]
                a, b = sc(d), sc(d, rid)
                rs.append(a)
                ps.append(b)
                ch = a != b
                changed += ch
                cand_rows.append(OrderedDict(
                    candidate_id=cid, route_id=route, perturbation_id=pid, reference_set_id=ref_set_id[route],
                    reference_score=a, perturbed_score=b, score_delta=b - a, score_changed=str(ch).upper(),
                    reference_tier="NOT_DECLARED", perturbed_tier="NOT_DECLARED", tier_changed="NOT_APPLICABLE"))
            rho = spearman(rs, ps)
            summ.append(OrderedDict(
                route_id=route, perturbation_id=pid, omitted_rule_id=rid, layer_position=additive[rid]["layer_position"],
                reference_set_id=ref_set_id[route], n_final_pass_reference=len(pop), n_scores_changed=changed,
                pct_scores_changed=round(100 * changed / len(pop), 2) if pop else "",
                reference_mean_score=round(sum(rs) / len(rs), 4) if rs else "",
                perturbed_mean_score=round(sum(ps) / len(ps), 4) if ps else "",
                reference_median_score=sorted(rs)[len(rs) // 2] if rs else "",
                perturbed_median_score=sorted(ps)[len(ps) // 2] if ps else "",
                score_spearman_rho="" if rho is None else round(rho, 6),
                spearman_note=("undefined: a side is constant after removal" if rho is None else
                               f"tie-dominated: the score is an integer on 0..{len(applicable_add[route])} over "
                               f"{len(pop)} candidates, so rho is computed on midranks"),
                hard_final_pass_changed="FALSE",
                membership_note="no tier or membership definition is declared, so delta_members is not reported"))
    assert not [r for r in cand_rows if int(r["score_delta"]) > 0], "removing a component raised a score, which cannot happen"
    out[layout.T_LOCO_DEFINITION], out[layout.T_LOCO_CANDIDATES], out[layout.T_LOCO_SUMMARY] = defs, cand_rows, summ
    return out


def run(rules, outcomes, out_dir):
    tables = analyse(rules, outcomes)
    for name, rows in tables.items():
        write_tsv(out_dir / name, rows)
    return {name: len(rows) for name, rows in tables.items()}
