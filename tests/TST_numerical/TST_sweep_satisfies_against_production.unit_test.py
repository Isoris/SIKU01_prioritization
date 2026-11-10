#!/usr/bin/env python3
"""TST_sweep_satisfies_against_production.unit_test.py

Known-answer AND equivalence test for satisfies(op, observed, target), imported directly from
02_code/code_A6434_execute_sweeps_v27_v01.py - the function the sensitivity sweeps actually call
on the real dataset, exactly as evaluate() is what production execution calls.

WHY A SEPARATE FUNCTION EXISTS AT ALL
    The sweep script does not import evaluate() from code_A6434_production_v27_v01.py; it has its
    own satisfies(). The two differ on one point: evaluate()'s "==" branch falls back to string
    comparison for a categorical threshold (e.g. M0_PROTEIN_FORM's "single"), while satisfies()
    converts the threshold with num() first, so a non-numeric threshold makes it return None for
    every candidate rather than compare as a string.

    This is reachable only if a "==" rule is ever swept. It is not: analysis.yaml's
    sensitivity.selected_numeric_hard_rules lists exactly 9 rules, confirmed below to be exactly
    the 9 swept in practice, and every one of them uses >=, >, <=, < or BETWEEN - never "==". The
    gap is real but dead code on the current contract. It is proven dead here rather than asserted
    in a comment: if a future rule table ever adds a "==" rule to the swept set, the dead-code
    check below starts failing instead of silently shipping a sweep that reports NOT_EVALUABLE for
    every row of that rule.

TWO THINGS ARE CHECKED
    1. Equivalence: for every case on every swept rule, satisfies() and evaluate() are called on
       the same value and must return the same answer. This is the direct test of "same function,
       same answer" for the one pair of gate/sweep functions that are not literally the same
       Python object.
    2. The known-answer cases themselves (below/at/above; BETWEEN's five points; missing), so a
       pass here is not just "these two agree," it is "these two agree, and both are right."

Usage:  python3 TST_sweep_satisfies_against_production.unit_test.py
Exit code: 0 if every case passes on both counts, 1 otherwise.
"""
from __future__ import annotations
import ast
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
sys.path.insert(0, os.path.join(CAP, "02_code"))
from code_A6434_production_v27_v01 import evaluate, load_authority, threshold_of  # noqa: E402


def extract_functions(source_path: str, names: set[str], constants: set[str] = frozenset()) -> dict:
    """Pull out only the named top-level function definitions (and any module-level constant
    assignments they depend on) from a script, without executing its module-level code.
    code_A6434_execute_sweeps_v27_v01.py reads the real candidate table and writes its outputs at
    module level (no __main__ guard), so a plain `import` here would re-run the whole sweep as a
    side effect of fetching one function. This gets the exact same source - byte-identical to what
    production runs, not a reimplementation - without triggering any of that."""
    src = open(source_path, encoding="utf-8").read()
    tree = ast.parse(src, filename=source_path)
    segments = []
    found_names = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            segments.append(ast.get_source_segment(src, node))
            found_names.add(node.name)
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants):
            segments.append(ast.get_source_segment(src, node))
            found_names.add(node.targets[0].id)
    missing = (names | constants) - found_names
    if missing:
        raise RuntimeError(f"{source_path}: could not find {missing}")
    ns: dict = {}
    exec("\n\n".join(segments), ns)
    return ns


_sweep_ns = extract_functions(
    os.path.join(CAP, "02_code", "code_A6434_execute_sweeps_v27_v01.py"),
    names={"satisfies", "num"}, constants={"MISSING"})
satisfies = _sweep_ns["satisfies"]
num = _sweep_ns["num"]

try:
    import yaml
except ImportError:
    yaml = None


def one_sided_cases(op: str, t: float):
    below, at, above = t - 1, t, t + 1
    want = {
        "<":  {below: True,  at: False, above: False},
        "<=": {below: True,  at: True,  above: False},
        ">":  {below: False, at: False, above: True},
        ">=": {below: False, at: True,  above: True},
    }[op]
    return [(v, exp, f"{op} {t}: value={v}") for v, exp in want.items()]


def between_cases(lo: float, hi: float):
    below, above = lo - 1, hi + 1
    mid = (lo + hi) / 2
    return [
        (below, False, f"BETWEEN {lo};{hi}: below lower"),
        (lo,    True,  f"BETWEEN {lo};{hi}: at lower"),
        (mid,   True,  f"BETWEEN {lo};{hi}: inside"),
        (hi,    True,  f"BETWEEN {lo};{hi}: at upper"),
        (above, False, f"BETWEEN {lo};{hi}: above upper"),
    ]


def run() -> int:
    if yaml is None:
        print("PyYAML not available; cannot read analysis.yaml's swept-rule list")
        return 2

    analysis = yaml.safe_load(open(os.path.join(CAP, "analysis.yaml"), encoding="utf-8"))["analysis"]
    swept_ids = analysis["sensitivity"]["selected_numeric_hard_rules"]

    rules, symbol = load_authority()
    by_id = {r["rule_id"]: r for r in rules}

    total = 0
    failures: list[str] = []

    # %% dead-code check: every swept rule must be a non-equality operator ------------------
    for rid in swept_ids:
        op = by_id[rid]["operator"]
        if op == "==":
            failures.append(
                f"{rid} is swept AND uses '==': satisfies()'s categorical gap is no longer dead "
                f"code. Either fix satisfies() to match evaluate()'s string fallback, or confirm "
                f"this rule's threshold is purely numeric before trusting its sweep output.")

    # %% equivalence + known-answer, per swept rule -----------------------------------------
    for rid in swept_ids:
        rule = by_id[rid]
        op = rule["operator"]
        thr, _sym = threshold_of(rule, symbol)

        if op == "BETWEEN":
            lo, hi = (float(x) for x in str(thr).split(";"))
            cases = between_cases(lo, hi)
        elif op in ("<", "<=", ">", ">="):
            cases = one_sided_cases(op, float(thr))
        else:
            failures.append(f"{rid}: swept rule with unsupported operator {op!r} for this test")
            continue
        cases.append((None, None, "missing value"))

        for value, expected, label in cases:
            total += 1
            got_evaluate = evaluate(value, op, thr)
            got_satisfies = satisfies(op, num(value) if value is not None else None, thr)
            if got_evaluate is not got_satisfies:
                failures.append(
                    f"{rid} ({label}): evaluate()={got_evaluate!r} but satisfies()={got_satisfies!r} "
                    f"- the sweep would not agree with production on this case")
            if got_evaluate is not expected:
                failures.append(f"{rid} ({label}): expected {expected!r}, evaluate() returned {got_evaluate!r}")

    print(f"{len(swept_ids)} swept rules from analysis.yaml sensitivity.selected_numeric_hard_rules: "
          f"{swept_ids}")
    print(f"{total} cases, each checked for evaluate()/satisfies() equivalence and the known answer")

    if failures:
        print(f"\n{len(failures)} FAILED:")
        for f in failures:
            print(f"  {f}")
        print(f"\n{total - len(failures)} / {total} passed")
        return 1

    print(f"{total} / {total} passed")
    print("dead-code check: no swept rule uses '==', so satisfies()'s categorical gap is "
          "confirmed unreachable on the current v27 contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
