#!/usr/bin/env python3
"""
code_A6434_perturbation_v27_v01.py — hard-gate LOO and additive LOCO under the v27 contract.

Implements 11_handoff/A6434_perturbation_reporting_spec_v02.md and the two planned_* READMEs, whose
.example.tsv files are schema only. Authority is read from capsule_brain/; the reference execution is
read from 01_analysis_output/derived/candidate_rule_outcomes_v27_v01.tsv, so no rule is re-expressed.

THREE SEPARATE QUANTITIES (§10 delta namespace; never a bare `delta`)
    delta_step_reference   rule within the ordered reference execution: n_pass - n_arriving
    delta_final_pass_LOO   route x hard-gate perturbation: change in final-pass N
    score_delta            candidate x route x additive perturbation: perturbed - reference
    delta_members          only when a tier/membership definition is declared (none is)

final_pass_reference
    planned_additive_perturbation/README.md §2 allows the order-independent intersection reading
    once all hard-gate outcomes are materialized independently. candidate_rule_outcomes_v27_v01.tsv
    carries every applicable rule's outcome per candidate, so that condition is met and final_pass is
    the intersection of the applicable hard gates. The sequential funnel is reported separately as
    delta_step_reference, which is order-dependent by construction.

TIER / MEMBERSHIP
    No tier definition is declared by the current authority (analysis.yaml makes tier outputs
    conditional on one existing). So membership_stability_summary and tier_membership_change are NOT
    materialized, and no tier column is invented. §8: tier N and Jaccard only if a tier is declared.
"""
import csv, os, sys
from collections import defaultdict, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _provenance import record_output

CAP = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BRAIN = os.path.join(CAP, "capsule_brain")
DER = os.path.join(CAP, "01_analysis_output", "derived")
PASS, FAIL, NE = "PASS", "FAIL", "NOT_EVALUABLE"
RULESET = "ranking_rules_v27"


def read_tsv(p):
    with open(p, newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh, delimiter="\t")]


# every output of this script is produced from the same declared inputs by the same code, so the
# provenance record is identical apart from the output itself
INPUTS = ["capsule_brain/ranking_rules_v27.tsv",
          "01_analysis_output/derived/candidate_rule_outcomes_v27_v01.tsv"]
CODE = ["02_code/code_A6434_perturbation_v27_v01.py", "02_code/_provenance.py"]
_unrecorded = []


def write_tsv(p, rows):
    if not rows:
        print(f"  (nothing to write for {os.path.basename(p)})"); return
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    # record at the moment the output is written: an output with no record is UNRECORDED, which is
    # neither current nor stale, so staleness could never be computed for it
    if record_output(CAP, p, INPUTS, CODE) is None:
        _unrecorded.append(os.path.relpath(p, CAP))
    print(f"  {os.path.relpath(p, CAP)}  ({len(rows)} rows)")


def jaccard(a, b):
    u = a | b
    return (len(a & b) / len(u)) if u else 1.0


