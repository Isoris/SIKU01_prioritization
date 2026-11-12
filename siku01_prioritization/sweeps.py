"""Sensitivity sweeps: move ONE threshold at a time and count who still satisfies that single criterion.

This is not a re-ranking and it is not eligibility. A sweep asks, for one rule, how many candidates satisfy that rule at a shifted
threshold and how much that set overlaps the set at the reference threshold (Jaccard). Eligibility under a removed gate is the
leave-one-out analysis (perturbation.py); the two answer different questions.

The sweep values are fixed before any outcome is looked at:

    rules/ST_A6434_03_parameter_sweep_contract_v02.tsv   the plan: which rules are swept, how many steps, in which direction
    rules/sweep_grid_values_v02.tsv                      the step values of seven rules, chosen from the measurement scale
    conservation (M0_CONSERVATION)                       five values computed here from the shape of the conservation
                                                         distribution alone (see conservation_sweep_values)

Population: a rule that applies to all routes is swept on the 1,527 entry orthogroups (M0_ENTRY_REFERENCE); a route-specific rule is
swept on the candidates of each of its routes.

Tables written
    ST_A6434_03_parameter_sweeps_v02.tsv   the plan with every value resolved (56 rows)
    hard_gate_sweep_execution_v01.tsv      one row per rule, sweep value and population (121 rows)
    hard_gate_sweep_summary_v01.tsv        one row per rule and population (16 rows)
"""
from collections import OrderedDict, defaultdict

import numpy as np

from . import layout
from .rules import evaluate, reference_population
from .tables import read_tsv, write_tsv

CONSERVATION_COLUMN = "conservation__median_conservation_hnorm"
# Provenance labels written into the tables. They are kept exactly as in the deposited tables, where they name the files of the
# deposit's folder layout (the candidate frame, and the resolved sweep table).
SOURCE_POPULATION = "04_tables/candidate_data_v02.tsv"
SOURCE_CONTRACT = "01_analysis_output/derived/ST_A6434_03_parameter_sweeps_v02.tsv"
VALUE_SOURCE = "frozen_pre_execution_2026-10-06"


def _kde_reflect(data, bw, grid):
    """Gaussian kernel density with reflection at 0 and 1, so the mass piled up at H.norm = 1 is not smoothed away."""
    xs = np.concatenate([data, -data, 2 - data])
    dens = np.exp(-0.5 * ((grid[:, None] - xs[None, :]) / bw) ** 2).sum(1)
    return dens / (data.size * bw * np.sqrt(2 * np.pi))


def conservation_sweep_values(frame):
    """Five conservation thresholds, from the distribution of the predictor only (no pass count is used).

    Normalised conservation is bimodal: most orthogroups sit at 1.0, a minority spread below. The density is estimated (Gaussian
    kernel, Silverman bandwidth), the dip (antimode) just left of the conserved peak is located, and the interval from the antimode
    to 1.0 is cut at 0, 20, 40, 60 and 80 % of its width.
    """
    ref = list(reference_population(frame).values())
    assert len(ref) == layout.N_REFERENCE, f"reference population is {len(ref)}, expected {layout.N_REFERENCE}"
    x = np.array([float(r[CONSERVATION_COLUMN]) for r in ref if r[CONSERVATION_COLUMN] not in ("", "NA")])
    n = x.size
    sd = x.std(ddof=1)
    iqr = float(np.subtract(*np.percentile(x, [75, 25])))
    # Silverman's rule; the IQR is 0 because most values are exactly 1, so the rule falls back to the standard deviation.
    bw = 0.9 * min(sd, iqr / 1.349 if iqr > 0 else sd) * n ** (-1 / 5)
    bw_scott = sd * n ** (-1 / 5)
    grid = np.arange(0, 1.0 + 1e-12, 0.0005)

    def antimode(b):
        d = _kde_reflect(x, b, grid)
        assert d[-1] > d[-2], "no density peak at H.norm = 1.0"
        minima = [grid[i] for i in range(1, len(d) - 1) if d[i] <= d[i - 1] and d[i] < d[i + 1]]
        return max(minima)   # the dip nearest to the conserved peak

    am, am_scott = float(antimode(bw)), float(antimode(bw_scott))
    width = 1.0 - am
    note = (f"KDE gaussian w/ boundary reflection, Silverman bw={bw:.6f} (IQR=0 under the "
            f"H.norm=1 plateau so the rule resolves to sd), grid step 0.0005; endpoint mode at "
            f"1.0; nearest antimode to its left {am:.4f}; Scott bw={bw_scott:.6f} gives "
            f"{am_scott:.4f} (delta {abs(am - am_scott):.4f} on the score axis)")
    values = {f"HNORM_KDE_F{int(f * 100):02d}": (am + f * width, f"antimode {am:.4f} + {f:.1f}x(1.0-antimode); {note}")
              for f in (0.0, 0.2, 0.4, 0.6, 0.8)}
    return values, dict(antimode=am, antimode_scott=am_scott, bandwidth=float(bw), n=int(n))


