"""Reader-friendly views of a run: the final-pass candidates of each route, and one folder per route.

Nothing is computed here. Every value is copied from the result tables in tables/ (which are the ones checked against the deposit);
these files only arrange them so that one route can be read on its own.

    shortlists/
        final_pass_summary.tsv        one row per route: candidates, PASS, FAIL, NOT_EVALUABLE
        final_pass_<route>.tsv        the PASS candidates of the route with the values each rule read
        final_pass_all_routes.tsv     every orthogroup that passes on at least one route, with its state on all six
    routes/<route>/
        candidates.tsv                all 1,527 orthogroups on this route: state, failed gates, every rule outcome and value
        gates.tsv                     the hard gates of the route: threshold, PASS / FAIL / NOT_EVALUABLE, the sequential funnel,
                                      and the effect of removing the gate
        additive_components.tsv       the additive components among the PASS candidates, and the effect of removing each
        threshold_sweeps.tsv          the threshold sweeps of the rules that apply to this route

Within a shortlist the candidates are sorted by additive score (highest first), then by pangenome_id. The additive score counts
favourable properties; it is not a ranking of vaccine potential.
"""
from collections import OrderedDict, defaultdict

from . import layout
from .rules import FAIL, NOT_EVALUABLE, PASS, executable, routes_of, threshold_of
from .tables import read_tsv, write_tsv


def _identity(row):
    return OrderedDict(pangenome_id=row["pangenome_id"], orthogroup_label=row["m0__orthogroup_label"],
                       gene_name=row["gene_name"], siku01_locus_tag=row["literature__representative_locus_tag"])


