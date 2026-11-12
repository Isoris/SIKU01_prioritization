"""Command line of the SIKU01 candidate prioritization.

    python prioritize.py reproduce              run it twice, check everything, keep the run in results/<date-time>/
    python prioritize.py run                    run it once into results/<date-time>/ (no checks against the deposit)
    python prioritize.py verify DIR             check a finished run against the deposited tables
    python prioritize.py check-inputs           are the input tables the recorded ones?
    python prioritize.py rules [--route R]      print the rules in plain words
    python prioritize.py show ID                everything about one orthogroup (pangenome_id, gene name or SIKU01 locus tag)
    python prioritize.py shortlist ROUTE        print the final-pass candidates of a route
    python prioritize.py test                   run the unit tests (about a minute)

`rules`, `show` and `shortlist` read the deposited tables in expected/tables/ unless --run DIR names a run of your own.
"""
import argparse
import sys
import tempfile
import time
from pathlib import Path

from . import inputs, layout, pipeline, rules, verify
from .tables import read_tsv


def _new_run_dir(out):
    return Path(out).resolve() if out else layout.RESULTS / time.strftime("%Y-%m-%d_%H%M%S")


def _print_final_pass(final_pass):
    print("final pass per route")
    for route in layout.ROUTES:
        print(f"   {route:<16}{final_pass[route]:>5}  {'#' * round(final_pass[route] / 10)}")
    print(f"   {'total':<16}{sum(final_pass.values()):>5}   ({layout.N_REFERENCE * len(layout.ROUTES)} candidates = "
          f"{layout.N_REFERENCE} orthogroups x {len(layout.ROUTES)} routes)")


def _check_run(tables_dir):
    """The checks of a single run. Returns True when all pass."""
    same, n, problems = verify.compare_with_expected(tables_dir)
    print(f"[match]     {same} of {n} result tables identical to the deposited tables in expected/tables/")
    for p in problems:
        print(f"            FAIL {p}")
    r = verify.independent_recompute(tables_dir)
    print(f"[recompute] {r['thresholds_equal']} of {r['thresholds']} population thresholds reproduced; {r['rows']} candidates "
          f"recomputed by separate code, {r['differ']} differ")
    for e in r["examples"]:
        print(f"            FAIL {e}")
    if r["missing"] or r["extra"]:
        print(f"            FAIL {r['missing']} candidates absent from the run, {r['extra']} in the run but not in the inputs")
    return not problems and r["ok"]


def cmd_run(a):
    out = _new_run_dir(a.out)
    log = pipeline.run(out)
    print()
    _print_final_pass(log["final_pass"])
    print(f"\nresults: {out}\n   start with REPORT.md and shortlists/")
    return 0


def cmd_reproduce(a):
    out = _new_run_dir(a.out)
    print("=" * 78)
    print("SIKU01 candidate prioritization: 23 rules, 6 routes, 1,527 core orthogroups")
    print("=" * 78)
    print(f"reproduce: run 1 of 2 -> {out}")
    log = pipeline.run(out)
    with tempfile.TemporaryDirectory(prefix="siku01_run2_") as tmp:
        print("reproduce: run 2 of 2 (to test that two runs give the same files)")
        pipeline.run(Path(tmp) / "run2", say=lambda *_: None)
        print()
        print("checks")
        ok = _check_run(out / "tables")
        same, n, problems = verify.compare_runs(out, Path(tmp) / "run2")
        print(f"[repeat]    {same} of {n} files byte-identical between the two runs")
        for p in problems:
            print(f"            FAIL {p}")
        ok = ok and not problems
    print()
    _print_final_pass(log["final_pass"])
    verdict = "PASS" if ok else "FAIL"
    (out / "VERDICT.txt").write_text(
        f"reproduce: {verdict}\nchecked: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} UTC\n"
        "checks: result tables identical to expected/tables/; independent recomputation of every candidate; two runs byte-identical\n",
        encoding="utf-8")
    print(f"\nresults: {out}\n   start with REPORT.md and shortlists/")
    print(f"reproduce: {verdict}" + ("" if ok else " (see the FAIL lines above)"))
    return 0 if ok else 1


