"""Run the prioritization from the frozen input tables to the result tables and the per-route shortlists.

    results/<run>/
        tables/        the 21 result tables (the same files as expected/tables/ when the run reproduces the deposit)
        shortlists/    final-pass candidates per route, and one overview across the routes
        routes/<route>/  everything about one route in one folder
        REPORT.md      what was run and what came out, in plain words
        run_log.json   command, versions, steps, checksum of every table
"""
import json
import platform
import sys
import time
from importlib import metadata

from . import __version__, inputs, layout, perturbation, ranking, rules, shortlists, sweeps
from .tables import sha256_file


def _version(pkg):
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def run(out_dir, say=print, inputs_dir=layout.INPUTS, rules_dir=layout.RULES):
    """Run every step into out_dir. Returns the run log (a dict). Raises on the first problem."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tdir = out_dir / "tables"
    tdir.mkdir(exist_ok=True)
    log = dict(pipeline="SIKU01 candidate prioritization", pipeline_version=__version__, ruleset=layout.RULESET_ID,
               command=sys.argv, started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               versions=dict(python=platform.python_version(), pandas=_version("pandas"), numpy=_version("numpy")),
               platform=platform.platform(), steps=[])

    clock = [time.time()]

    def step(name, what):
        if log["steps"]:
            say(f"      done ({time.time() - clock[0]:.1f} s)")
        clock[0] = time.time()
        say(f"[{len(log['steps']) + 1}/7] {what}")
        log["steps"].append(dict(step=name))
        return log["steps"][-1]

    s = step("check_inputs", "checking the input tables against inputs/CHECKSUMS.tsv")
    rows, problems = inputs.check_inputs(inputs_dir)
    frozen = [r for r in rows if r["role"] == "frozen_table"]
    s.update(files=len(rows), frozen_tables=len(frozen), frozen_tables_ok=sum(r["status"] == "OK" for r in frozen), problems=problems)
    say(f"      {s['frozen_tables_ok']} of {len(frozen)} frozen tables and {sum(r['status'] == 'OK' for r in rows) - s['frozen_tables_ok']} "
        f"of {len(rows) - len(frozen)} other inputs identical to their recorded checksum")
    if problems:
        raise RuntimeError("the inputs are not the recorded ones:\n  " + "\n  ".join(problems))

    s = step("load_rules", f"reading the rules ({layout.RULE_TABLE})")
    rule_table, symbol = rules.load_rules(rules_dir)
    s.update(rules=len(rule_table), hard=sum(r["role"] == "hard" for r in rule_table),
             additive=sum(r["role"] == "additive" for r in rule_table))
    say(f"      {s['rules']} rules: {s['hard']} hard gates, {s['additive']} additive components, 1 declaration")

    s = step("build_literature", "literature evidence per orthogroup")
    s.update(inputs.build_literature(tdir / layout.T_LITERATURE, inputs_dir))
    say(f"      {s['rows']} orthogroups; {s['with_identifier']} with a PubMed reference, {s['with_vaccine_reference']} with a curated "
        f"vaccine reference")

    s = step("assemble", "joining the input tables into one row per orthogroup")
    s.update(inputs.assemble_ranking_inputs(tdir / layout.T_LITERATURE, tdir / layout.T_RANKING_INPUTS,
                                            tdir / layout.T_INPUT_AUDIT, tdir / layout.T_EXCLUSIONS, inputs_dir))
    frame = inputs.build_frame(tdir / layout.T_RANKING_INPUTS)
    s.update(candidate_rows=len(frame), thresholds=rules.check_parameters(frame, rules_dir))
    say(f"      {s['candidate_orthogroups']} orthogroups x {len(layout.ROUTES)} routes = {len(frame)} candidates; "
        f"{len(s['thresholds'])} population thresholds recomputed and equal to the frozen values")

    s = step("apply_rules", "applying the rules")
    outcomes, states = ranking.run(rule_table, symbol, frame, tdir)
    counts = ranking.final_pass_counts(states)
    s.update(rule_outcomes=len(outcomes), candidates=len(states), final_pass={k: v["PASS"] for k, v in counts.items()})
    say(f"      {len(outcomes)} rule outcomes for {len(states)} candidates")
    say(f"      {'route':<16}{'final pass':>10}{'fail':>8}{'not evaluable':>15}")
    for route, c in counts.items():
        say(f"      {route:<16}{c['PASS']:>10}{c['FAIL']:>8}{c['NOT_EVALUABLE']:>15}")

    s = step("sensitivity", "sensitivity: threshold sweeps, leave-one-gate-out, leave-one-component-out")
    s.update(sweeps=sweeps.run(rule_table, frame, tdir, rules_dir), perturbation=perturbation.run(rule_table, outcomes, tdir))
    say(f"      {s['sweeps']['sweep_values']} sweep values on {s['sweeps']['rules_swept']} gates; 14 gates and 8 components left out "
        f"one at a time")

    s = step("shortlists", "writing the shortlists and the per-route folders")
    s.update(shortlists.write(out_dir, rule_table, symbol, frame, tdir))
    say(f"      {s['files']} files; {s['orthogroups_passing_any_route']} orthogroups pass on at least one route")
    say(f"      done ({time.time() - clock[0]:.1f} s)")

    written = sorted(p.name for p in tdir.iterdir())
    assert written == sorted(layout.RESULT_TABLES), f"unexpected set of result tables: {sorted(set(written) ^ set(layout.RESULT_TABLES))}"
    log["tables"] = {n: sha256_file(tdir / n) for n in layout.RESULT_TABLES}
    log["final_pass"] = {k: v["PASS"] for k, v in counts.items()}
    log["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out_dir / "run_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log