def write(out_dir, rules, symbol, frame, tables_dir):
    outcomes = read_tsv(tables_dir / layout.T_OUTCOMES)
    states = {(s["pangenome_id"], s["route"]): s for s in read_tsv(tables_dir / layout.T_STATE)}
    counts = {(c["rule_id"], c["route"]): c for c in read_tsv(tables_dir / layout.T_COUNTS)}
    funnel = {(f["rule_id"], f["route_id"]): f for f in read_tsv(tables_dir / layout.T_STEP_REFERENCE)}
    loo = {(x["omitted_rule_id"], x["route_id"]): x for x in read_tsv(tables_dir / layout.T_LOO_SUMMARY)}
    add_ref = {(x["rule_id"], x["route_id"]): x for x in read_tsv(tables_dir / layout.T_ADDITIVE_REFERENCE)}
    loco = {(x["omitted_rule_id"], x["route_id"]): x for x in read_tsv(tables_dir / layout.T_LOCO_SUMMARY)}
    sweep_rows = read_tsv(tables_dir / layout.T_SWEEP_EXECUTION)
    by_candidate = defaultdict(dict)   # (pangenome_id, route) -> {rule_id: outcome row}
    for o in outcomes:
        by_candidate[(o["pangenome_id"], o["route"])][o["rule_id"]] = o
    info = {}
    for r in frame:
        info.setdefault(r["pangenome_id"], r)
    order = list(info)   # numeric pangenome_id order of the assembled table
    todo = executable(rules)

    sdir = out_dir / "shortlists"
    sdir.mkdir(exist_ok=True)
    summary, n_files = [], 0
    for route in layout.ROUTES:
        mine = [r for r in todo if route in routes_of(r, layout.ROUTES)]
        hard = [r for r in mine if r["role"] == "hard"]
        additive = [r for r in mine if r["role"] == "additive"]
        variables = list(OrderedDict.fromkeys(r["variable"] for r in mine))
        rdir = out_dir / "routes" / route
        rdir.mkdir(parents=True, exist_ok=True)

        # routes/<route>/candidates.tsv : everything about every orthogroup on this route
        rows = []
        for pid in order:
            s, oc = states[(pid, route)], by_candidate[(pid, route)]
            row = _identity(info[pid])
            row.update(route=route, final_pass=s["final_pass"],
                       n_hard_gates=s["n_hard_applicable"], n_hard_pass=s["n_hard_pass"], n_hard_fail=s["n_hard_fail"],
                       n_hard_not_evaluable=s["n_hard_not_evaluable"],
                       failed_gates="; ".join(r["rule_id"] for r in hard if oc[r["rule_id"]]["outcome"] == FAIL),
                       not_evaluable_gates="; ".join(r["rule_id"] for r in hard if oc[r["rule_id"]]["outcome"] == NOT_EVALUABLE),
                       additive_score=s["additive_score"], n_additive_components=s["n_additive_applicable"])
            for r in mine:
                row[r["rule_id"]] = oc[r["rule_id"]]["outcome"]
            for v in variables:
                row[v] = info[pid].get(v, "")
            rows.append(row)
        write_tsv(rdir / "candidates.tsv", rows)

        # shortlists/final_pass_<route>.tsv : the PASS candidates, highest additive score first
        keep = ["pangenome_id", "orthogroup_label", "gene_name", "siku01_locus_tag", "route", "final_pass", "additive_score",
                "n_additive_components"] + [r["rule_id"] for r in additive] + variables
        passed = [OrderedDict((k, r[k]) for k in keep) for r in rows if r["final_pass"] == PASS]
        passed.sort(key=lambda r: (-int(r["additive_score"]), int(r["pangenome_id"])))
        write_tsv(sdir / f"final_pass_{route}.tsv", passed, fields=keep)

        # routes/<route>/gates.tsv
        grows = []
        for r in hard:
            c, f, x = counts[(r["rule_id"], route)], funnel[(r["rule_id"], route)], loo[(r["rule_id"], route)]
            thr, sym = threshold_of(r, symbol)
            grows.append(OrderedDict(
                route=route, rule_id=r["rule_id"], position=r["layer_position"], name=r["manuscript_name"],
                expression=r["expression"], variable=r["variable"], operator=r["operator"], threshold=thr, threshold_symbol=sym or "",
                unit=r["unit"], n_candidates=c["n_evaluated"], n_pass=c["n_pass"], n_fail=c["n_fail"],
                n_not_evaluable=c["n_not_evaluable"],
                funnel_n_arriving=f["n_arriving"], funnel_n_pass=f["n_pass"],
                final_pass_reference=x["n_final_pass_reference"], final_pass_without_this_gate=x["n_final_pass_perturbed"],
                newly_admitted_without_this_gate=x["n_newly_admitted"]))
        write_tsv(rdir / "gates.tsv", grows)

        # routes/<route>/additive_components.tsv
        arows = []
        for r in additive:
            c, a, x = counts[(r["rule_id"], route)], add_ref[(r["rule_id"], route)], loco[(r["rule_id"], route)]
            thr, sym = threshold_of(r, symbol)
            arows.append(OrderedDict(
                route=route, rule_id=r["rule_id"], position=r["layer_position"], name=r["manuscript_name"],
                expression=r["expression"], variable=r["variable"], operator=r["operator"], threshold=thr, threshold_symbol=sym or "",
                unit=r["unit"], n_candidates=c["n_evaluated"], n_plus1_all_candidates=c["n_plus1"],
                n_final_pass=a["n_final_pass_reference"], n_plus1_final_pass=a["n_plus1"], pct_plus1_final_pass=a["pct_plus1"],
                scores_changed_without_this_component=x["n_scores_changed"]))
        write_tsv(rdir / "additive_components.tsv", arows)

        # routes/<route>/threshold_sweeps.tsv : sweeps of this route's rules (on the route, or on the reference population)
        ids = {r["rule_id"] for r in mine}
        srows = [s for s in sweep_rows if s["rule_id"] in ids and s["population"] in (route, layout.REFERENCE_POPULATION)]
        write_tsv(rdir / "threshold_sweeps.tsv", srows, fields=list(sweep_rows[0].keys()))

        n = {k: sum(1 for r in rows if r["final_pass"] == k) for k in (PASS, FAIL, NOT_EVALUABLE)}
        summary.append(OrderedDict(route=route, description=layout.ROUTE_LABEL[route], n_candidates=len(rows),
                                   n_final_pass=n[PASS], n_fail=n[FAIL], n_not_evaluable=n[NOT_EVALUABLE],
                                   hard_gates="; ".join(r["rule_id"] for r in hard),
                                   additive_components="; ".join(r["rule_id"] for r in additive),
                                   shortlist=f"shortlists/final_pass_{route}.tsv"))
        n_files += 5
    write_tsv(sdir / "final_pass_summary.tsv", summary)

    # shortlists/final_pass_all_routes.tsv
    rows = []
    for pid in order:
        on = [rt for rt in layout.ROUTES if states[(pid, rt)]["final_pass"] == PASS]
        if not on:
            continue
        row = _identity(info[pid])
        row.update(n_routes_final_pass=len(on), routes_final_pass="; ".join(on))
        for rt in layout.ROUTES:
            row[f"final_pass_{rt}"] = states[(pid, rt)]["final_pass"]
        for rt in layout.ROUTES:
            row[f"additive_score_{rt}"] = states[(pid, rt)]["additive_score"]
        rows.append(row)
    write_tsv(sdir / "final_pass_all_routes.tsv", rows)

    _report(out_dir, summary, rules, symbol, len(rows), len(order))
    return dict(files=n_files + 3, orthogroups_passing_any_route=len(rows),
                final_pass={s["route"]: s["n_final_pass"] for s in summary})


