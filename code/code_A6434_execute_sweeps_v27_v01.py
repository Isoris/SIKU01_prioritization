#!/usr/bin/env python3
"""Execute the frozen parameter sweeps: per rule x sweep_id, who satisfies the criterion.

The contract was frozen BEFORE any eligibility outcome was known (EXE_0002/EXE_0003), which is what
makes this a sensitivity analysis rather than a search for a threshold that gives a nicer answer.
This script only executes it: it reads the resolved sweep values and reports, for each one, how many
candidates satisfy that single criterion and how much that set overlaps the reference set.

WHAT THIS IS NOT
    It is not a re-ranking and it is not eligibility. A sweep moves ONE criterion and asks how many
    candidates satisfy THAT criterion; final eligibility is the intersection of all applicable hard
    gates and is perturbed by the LOO analysis instead. The two answer different questions and their
    numbers are not interchangeable.

GRAIN  rule_id x sweep_id x population
POPULATION
    A sweep on a shared rule (M0, M2P) is evaluated on the M0-entry reference population, one row per
    pangenome_id, n = 1,527 — the population the contract stamped. A sweep on a route-specific rule
    is evaluated on the candidates of that route, because the criterion only exists there.
"""
import csv, os, sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _provenance import record_output

CAP = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DER = os.path.join(CAP, "01_analysis_output", "derived")
BRAIN = os.path.join(CAP, "capsule_brain")
SWEEPS = os.path.join(DER, "ST_A6434_03_parameter_sweeps_v02.tsv")
CAND = os.path.join(CAP, "04_tables", "candidate_data_v02.tsv")
RULES = os.path.join(BRAIN, "ranking_rules_v27.tsv")
MISSING = {"", "NA", "NaN", "nan", "None", "NULL", "-"}


def read(p):
    with open(p, newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh, delimiter="\t")]


def num(v):
    if v is None or str(v).strip() in MISSING:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def satisfies(op, observed, target):
    """One criterion, one candidate. None when the measurement is absent: a missing measurement is
    not negative evidence, so it is counted as not evaluable rather than as a failure."""
    if observed is None:
        return None
    if op == "BETWEEN":
        lo, hi = [float(x) for x in str(target).split(";")]
        return lo <= observed <= hi
    t = num(target)
    if t is None:
        return None
    return {">": observed > t, ">=": observed >= t, "<": observed < t,
            "<=": observed <= t, "==": observed == t}[op]


def jaccard(a, b):
    u = a | b
    return (len(a & b) / len(u)) if u else 1.0


sweeps = read(SWEEPS)
cand = read(CAND)
rules = {r["rule_id"]: r for r in read(RULES)}

# the stamped reference population: one row per pangenome_id, in first-seen order
ref_pop = OrderedDict()
for r in cand:
    ref_pop.setdefault(r["pangenome_id"], r)
by_route = defaultdict(OrderedDict)
for r in cand:
    by_route[r["route"]][r["pangenome_id"]] = r

N_REF = len(ref_pop)
routes = sorted(by_route)

# Which routes a rule applies to, read from the declaration's `routes` column.
#
# `routes` is the authoritative field: it holds either "all" or explicit route ids
# ("pdna_tilapia; pdna_zebrafish"). `route_binding` is NOT a route — it is a grouping label
# ("common_pdna") that names a family of routes sharing an implementation. Reading route_binding as
# a route id resolves M2_CDS_LEN to a route that does not exist, and an earlier version of this
# script then produced ZERO rows for that rule without saying so. Any route named here must exist in
# the candidate table, and every swept rule must produce rows; both are asserted below, because a
# silently skipped rule is the worst outcome available.
route_of = {}
for rid, r in rules.items():
    raw = (r.get("routes") or "").strip()
    if raw and raw.lower() not in ("all", "shared", "any"):
        route_of[rid] = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]

rows, summ = [], []
exec_status = {}

