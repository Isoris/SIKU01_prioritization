#!/usr/bin/env python3
"""TST_execution_against_data.unit_test.py

Re-derives the published reference execution and the published sensitivity sweeps FROM THE REAL
EVIDENCE FRAME, using the production functions themselves, and asserts that every deposited row is
what the code actually produces on the real inputs.

WHY THIS EXISTS ALONGSIDE THE KNOWN-ANSWER TESTS
    The sibling tests assert that each predicate is right on constructed cases:
        TST_numerical/TST_numerical_against_production.unit_test.py       evaluate()
        TST_numerical/TST_sweep_satisfies_against_production.unit_test.py satisfies()
        TST_perturbation/TST_perturbation_against_production.unit_test.py final_pass(), score()
    None of them touches 04_tables/candidate_data_v02.tsv. verify.py is also not this check: it
    recomputes sha256 for deposited files against artifact_manifest.tsv, so it proves the bytes have
    not changed, not that the bytes are what applying the v27 rules to the frame produces. A
    rerun of the canonical pipeline reproduces the files byte-for-byte, but by definition it runs
    the same code path that wrote them.

    This test closes that gap for the two layers that read the frame directly:

      1. REFERENCE EXECUTION  production's own run() is called on the real frame and the real rule
         table, and its three products are compared row for row with the deposited tables:
             candidate_rule_outcomes_v27_v01.tsv   candidate x route x rule
             candidate_route_state_v27_v01.tsv     candidate x route
             rule_outcome_counts_v27_v01.tsv       rule x route
         run() returns data and writes nothing; main() does the writing and is behind a __main__
         guard, so importing the module is side-effect free.

      2. SENSITIVITY SWEEPS   the sweep script is a flat script with no __main__ guard, so its
         satisfies() and num() are lifted out of the module SOURCE with ast and compiled unmodified
         (the same technique the perturbation test uses and for the same reason). Each deposited
         sweep row's n_satisfying and n_not_evaluable are then recomputed on the population that row
         names, and compared.

    The perturbation layer (hard-gate LOO and additive LOCO) is already asserted against the real
    data in TST_perturbation/TST_perturbation_against_production.unit_test.py, so it is not
    repeated here.

Usage:  python3 TST_execution_against_data.unit_test.py
Exit code: 0 if every deposited row is reproduced from the frame, 1 otherwise.
"""
from __future__ import annotations
import ast
import csv
import os
import sys
from collections import OrderedDict, defaultdict

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
CODE_DIR = os.path.join(CAP, "02_code")
DER = os.path.join(CAP, "01_analysis_output", "derived")
TAB = os.path.join(CAP, "04_tables")
BRAIN = os.path.join(CAP, "capsule_brain")
SWEEP_SRC = os.path.join(CODE_DIR, "code_A6434_execute_sweeps_v27_v01.py")

sys.path.insert(0, CODE_DIR)
from code_A6434_production_v27_v01 import load_authority, read_tsv, run  # noqa: E402

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))