def _report(out_dir, summary, rules, symbol, n_any, n_orthogroups):
    L = ["# SIKU01 candidate prioritization: run report", "",
         f"Rule set `{layout.RULESET_ID}`: {sum(r['role'] == 'hard' for r in rules)} hard gates and "
         f"{sum(r['role'] == 'additive' for r in rules)} additive components, applied to {n_orthogroups:,} core orthogroups on "
         f"{len(layout.ROUTES)} routes ({n_orthogroups * len(layout.ROUTES):,} candidates).", "",
         "## Final pass per route", "",
         "| route | what | candidates | final pass | fail | not evaluable |", "|---|---|---:|---:|---:|---:|"]
    for s in summary:
        L.append(f"| `{s['route']}` | {s['description']} | {s['n_candidates']:,} | **{s['n_final_pass']:,}** | {s['n_fail']:,} | "
                 f"{s['n_not_evaluable']:,} |")
    L += ["", f"{n_any:,} orthogroups pass on at least one route (`shortlists/final_pass_all_routes.tsv`).", "",
          "A candidate is *final pass* on a route when every hard gate of that route is PASS. *Not evaluable* means no gate "
          "failed but at least one could not be evaluated because its value is missing. The additive score counts favourable "
          "properties and never changes the final pass.", "",
          "## The rules", "", "| position | rule | role | routes | condition | threshold used |", "|---|---|---|---|---|---|"]
    for r in rules:
        if r["role"] == "declaration":
            continue
        thr, sym = threshold_of(r, symbol)
        used = f"{thr} ({sym})" if sym else str(thr).replace(";", " to ")
        L.append(f"| {r['layer_position']} | {r['manuscript_name']} | {r['role']} | {r['routes']} | `{r['expression']}` | {used} |")
    L += ["", "## Files", "",
          "- `tables/`: the 21 result tables (the tables of the deposit).",
          "- `shortlists/`: `final_pass_<route>.tsv` per route, `final_pass_all_routes.tsv`, `final_pass_summary.tsv`.",
          "- `routes/<route>/`: `candidates.tsv` (all orthogroups with every rule outcome), `gates.tsv`, "
          "`additive_components.tsv`, `threshold_sweeps.tsv`.",
          "- `run_log.json`: versions, steps and the checksum of every table.", ""]
    (out_dir / "REPORT.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