for rid in sorted({s["rule_id"] for s in sweeps}):
    mine = [s for s in sweeps if s["rule_id"] == rid]
    var = mine[0]["variable"]
    op = mine[0]["operator"]
    # A swept rule that is not in the declaration must stop the run. Treating it as shared is the
    # silent fallback that produced wrong populations when the frozen contract still carried the
    # retired M2P_/M2D_ ids: route_of.get() missed, and the rule was evaluated on the M0-entry
    # population as though it had no route binding.
    assert rid in rules, (f"{rid} is in the frozen sweep contract but not in "
                          f"capsule_brain/ranking_rules_v27.tsv. If this is a retired identifier, "
                          f"regenerate the frozen contract from the brain (the freeze script) "
                          f"instead of letting it default to the shared population. "
                          f"Crosswalk: capsule_brain/rule_id_crosswalk_v01.tsv")
    bound = route_of.get(rid)
    if bound:
        unknown = [rt for rt in bound if rt not in by_route]
        assert not unknown, (f"{rid}: declared routes {unknown} are not in the candidate table "
                             f"(available: {sorted(by_route)}). A route that does not resolve must "
                             f"stop the run, never silently drop the rule.")
        pops = [(rt, by_route[rt]) for rt in bound]
    else:
        pops = [("M0_ENTRY_REFERENCE", ref_pop)]
    assert pops, f"{rid}: no population resolved; the rule would be skipped silently"

    for pop_name, pop in pops:
        ref_row = next((s for s in mine if s["is_reference"].strip().upper() == "TRUE"), None)
        assert ref_row is not None, f"{rid}: the contract declares no reference sweep row"

        sets, ne = {}, {}
        for s in mine:
            keep, notev = set(), 0
            for pid, r in pop.items():
                v = satisfies(op, num(r.get(var)), s["sweep_value"])
                if v is None:
                    notev += 1
                elif v:
                    keep.add(pid)
            sets[s["sweep_id"]] = keep
            ne[s["sweep_id"]] = notev

        ref_set = sets[ref_row["sweep_id"]]
        for s in mine:
            sid = s["sweep_id"]
            k = sets[sid]
            rows.append(OrderedDict(
                rule_id=rid, layer_position=s["layer_position"], sweep_id=sid,
                sweep_family=s["sweep_family"], population=pop_name, n_population=len(pop),
                variable=var, operator=op,
                reference_value=s["reference_value"], sweep_value=s["sweep_value"],
                is_reference=s["is_reference"],
                n_satisfying=len(k), n_not_evaluable=ne[sid],
                n_satisfying_reference=len(ref_set),
                delta_n_satisfying=len(k) - len(ref_set),
                jaccard_vs_reference=round(jaccard(ref_set, k), 6),
                n_only_reference=len(ref_set - k), n_only_sweep=len(k - ref_set),
                source_population="04_tables/candidate_data_v02.tsv",
                source_contract="01_analysis_output/derived/ST_A6434_03_parameter_sweeps_v02.tsv",
                status="EXECUTED"))
            exec_status[(rid, sid)] = "EXECUTED"

        ns = [len(sets[s["sweep_id"]]) for s in mine]
        js = [jaccard(ref_set, sets[s["sweep_id"]]) for s in mine
              if s["is_reference"].strip().upper() != "TRUE"]
        summ.append(OrderedDict(
            rule_id=rid, layer_position=mine[0]["layer_position"],
            sweep_family=mine[0]["sweep_family"], population=pop_name, n_population=len(pop),
            variable=var, operator=op, n_sweeps=len(mine),
            reference_sweep_id=ref_row["sweep_id"], reference_value=ref_row["sweep_value"],
            n_satisfying_reference=len(ref_set),
            n_satisfying_min=min(ns), n_satisfying_max=max(ns),
            n_satisfying_range=f"{min(ns)}-{max(ns)}",
            jaccard_min=round(min(js), 6) if js else "", jaccard_max=round(max(js), 6) if js else "",
            jaccard_range=f"{min(js):.3f}-{max(js):.3f}" if js else "",
            n_not_evaluable_reference=ne[ref_row["sweep_id"]],
            status="EXECUTED"))

# stamp execution_status back onto the frozen contract: the resolved values are untouched
for s in sweeps:
    st = exec_status.get((s["rule_id"], s["sweep_id"]))
    if st:
        s["execution_status"] = st
with open(SWEEPS, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(sweeps[0].keys()), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(sweeps)

OUT_D = os.path.join(DER, "hard_gate_sweep_execution_v01.tsv")
OUT_S = os.path.join(DER, "hard_gate_sweep_summary_v01.tsv")
for p, rs in ((OUT_D, rows), (OUT_S, summ)):
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rs[0].keys()), delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(rs)
    print(f"  {os.path.relpath(p, CAP)}  ({len(rs)} rows)")

INPUTS = ["04_tables/candidate_data_v02.tsv", "capsule_brain/ranking_rules_v27.tsv",
          "01_analysis_output/derived/ST_A6434_03_parameter_sweeps_v02.tsv"]
CODE = ["02_code/code_A6434_execute_sweeps_v27_v01.py", "02_code/_provenance.py"]
for p in (OUT_D, OUT_S, SWEEPS):
    record_output(CAP, p, INPUTS if p != SWEEPS else
                  ["04_tables/candidate_data_v02.tsv",
                   "capsule_brain/ST_A6434_03_parameter_sweep_contract_v02.tsv"], CODE)

# the reference sweep row must reproduce the production gate outcome, or the sweep is not measuring
# the same criterion the rule applies
print(f"\nreference population n = {N_REF}; routes {', '.join(routes)}")
print(f"\n{'rule':<20}{'population':<22}{'ref N':>7}{'range':>14}{'jaccard':>16}")
for s in summ:
    print(f"{s['rule_id']:<20}{s['population']:<22}{s['n_satisfying_reference']:>7}"
          f"{s['n_satisfying_range']:>14}{s['jaccard_range'] or 'n/a':>16}")
missing = [(s["rule_id"], s["sweep_id"]) for s in sweeps
           if (s["rule_id"], s["sweep_id"]) not in exec_status]
print(f"\nexecution_status stamped EXECUTED on {len(exec_status)} of {len(sweeps)} contract rows")
assert not missing, ("the following frozen sweeps were NOT executed, so the contract and the "
                     f"execution disagree: {missing}")
swept_rules = {s["rule_id"] for s in sweeps}
produced = {r["rule_id"] for r in rows}
assert swept_rules == produced, f"rules with no executed row: {sorted(swept_rules - produced)}"
print(f"every one of the {len(swept_rules)} swept rules produced rows")