def resolve_plan(frame, rules_dir=layout.RULES):
    """Fill every pending value of the sweep plan. Uses the measurement scale and the predictor distribution only."""
    plan = read_tsv(rules_dir / layout.SWEEP_CONTRACT)
    grid = {(g["rule_id"], g["sweep_id"]): (g["sweep_value"], g["predeclared_rationale"])
            for g in read_tsv(rules_dir / layout.SWEEP_GRID)}
    cons, kde = conservation_sweep_values(frame)
    for r in plan:
        if r["resolution_status"] == "RESOLVED" and r["sweep_value"]:
            continue
        sid, rid = r["sweep_id"], r["rule_id"]
        if r["is_reference"].strip().upper() == "TRUE" and not r["sweep_value"]:
            r["sweep_value"] = r["reference_value"]   # the reference row of a two-sided rule
            r["value_source"] = "canonical_reference"
            r["resolution_status"] = "RESOLVED"
            continue
        if rid == "M0_CONSERVATION" and sid in cons:
            val, why = cons[sid]
            r["sweep_value"] = f"{val:.6f}"
            r["derivation_method"] = "KDE conserved-mode antimode; equal score-axis fractions, not member quantiles"
        elif (rid, sid) in grid:
            r["sweep_value"], why = grid[(rid, sid)]
        else:
            raise ValueError(f"the sweep plan has a pending row with no value: {rid} / {sid}")
        r["value_source"] = VALUE_SOURCE
        r["predeclared_rationale"] = why
        r["resolution_status"] = "RESOLVED"
        r["reference_population"] = layout.REFERENCE_POPULATION
        r["n_reference_population"] = str(layout.N_REFERENCE)
    ids = [(r["rule_id"], r["sweep_id"]) for r in plan]
    assert len(ids) == len(set(ids)), "rule_id x sweep_id is not unique in the sweep plan"
    assert all(r["resolution_status"] == "RESOLVED" for r in plan), "sweep rows still pending"
    return plan, kde


def _jaccard(a, b):
    u = a | b
    return (len(a & b) / len(u)) if u else 1.0


def execute(plan, rules, frame):
    """Evaluate every sweep value. Returns (execution rows, summary rows); stamps execution_status on the plan."""
    by_id = {r["rule_id"]: r for r in rules}
    ref_pop = reference_population(frame)
    by_route = defaultdict(OrderedDict)
    for r in frame:
        by_route[r["route"]][r["pangenome_id"]] = r
    # the routes of a route-specific rule; a rule on all routes has no entry and is swept on the reference population
    route_of = {}
    for rid, r in by_id.items():
        raw = (r.get("routes") or "").strip()
        if raw and raw.lower() != "all":
            route_of[rid] = [x.strip() for x in raw.split(";") if x.strip()]

    rows, summ, done = [], [], set()
    for rid in sorted({s["rule_id"] for s in plan}):
        mine = [s for s in plan if s["rule_id"] == rid]
        var, op = mine[0]["variable"], mine[0]["operator"]
        assert rid in by_id, f"{rid} is in the sweep plan but not in the rule table"
        assert (var, op) == (by_id[rid]["variable"], by_id[rid]["operator"]), f"{rid}: the plan and the rule table disagree"
        assert op != "==", f"{rid}: an equality rule cannot be swept"
        bound = route_of.get(rid)
        if bound:
            unknown = [rt for rt in bound if rt not in by_route]
            assert not unknown, f"{rid}: routes {unknown} are not in the candidate frame"
            pops = [(rt, by_route[rt]) for rt in bound]
        else:
            pops = [(layout.REFERENCE_POPULATION, ref_pop)]

        for pop_name, pop in pops:
            ref_row = next((s for s in mine if s["is_reference"].strip().upper() == "TRUE"), None)
            assert ref_row is not None, f"{rid}: the plan has no reference row"
            sets, ne = {}, {}
            for s in mine:
                keep, notev = set(), 0
                for pid, r in pop.items():
                    v = evaluate(r.get(var), op, s["sweep_value"])
                    if v is None:
                        notev += 1   # a missing measurement is not evaluable; it is not counted as a failure
                    elif v:
                        keep.add(pid)
                sets[s["sweep_id"]], ne[s["sweep_id"]] = keep, notev
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
                    jaccard_vs_reference=round(_jaccard(ref_set, k), 6),
                    n_only_reference=len(ref_set - k), n_only_sweep=len(k - ref_set),
                    source_population=SOURCE_POPULATION, source_contract=SOURCE_CONTRACT,
                    status="EXECUTED"))
                done.add((rid, sid))
            ns = [len(sets[s["sweep_id"]]) for s in mine]
            js = [_jaccard(ref_set, sets[s["sweep_id"]]) for s in mine if s["is_reference"].strip().upper() != "TRUE"]
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

    for s in plan:
        if (s["rule_id"], s["sweep_id"]) in done:
            s["execution_status"] = "EXECUTED"
    not_done = [(s["rule_id"], s["sweep_id"]) for s in plan if (s["rule_id"], s["sweep_id"]) not in done]
    assert not not_done, f"sweeps in the plan that were not executed: {not_done}"
    return rows, summ


def run(rules, frame, out_dir, rules_dir=layout.RULES):
    plan, kde = resolve_plan(frame, rules_dir)
    rows, summ = execute(plan, rules, frame)
    write_tsv(out_dir / layout.T_SWEEPS, plan)
    write_tsv(out_dir / layout.T_SWEEP_EXECUTION, rows)
    write_tsv(out_dir / layout.T_SWEEP_SUMMARY, summ)
    return dict(sweep_values=len(plan), rules_swept=len({s["rule_id"] for s in plan}), execution_rows=len(rows), **kde)