def cmd_verify(a):
    d = Path(a.run).resolve()
    tables_dir = d / "tables" if (d / "tables").is_dir() else d
    ok = _check_run(tables_dir)
    print(f"verify: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_check_inputs(a):
    rows, problems = inputs.check_inputs()
    for r in rows:
        used = "read by the ranking" if r["read_by_ranking"] == "yes" else "not read by the ranking"
        print(f"   {r['status']:<8}{r['file']:<56}{r['role']:<17}{int(r['data_rows']):>8} rows   {used}")
    frozen = [r for r in rows if r["role"] == "frozen_table"]
    print(f"{sum(r['status'] == 'OK' for r in frozen)} of {len(frozen)} frozen tables and "
          f"{sum(r['status'] == 'OK' for r in rows) - sum(r['status'] == 'OK' for r in frozen)} of {len(rows) - len(frozen)} other "
          "inputs identical to their recorded checksum")
    for p in problems:
        print(f"   FAIL {p}")
    return 1 if problems else 0


def _threshold_text(rule, symbol):
    thr, sym = rules.threshold_of(rule, symbol)
    if rule["operator"] == "BETWEEN":
        lo, hi = str(thr).split(";")
        return f"{lo} to {hi}"
    return f"{thr} ({sym})" if sym else str(thr)


def cmd_rules(a):
    table, symbol = rules.load_rules()
    print(f"{'pos':<7}{'rule_id':<19}{'role':<10}{'routes':<30}{'condition':<46}threshold")
    for r in table:
        if r["role"] == "declaration":
            print(f"{r['layer_position']:<7}{r['rule_id']:<19}{'(entry)':<10}{'all':<30}{r['expression']}")
            continue
        if a.route and a.route not in rules.routes_of(r, layout.ROUTES):
            continue
        print(f"{r['layer_position']:<7}{r['rule_id']:<19}{r['role']:<10}{r['routes']:<30}{r['expression']:<46}{_threshold_text(r, symbol)}")
    print("\nhard: the candidate must pass (PASS / FAIL / NOT_EVALUABLE).  additive: +1 when satisfied, never removes a candidate.")
    return 0


def _tables_dir(run):
    if not run:
        return layout.EXPECTED_TABLES, "the deposited tables (expected/tables/)"
    d = Path(run).resolve()
    return (d / "tables" if (d / "tables").is_dir() else d), str(d)


def cmd_show(a):
    tdir, label = _tables_dir(a.run)
    info = read_tsv(tdir / layout.T_RANKING_INPUTS)
    q = a.id.strip()
    hits = [r for r in info if q in (r["pangenome_id"], r["literature__representative_locus_tag"])
            or q.lower() in (r["gene_name"].lower(), r["m0__orthogroup_label"].lower())]
    if not hits:
        print(f"no candidate orthogroup matches {q!r} (try a pangenome_id such as 21, a gene name such as polC, or a locus tag such as "
              "SIKU01_000318). Only the 1,527 core orthogroups that enter the prioritization are listed.")
        return 1
    table, symbol = rules.load_rules()
    by_id = {r["rule_id"]: r for r in table}
    outcomes = read_tsv(tdir / layout.T_OUTCOMES)
    states = {(s["pangenome_id"], s["route"]): s for s in read_tsv(tdir / layout.T_STATE)}
    print(f"source: {label}")
    for h in hits:
        pid = h["pangenome_id"]
        print(f"\npangenome_id {pid}   label {h['m0__orthogroup_label']}   gene {h['gene_name'] or '-'}   "
              f"SIKU01 locus {h['literature__representative_locus_tag'] or '-'}")
        mine = [o for o in outcomes if o["pangenome_id"] == pid]
        for route in layout.ROUTES:
            s = states[(pid, route)]
            print(f"\n  {route}: final pass = {s['final_pass']}; additive score {s['additive_score']} of {s['n_additive_applicable']}")
            for o in mine:
                if o["route"] != route:
                    continue
                r = by_id[o["rule_id"]]
                value = o["observed_value"] if o["observed_value"] != "" else "(missing)"
                print(f"     {o['layer_position']:<6}{o['rule_id']:<18}{o['outcome']:<15}{r['expression']:<46}value {value}")
    return 0


def cmd_shortlist(a):
    tdir, label = _tables_dir(a.run)
    info = {r["pangenome_id"]: r for r in read_tsv(tdir / layout.T_RANKING_INPUTS)}
    rows = [s for s in read_tsv(tdir / layout.T_STATE) if s["route"] == a.route and s["final_pass"] == "PASS"]
    rows.sort(key=lambda s: (-int(s["additive_score"]), int(s["pangenome_id"])))
    print(f"source: {label}")
    print(f"{a.route}: {len(rows)} final-pass candidates ({layout.ROUTE_LABEL[a.route]}); sorted by additive score, then pangenome_id\n")
    print(f"{'pangenome_id':<14}{'label':<16}{'gene':<10}{'SIKU01 locus':<16}additive score")
    for s in rows[: a.n or None]:
        r = info[s["pangenome_id"]]
        print(f"{s['pangenome_id']:<14}{r['m0__orthogroup_label'][:15]:<16}{r['gene_name'][:9] or '-':<10}"
              f"{r['literature__representative_locus_tag'] or '-':<16}{s['additive_score']} of {s['n_additive_applicable']}")
    if a.n and len(rows) > a.n:
        print(f"... {len(rows) - a.n} more (use -n 0 for all; the full table is shortlists/final_pass_{a.route}.tsv of a run)")
    return 0


def cmd_test(a):
    import unittest
    sys.path.insert(0, str(layout.REPO))
    suite = unittest.defaultTestLoader.discover(str(layout.REPO / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2 if a.verbose else 1).run(suite)
    print(f"tests: {result.testsRun} run, {len(result.failures) + len(result.errors)} failed, {len(result.skipped)} skipped")
    return 0 if result.wasSuccessful() else 1


def cmd_manifest(a):
    print(f"expected/MANIFEST.tsv rewritten: {verify.build_manifest()} tables")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="prioritize.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", metavar="command")
    p = sub.add_parser("reproduce", help="run twice and check everything against the deposited results")
    p.add_argument("--out", help="folder for the kept run (default: results/<date-time>/)")
    p.set_defaults(fn=cmd_reproduce)
    p = sub.add_parser("run", help="run once")
    p.add_argument("--out", help="output folder (default: results/<date-time>/)")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("verify", help="check a finished run")
    p.add_argument("run", help="a run folder (or its tables/ folder)")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("check-inputs", help="compare the input tables with their recorded checksums")
    p.set_defaults(fn=cmd_check_inputs)
    p = sub.add_parser("rules", help="print the rules")
    p.add_argument("--route", choices=layout.ROUTES)
    p.set_defaults(fn=cmd_rules)
    p = sub.add_parser("show", help="everything about one orthogroup")
    p.add_argument("id", help="pangenome_id, gene name or SIKU01 locus tag")
    p.add_argument("--run", help="a run folder (default: the deposited tables)")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("shortlist", help="print the final-pass candidates of a route")
    p.add_argument("route", choices=layout.ROUTES)
    p.add_argument("-n", type=int, default=20, help="how many to print (default 20; 0 = all)")
    p.add_argument("--run", help="a run folder (default: the deposited tables)")
    p.set_defaults(fn=cmd_shortlist)
    p = sub.add_parser("test", help="run the unit tests")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_test)
    p = sub.add_parser("manifest")   # maintenance: rewrite expected/MANIFEST.tsv after a deliberate change of the reference tables
    p.set_defaults(fn=cmd_manifest)
    a = ap.parse_args(argv)
    if not a.command:
        ap.print_help()
        return 2
    try:
        return a.fn(a)
    except (RuntimeError, FileNotFoundError, rules.RuleTableError, AssertionError) as e:
        print(f"\nSTOPPED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
