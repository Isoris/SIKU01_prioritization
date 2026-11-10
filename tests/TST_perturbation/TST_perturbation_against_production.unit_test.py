#!/usr/bin/env python3
"""TST_perturbation_against_production.unit_test.py

Known-answer AND equivalence test for the two functions the validation layer uses to recompute
eligibility and score with one rule omitted:

    final_pass(d, omit=None)   02_code/code_A6434_perturbation_v27_v01.py
    score(d, omit=None)        02_code/code_A6434_perturbation_v27_v01.py

WHY THIS TEST EXISTS
    The hard-gate LOO and additive LOCO results are not produced by a second ranking engine. They
    read the production outcomes (candidate_rule_outcomes_v27_v01.tsv) and recompute final_pass and
    the additive score with one rule left out. That is the same decision the ranking makes, with a
    rule skipped - so the implementation test for the gates has to be the same test. If these two
    functions ever drift from production's own intersection and accumulation, every LOO and LOCO
    number silently becomes a statement about a different rule set than the one that was executed.

    The sibling tests cover the other two predicates in the pipeline:
        TST_numerical/TST_numerical_against_production.unit_test.py   evaluate()   (production)
        TST_numerical/TST_sweep_satisfies_against_production.unit_test.py satisfies() (sensitivity)
    This one closes the third: the perturbation layer that LOO and LOCO are built on.

HOW THE FUNCTIONS ARE OBTAINED
    code_A6434_perturbation_v27_v01.py is a flat script with no __main__ guard: importing it would
    execute the whole perturbation and rewrite its outputs. The two function definitions are
    therefore lifted out of the module SOURCE with ast, compiled unmodified, and executed in a
    namespace this test controls. Nothing is reimplemented here - an edit to either function is
    picked up on the next run, and a rename makes this test fail rather than silently pass.
    The controlled namespace is also what lets section 1 below put a synthetic rule set behind the
    functions instead of the real one.

WHAT IS CHECKED
    1. KNOWN ANSWER, synthetic rule set:
         outcome precedence  any FAIL -> FAIL; else any NOT_EVALUABLE -> NOT_EVALUABLE; else PASS
         omit                removes exactly the named rule from consideration, and nothing else
         score               counts only "+1" among applicable additive rules, omitting one
         non-applicable      a rule absent from the candidate's dict is simply not considered
    2. EQUIVALENCE WITH PRODUCTION on the executed dataset:
         final_pass(d)  == production's final_pass      for every candidate x route
         score(d)       == production's additive_score  for every candidate x route
    3. LOO REPRODUCTION: recomputing each omitted hard rule reproduces
       hard_gate_loo_summary_v01.tsv n_final_pass_perturbed exactly, and the monotonicity
       invariant (omitting a hard gate can never remove a candidate from the final-pass set).
    4. LOCO REPRODUCTION: recomputing each omitted additive component reproduces
       additive_perturbation_summary_v01.tsv n_scores_changed exactly, and the invariant that an
       additive component never changes hard-gate eligibility.

Usage:  python3 TST_perturbation_against_production.unit_test.py
Exit code: 0 if every case matches its predetermined answer, 1 otherwise.
"""
from __future__ import annotations
import ast
import csv
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
CODE = os.path.join(CAP, "02_code", "code_A6434_perturbation_v27_v01.py")
DER = os.path.join(CAP, "01_analysis_output", "derived")
BRAIN = os.path.join(CAP, "capsule_brain")

PASS, FAIL, NE = "PASS", "FAIL", "NOT_EVALUABLE"
WANTED = ("final_pass", "score")

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))


def read_tsv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


# ---------------------------------------------------------------- lift the real functions
def load_functions(hard: dict, additive: dict):
    """Compile final_pass and score from the module source into a namespace holding the rule
    sets they close over. No import, so the script's top-level work never runs."""
    tree = ast.parse(open(CODE, encoding="utf-8").read(), filename=CODE)
    picked = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in WANTED]
    missing = set(WANTED) - {n.name for n in picked}
    if missing:
        raise SystemExit(f"{CODE} no longer defines {sorted(missing)}; the perturbation layer was "
                         f"renamed or restructured and this test must be updated with it")
    ns: dict = {"FAIL": FAIL, "NE": NE, "PASS": PASS, "hard": hard, "additive": additive}
    exec(compile(ast.Module(body=picked, type_ignores=[]), CODE, "exec"), ns)
    return ns["final_pass"], ns["score"]


# ---------------------------------------------------------------- 1. known answer, synthetic rules
SYN_HARD = {"H1": {}, "H2": {}, "H3": {}}
SYN_ADD = {"A1": {}, "A2": {}, "A3": {}}
fp, sc = load_functions(SYN_HARD, SYN_ADD)

PRECEDENCE = [
    ({"H1": PASS, "H2": PASS, "H3": PASS}, None, PASS, "all pass"),
    ({"H1": PASS, "H2": FAIL, "H3": PASS}, None, FAIL, "one fail dominates"),
    ({"H1": PASS, "H2": NE, "H3": PASS}, None, NE, "one not-evaluable, no fail"),
    ({"H1": FAIL, "H2": NE, "H3": PASS}, None, FAIL, "fail outranks not-evaluable"),
    ({"H1": FAIL, "H2": FAIL, "H3": FAIL}, None, FAIL, "all fail"),
    ({}, None, PASS, "no applicable hard gate is a vacuous pass"),
    # omit
    ({"H1": PASS, "H2": FAIL, "H3": PASS}, "H2", PASS, "omitting the only failing gate admits"),
    ({"H1": PASS, "H2": FAIL, "H3": PASS}, "H1", FAIL, "omitting a passing gate changes nothing"),
    ({"H1": FAIL, "H2": FAIL, "H3": PASS}, "H1", FAIL, "a second failing gate still fails"),
    ({"H1": NE, "H2": PASS, "H3": PASS}, "H1", PASS, "omitting the not-evaluable gate admits"),
    # additive outcomes present in the dict must never be read as hard states
    ({"H1": PASS, "A1": "0", "A2": "+1"}, None, PASS, "additive outcomes ignored by final_pass"),
]
for d, omit, want, label in PRECEDENCE:
    got = fp(d, omit)
    check(got == want, f"final_pass {label}: expected {want}, got {got}")