def spearman(xs, ys):
    """Spearman rho with average ranks; None when either side is constant."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v); i = 0
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


# ---------------------------------------------------------------- load the reference execution
rules = read_tsv(os.path.join(BRAIN, "ranking_rules_v27.tsv"))
outcomes = read_tsv(os.path.join(DER, "candidate_rule_outcomes_v27_v01.tsv"))
hard = {r["rule_id"]: r for r in rules if r["role"] == "hard"}
additive = {r["rule_id"]: r for r in rules if r["role"] == "additive"}

# candidate x route -> {rule_id: outcome}
state = defaultdict(dict)
for o in outcomes:
    state[(o["pangenome_id"], o["route"])][o["rule_id"]] = o["outcome"]
routes = sorted({r for _, r in state})
applicable_hard = defaultdict(set)
applicable_add = defaultdict(set)
for (cid, route), d in state.items():
    for rid, out in d.items():
        (applicable_hard if rid in hard else applicable_add)[route].add(rid)


def final_pass(d, omit=None):
    """Order-independent intersection of the applicable hard gates, optionally omitting one."""
    sts = [v for k, v in d.items() if k in hard and k != omit]
    if FAIL in sts:
        return "FAIL"
    return "NOT_EVALUABLE" if NE in sts else "PASS"


def score(d, omit=None):
    return sum(1 for k, v in d.items() if k in additive and k != omit and v == "+1")


def outcome(cid, route, rid):
    """The reference outcome of one rule on one candidate-route, or None if not materialized."""
    return state.get((cid, route), {}).get(rid)


ref_pass = {route: {cid for (cid, r), d in state.items() if r == route and final_pass(d) == "PASS"}
            for route in routes}

print("reference final_pass by route:")
for route in routes:
    print(f"  {route:<16} {len(ref_pass[route]):>5}")

# ---------------------------------------------------------------- 1. hard-gate reference sets
ref_set_id = {route: f"REFSET_{route.upper()}" for route in routes}
rows = []
for route in routes:
    gates = sorted(applicable_hard[route], key=lambda r: float(hard[r]["rule_order"]))
    rows.append(OrderedDict(
        reference_set_id=ref_set_id[route], route_binding=route, ruleset_id=RULESET,
        execution_order_id="rule_order", source_final_pass_field="final_pass",
        n_candidates=len(ref_pass[route]),
        hard_gate_expression=" AND ".join(gates),
        source_table="01_analysis_output/derived/candidate_rule_outcomes_v27_v01.tsv",
        status="EXECUTED"))
print("\nhard-gate reference sets:")
write_tsv(os.path.join(DER, "hard_gate_reference_set_v01.tsv"), rows)

# ---------------------------------------------------------------- 2. reference candidate state
score_cols = sorted(additive)
rows = []
for (cid, route), d in sorted(state.items()):
    hv = [v for k, v in d.items() if k in hard]
    r = OrderedDict(candidate_id=cid, route_id=route, reference_set_id=ref_set_id[route],
                    final_pass_reference=final_pass(d), reference_score=score(d),
                    reference_tier="NOT_DECLARED",
                    n_hard_pass=hv.count(PASS), n_hard_fail=hv.count(FAIL),
                    n_additive_plus1=sum(1 for k, v in d.items() if k in additive and v == "+1"))
    for rid in score_cols:
        r[f"score_{rid}"] = (1 if d.get(rid) == "+1" else 0) if rid in d else ""
    r["source_final_audit"] = "code_A6434_production_v27_v01.py"
    rows.append(r)
print("\nreference candidate-route state:")
write_tsv(os.path.join(DER, "candidate_route_reference_state_v01.tsv"), rows)

# ---------------------------------------------------------------- 3. delta_step_reference
rows = []
for route in routes:
    gates = sorted(applicable_hard[route], key=lambda r: float(hard[r]["rule_order"]))
    arriving = {cid for (cid, r) in state if r == route}
    for rid in gates:
        passed = {cid for cid in arriving if state[(cid, route)].get(rid) == PASS}
        rows.append(OrderedDict(
            route_id=route, rule_id=rid, layer_position=hard[rid]["layer_position"],
            rule_order=hard[rid]["rule_order"], n_arriving=len(arriving), n_pass=len(passed),
            n_fail=len(arriving) - len(passed),
            delta_step_reference=len(passed) - len(arriving),
            note="order-dependent sequential step effect; not the LOO quantity"))
        arriving = passed
print("\nsequential reference funnel (delta_step_reference):")
write_tsv(os.path.join(DER, "hard_gate_step_reference_v01.tsv"), rows)

# ---------------------------------------------------------------- 4. hard-gate LOO
defs, cand_rows, summ, invalid = [], [], [], []
for rid in sorted(hard, key=lambda r: float(hard[r]["rule_order"])):
    pid = f"LOO_{rid}"
    routes_for = sorted(r for r in routes if rid in applicable_hard[r])
    if not routes_for:
        continue
    defs.append(OrderedDict(
        perturbation_id=pid, perturbation_class="hard_gate_leave_one_rule_out",
        omitted_rule_id=rid, applicable_routes="; ".join(routes_for),
        reference_ruleset_id=RULESET, reference_execution_order_id="rule_order",
        description=f"omit only {rid}; every remaining hard rule stays at its reference specification",
        status="EXECUTED"))
    for route in routes_for:
        pert = set()
        ## sorted, not a bare set. Python randomises string hashing per process, so iterating a set
        ## emitted this 79,405-row table in a different ROW ORDER on every run. The content was
        ## identical as a set and the science never moved, but the file never hashed the same
        ## twice, which marked every downstream object stale on each re-run and made hash-based
        ## provenance meaningless here. Natural-key sorted so the order is the candidate order.
        for cid in sorted({c for (c, r) in state if r == route},
                          key=lambda c: (int(c) if str(c).isdigit() else 0, str(c))):
            d = state[(cid, route)]
            rf, pf = final_pass(d), final_pass(d, omit=rid)
            if pf == "PASS":
                pert.add(cid)
            changed = rf != pf
            if rf == "PASS" and pf != "PASS":
                direction = "INVALID_TRUE_TO_FALSE"
                invalid.append((cid, route, rid))
            elif changed and pf == "PASS":
                # distinguish a candidate the gate actually excluded from one whose outcome on the
                # omitted gate was never evaluable: the second is data completeness, not permissiveness
                direction = ("newly_admitted_not_evaluable"
                             if outcome(cid, route, rid) == NE else "newly_admitted")
            elif rf == "PASS":
                direction = "stable_pass"
            else:
                direction = "stable_fail"
            cand_rows.append(OrderedDict(
                candidate_id=cid, route_id=route, perturbation_id=pid, omitted_rule_id=rid,
                reference_final_pass=rf, perturbed_final_pass=pf,
                eligibility_changed=str(changed).upper(), eligibility_direction=direction,
                reference_set_id=ref_set_id[route],
                source_reference_execution="candidate_rule_outcomes_v27_v01.tsv",
                status="EXECUTED"))
        ref = ref_pass[route]
        summ.append(OrderedDict(
            route_id=route, perturbation_id=pid, omitted_rule_id=rid,
            layer_position=hard[rid]["layer_position"],
            n_final_pass_reference=len(ref), n_final_pass_perturbed=len(pert),
            delta_final_pass_LOO=len(pert) - len(ref),
            n_newly_admitted=len(pert - ref),
            n_newly_admitted_not_evaluable=sum(
                1 for c in (pert - ref) if outcome(c, route, rid) == NE),
            n_reference_preserved=len(ref & pert),
            final_pass_jaccard=round(jaccard(ref, pert), 6), status="EXECUTED"))
print("\nhard-gate LOO:")
write_tsv(os.path.join(DER, "hard_gate_loo_definition_v01.tsv"), defs)
write_tsv(os.path.join(DER, "candidate_hard_gate_loo_v01.tsv"), cand_rows)
write_tsv(os.path.join(DER, "hard_gate_loo_summary_v01.tsv"), summ)
assert not invalid, f"INVARIANT BROKEN: {len(invalid)} TRUE->FALSE transition(s) under pure gate removal"
print("  invariant: no TRUE -> FALSE transition under pure gate removal (0 found)")

# ---------------------------------------------------------------- 5. reference additive execution
rows = []
for route in routes:
    pop = ref_pass[route]
    for rid in sorted(applicable_add[route], key=lambda r: float(additive[r]["rule_order"])):
        n1 = sum(1 for cid in pop if state[(cid, route)].get(rid) == "+1")
        n0 = len(pop) - n1
        rows.append(OrderedDict(
            route_id=route, reference_set_id=ref_set_id[route], rule_id=rid,
            layer_position=additive[rid]["layer_position"], n_final_pass_reference=len(pop),
            n_zero=n0, pct_zero=round(100 * n0 / len(pop), 2) if pop else "",
            n_plus1=n1, pct_plus1=round(100 * n1 / len(pop), 2) if pop else "",
            status="EXECUTED"))
print("\nreference additive execution on the fixed hard-gate reference set:")
write_tsv(os.path.join(DER, "additive_reference_execution_v01.tsv"), rows)

rows = []
for route in routes:
    pop = ref_pass[route]
    dist = defaultdict(int)
    for cid in pop:
        dist[score(state[(cid, route)])] += 1
    for s in sorted(dist):
        rows.append(OrderedDict(
            route_id=route, reference_set_id=ref_set_id[route], additive_score=s,
            n_candidates=dist[s],
            pct_candidates=round(100 * dist[s] / len(pop), 2) if pop else "",
            n_additive_applicable=len(applicable_add[route])))
write_tsv(os.path.join(DER, "additive_score_distribution_v01.tsv"), rows)

# ---------------------------------------------------------------- 6. additive LOCO
defs, cand_rows, summ = [], [], []
for rid in sorted(additive, key=lambda r: float(additive[r]["rule_order"])):
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
        rs, ps = [], []
        changed = 0
        for cid in pop:
            d = state[(cid, route)]
            a, b = score(d), score(d, omit=rid)
            rs.append(a); ps.append(b)
            ch = a != b
            changed += ch
            cand_rows.append(OrderedDict(
                candidate_id=cid, route_id=route, perturbation_id=pid,
                reference_set_id=ref_set_id[route], reference_score=a, perturbed_score=b,
                score_delta=b - a, score_changed=str(ch).upper(),
                reference_tier="NOT_DECLARED", perturbed_tier="NOT_DECLARED",
                tier_changed="NOT_APPLICABLE"))
        rho = spearman(rs, ps)
        summ.append(OrderedDict(
            route_id=route, perturbation_id=pid, omitted_rule_id=rid,
            layer_position=additive[rid]["layer_position"],
            reference_set_id=ref_set_id[route], n_final_pass_reference=len(pop),
            n_scores_changed=changed,
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
print("\nadditive LOCO on the fixed reference population:")
write_tsv(os.path.join(DER, "additive_perturbation_definition_v01.tsv"), defs)
write_tsv(os.path.join(DER, "candidate_additive_perturbation_v01.tsv"), cand_rows)
write_tsv(os.path.join(DER, "additive_perturbation_summary_v01.tsv"), summ)

bad = [r for r in cand_rows if int(r["score_delta"]) > 0]
assert not bad, f"INVARIANT BROKEN: {len(bad)} positive score_delta under pure component removal"
print("  invariant: score_delta <= 0 everywhere under pure component removal")
print("  invariant: hard final_pass fixed by construction (the population is the reference set)")

if _unrecorded:
    print(f"\nWARNING: {len(_unrecorded)} output(s) carry no produced_from record, so `research_os "
          f"stale` will report them UNRECORDED:")
    for x in _unrecorded:
        print(f"  {x}")
else:
    print("\nprovenance: every output carries a produced_from record "
          "(.research/produced_from/<logical_id>.yaml)")