def deposited(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


# ================================================================ 1. reference execution
rules, symbol = load_authority()
cand = read_tsv(os.path.join(TAB, "candidate_data_v02.tsv"))
outcomes, states, counts, all_routes = run(rules, symbol, cand)

# ---- 1a. candidate x route x rule outcomes
dep_out = deposited(os.path.join(DER, "candidate_rule_outcomes_v27_v01.tsv"))
check(len(outcomes) == len(dep_out),
      f"re-derived outcome rows {len(outcomes)} == deposited {len(dep_out)}")
key = lambda r: (r["pangenome_id"], r["route"], r["rule_id"])  # noqa: E731
dep_by = {key(r): r for r in dep_out}
mismatch = []
for r in outcomes:
    d = dep_by.get(key(r))
    if d is None:
        mismatch.append((key(r), "absent from the deposited table", ""))
    elif str(r["outcome"]) != d["outcome"]:
        mismatch.append((key(r), r["outcome"], d["outcome"]))
check(not mismatch,
      f"every re-derived rule outcome equals the deposited outcome "
      f"({len(mismatch)} of {len(outcomes)} disagreed)")
for k, got, want in mismatch[:5]:
    print(f"       {k}: re-derived {got!r}, deposited {want!r}")

# ---- 1b. candidate x route state: final_pass and additive_score
dep_state = deposited(os.path.join(DER, "candidate_route_state_v27_v01.tsv"))
check(len(states) == len(dep_state),
      f"re-derived state rows {len(states)} == deposited {len(dep_state)}")
skey = lambda r: (r["pangenome_id"], r["route"])  # noqa: E731
dep_s = {skey(r): r for r in dep_state}
bad_fp = bad_sc = bad_n = 0
for r in states:
    d = dep_s.get(skey(r))
    if d is None:
        bad_fp += 1
        continue
    if r["final_pass"] != d["final_pass"]:
        bad_fp += 1
    if int(r["additive_score"]) != int(d["additive_score"]):
        bad_sc += 1
    if int(r["n_hard_applicable"]) != int(d["n_hard_applicable"]):
        bad_n += 1
check(bad_fp == 0, f"re-derived final_pass equals the deposited value on all {len(states)} "
                   f"candidate-route rows ({bad_fp} disagreed)")
check(bad_sc == 0, f"re-derived additive_score equals the deposited value on all {len(states)} "
                   f"candidate-route rows ({bad_sc} disagreed)")
check(bad_n == 0, f"re-derived n_hard_applicable equals the deposited value on all {len(states)} "
                  f"candidate-route rows ({bad_n} disagreed)")

# ---- 1c. rule x route counts
dep_counts = deposited(os.path.join(DER, "rule_outcome_counts_v27_v01.tsv"))
rebuilt = {}
for (rid, route), c in counts.items():
    rebuilt[(rid, route)] = dict(
        n_evaluated=sum(c.values()), n_pass=c.get("PASS", 0), n_fail=c.get("FAIL", 0),
        n_not_evaluable=c.get("NOT_EVALUABLE", 0), n_plus1=c.get("+1", 0), n_zero=c.get("0", 0))
bad_c = 0
for d in dep_counts:
    g = rebuilt.get((d["rule_id"], d["route"]))
    if g is None or any(int(d[k]) != v for k, v in g.items()):
        bad_c += 1
check(len(rebuilt) == len(dep_counts),
      f"re-derived rule x route count rows {len(rebuilt)} == deposited {len(dep_counts)}")
check(bad_c == 0, f"every deposited rule x route count row is reproduced "
                  f"({bad_c} of {len(dep_counts)} disagreed)")

# ---- 1d. the headline the manuscript quotes, re-derived rather than read
final_by_route = defaultdict(int)
for r in states:
    if r["final_pass"] == "PASS":
        final_by_route[r["route"]] += 1

# ================================================================ 2. sensitivity sweeps
tree = ast.parse(open(SWEEP_SRC, encoding="utf-8").read(), filename=SWEEP_SRC)
wanted = ("satisfies", "num")
picked = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
missing = set(wanted) - {n.name for n in picked}
if missing:
    raise SystemExit(f"{SWEEP_SRC} no longer defines {sorted(missing)}; the sweep layer was "
                     f"restructured and this test must be updated with it")
# the module-level literal constants those functions close over (e.g. MISSING), taken from the
# source rather than restated here, so the test cannot disagree with the module about them
consts = [n for n in tree.body if isinstance(n, ast.Assign)
          and all(isinstance(t, ast.Name) for t in n.targets)
          and isinstance(n.value, (ast.Constant, ast.Set, ast.Tuple, ast.List, ast.Dict))]
ns: dict = {}
exec(compile(ast.Module(body=consts + picked, type_ignores=[]), SWEEP_SRC, "exec"), ns)
satisfies, num = ns["satisfies"], ns["num"]
check("MISSING" in ns, "the sweep module's missing-value token set was lifted with its functions")

# populations, built exactly as the sweep script builds them
ref_pop = OrderedDict()
for r in cand:
    ref_pop.setdefault(r["pangenome_id"], r)
by_route = defaultdict(OrderedDict)
for r in cand:
    by_route[r["route"]][r["pangenome_id"]] = r

dep_sweep = deposited(os.path.join(DER, "hard_gate_sweep_execution_v01.tsv"))
bad_sat = bad_ne = 0
for row in dep_sweep:
    pop = ref_pop if row["population"] == "M0_ENTRY_REFERENCE" else by_route.get(row["population"])
    if pop is None:
        bad_sat += 1
        continue
    keep, notev = 0, 0
    for _pid, r in pop.items():
        v = satisfies(row["operator"], num(r.get(row["variable"])), row["sweep_value"])
        if v is None:
            notev += 1
        elif v:
            keep += 1
    if keep != int(row["n_satisfying"]):
        bad_sat += 1
    if notev != int(row["n_not_evaluable"]):
        bad_ne += 1
check(bad_sat == 0, f"every deposited sweep row's n_satisfying is reproduced from the frame "
                    f"({bad_sat} of {len(dep_sweep)} disagreed)")
check(bad_ne == 0, f"every deposited sweep row's n_not_evaluable is reproduced from the frame "
                   f"({bad_ne} of {len(dep_sweep)} disagreed)")

# ================================================================ 3. population identity
# One population underlies every distribution-derived threshold and every shared-rule sweep. It has
# exactly one identifier, M0_ENTRY_REFERENCE, and it is declared by the M0.0 rule record M0_INPUT.
# Those are two different objects - a population id and a rule id - and the only way they stay
# consistent across the parameter table, the sweep contract and the rule expressions is to assert it.
POP = "M0_ENTRY_REFERENCE"
DECLARING_RULE = "M0_INPUT"

params = deposited(os.path.join(BRAIN, "rule_parameter_resolution_v02.tsv"))
check(all(p["distribution_binding_id"] == POP for p in params),
      f"every distribution-derived parameter binds the population {POP} "
      f"({sorted({p['distribution_binding_id'] for p in params})})")
check(all(int(p["n_reference"]) == len(ref_pop) for p in params),
      f"every parameter row's n_reference equals the population re-derived from the frame "
      f"({len(ref_pop)}); declared {sorted({p['n_reference'] for p in params})}")

rule_ids = {r["rule_id"] for r in rules}
check(DECLARING_RULE in rule_ids,
      f"{DECLARING_RULE} is a rule_id in the rule owner (the M0.0 declaration), not a population id")
check(POP not in rule_ids,
      f"{POP} is a population id and must never appear as a rule_id in the rule owner")

# the rule expressions that resolve a distribution-derived threshold must name the population,
# never the declaring rule
expr_rules = [r for r in rules if "Q3(" in r["expression"] or "median(" in r["expression"]]
bad_expr = [r["rule_id"] for r in expr_rules if POP not in r["expression"]]
check(not bad_expr,
      f"every distribution-derived rule expression names {POP} "
      f"({len(expr_rules)} expressions; offenders: {bad_expr})")

# shared-rule sweeps must run on that same named population
shared_pops = {row["population"] for row in dep_sweep
               if row["population"] not in by_route}
check(shared_pops <= {POP},
      f"every non-route sweep population is {POP} (found {sorted(shared_pops)})")

# ================================================================ 4. missing-value token agreement
# MISSING_DIVERGENCE: production's evaluate() and the sweep's satisfies() each carry their own
# missing-value token set, and they are not identical - the sweep additionally treats "-" as
# missing. On the current frame no cell carries a divergent token, so the two layers cannot
# disagree today. That is a property of the data, not of the code, so it is asserted rather than
# assumed: if a frame ever arrives carrying one of these tokens, this fails instead of the
# reference execution and its own sensitivity analysis quietly scoring that cell differently.
prod_src = open(os.path.join(CODE_DIR, "code_A6434_production_v27_v01.py"), encoding="utf-8").read()
prod_tree = ast.parse(prod_src)
prod_ns: dict = {}
exec(compile(ast.Module(body=[n for n in prod_tree.body if isinstance(n, ast.Assign)
                              and all(isinstance(t, ast.Name) for t in n.targets)
                              and isinstance(n.value, (ast.Constant, ast.Set, ast.Tuple, ast.List, ast.Dict))],
                        type_ignores=[]), "production", "exec"), prod_ns)
divergent = set(ns["MISSING"]) ^ set(prod_ns["MISSING"])
carried = {}
for r in cand:
    for k, v in r.items():
        if v is not None and str(v).strip() in divergent:
            carried[k] = carried.get(k, 0) + 1
check(not carried,
      f"no frame cell carries a token the two predicates treat differently "
      f"(divergent tokens {sorted(divergent)}; carried by {carried or 'nothing'})")

# ================================================================ report
failed = [lab for ok, lab in results if not ok]
for lab in failed:
    print(f"FAIL  {lab}")
print(f"frame {len(cand)} candidate-route rows x {len([r for r in rules if r['role'] in ('hard','additive')])} "
      f"executable rules -> {len(outcomes)} rule outcomes, {len(states)} states, "
      f"{len(rebuilt)} rule x route counts; {len(dep_sweep)} sweep rows re-derived")
print("final_pass by route, re-derived from the frame: "
      + ", ".join(f"{rt} {final_by_route[rt]}" for rt in sorted(final_by_route)))
print(f"{len(results) - len(failed)} / {len(results)} passed")
sys.exit(1 if failed else 0)