SCORE_CASES = [
    ({"A1": "+1", "A2": "+1", "A3": "+1"}, None, 3, "all satisfied"),
    ({"A1": "+1", "A2": "0", "A3": "+1"}, None, 2, "one unsatisfied"),
    ({"A1": "0", "A2": "0", "A3": "0"}, None, 0, "none satisfied"),
    ({"A1": "+1", "A2": "+1", "A3": "+1"}, "A2", 2, "omit a satisfied component"),
    ({"A1": "+1", "A2": "0", "A3": "+1"}, "A2", 2, "omit an unsatisfied component"),
    ({"A1": "+1", "H1": PASS}, None, 1, "hard outcomes ignored by score"),
    ({}, None, 0, "no applicable additive component"),
]
for d, omit, want, label in SCORE_CASES:
    got = sc(d, omit)
    check(got == want, f"score {label}: expected {want}, got {got}")

# ---------------------------------------------------------------- real rule sets and state
rules = read_tsv(os.path.join(BRAIN, "ranking_rules_v27.tsv"))
hard = {r["rule_id"]: r for r in rules if r["role"] == "hard"}
additive = {r["rule_id"]: r for r in rules if r["role"] == "additive"}
fp, sc = load_functions(hard, additive)

outcomes = read_tsv(os.path.join(DER, "candidate_rule_outcomes_v27_v01.tsv"))
state: dict[tuple[str, str], dict[str, str]] = {}
for o in outcomes:
    state.setdefault((o["pangenome_id"], o["route"]), {})[o["rule_id"]] = o["outcome"]

# ---------------------------------------------------------------- 2. equivalence with production
prod = read_tsv(os.path.join(DER, "candidate_route_state_v27_v01.tsv"))
bad_fp = bad_sc = 0
for row in prod:
    d = state.get((row["pangenome_id"], row["route"]), {})
    if fp(d) != row["final_pass"]:
        bad_fp += 1
    if sc(d) != int(row["additive_score"]):
        bad_sc += 1
check(bad_fp == 0, f"final_pass() equals production final_pass on all {len(prod)} candidate-route "
                   f"rows ({bad_fp} disagreed)")
check(bad_sc == 0, f"score() equals production additive_score on all {len(prod)} candidate-route "
                   f"rows ({bad_sc} disagreed)")

routes = sorted({r for _, r in state})
ref_pass = {rt: {cid for (cid, r), d in state.items() if r == rt and fp(d) == PASS} for rt in routes}

# ---------------------------------------------------------------- 3. LOO reproduction
loo = read_tsv(os.path.join(DER, "hard_gate_loo_summary_v01.tsv"))
bad_loo = bad_mono = 0
for row in loo:
    rt, rid = row["route_id"], row["omitted_rule_id"]
    got = {cid for (cid, r), d in state.items() if r == rt and fp(d, rid) == PASS}
    if len(got) != int(row["n_final_pass_perturbed"]):
        bad_loo += 1
    if not ref_pass[rt] <= got:
        bad_mono += 1
check(bad_loo == 0, f"recomputing each omitted hard gate reproduces n_final_pass_perturbed on all "
                    f"{len(loo)} route x rule rows ({bad_loo} disagreed)")
check(bad_mono == 0, f"omitting a hard gate never removes a candidate from the final-pass set "
                     f"({bad_mono} of {len(loo)} violated the monotonicity invariant)")

# ---------------------------------------------------------------- 4. LOCO reproduction
loco = read_tsv(os.path.join(DER, "additive_perturbation_summary_v01.tsv"))
bad_loco = bad_elig = 0
for row in loco:
    rt, rid = row["route_id"], row["omitted_rule_id"]
    pop = [(cid, d) for (cid, r), d in state.items() if r == rt and fp(d) == PASS]
    changed = sum(1 for _, d in pop if sc(d, rid) != sc(d))
    if changed != int(row["n_scores_changed"]):
        bad_loco += 1
    # omitting an additive component must leave eligibility untouched: final_pass reads hard
    # outcomes only, so passing it an additive rule_id has to be a no-op on every candidate.
    if any(fp(d, rid) != fp(d) for _, d in pop):
        bad_elig += 1
check(bad_loco == 0, f"recomputing each omitted additive component reproduces n_scores_changed on "
                     f"all {len(loco)} route x component rows ({bad_loco} disagreed)")
check(bad_elig == 0, f"omitting an additive component never changes final_pass "
                     f"({bad_elig} of {len(loco)} route x component rows disagreed)")
check(all(row["hard_final_pass_changed"].upper() == "FALSE" for row in loco),
      "no additive component changes hard-gate eligibility in the executed LOCO summary")

# ---------------------------------------------------------------- report
failed = [lab for ok, lab in results if not ok]
for lab in failed:
    print(f"FAIL  {lab}")
print(f"{len(PRECEDENCE)} final_pass and {len(SCORE_CASES)} score known-answer cases on a synthetic "
      f"rule set; equivalence with production over {len(prod)} candidate-route rows; "
      f"{len(loo)} LOO and {len(loco)} LOCO rows reproduced")
print(f"{len(results) - len(failed)} / {len(results)} passed")
sys.exit(1 if failed else 0)
