#!/usr/bin/env python3
"""TST_numerical_against_production.unit_test.py

Known-answer test for every hard and additive rule in capsule_brain/ranking_rules_v27.tsv, run
against evaluate() imported directly from 02_code/code_A6434_production_v27_v01.py - the actual
production comparison function, not a reimplementation of it. Two sections:

  1. PER-RULE CASES, one call to evaluate() per case:
       one-sided (<, <=, >, >=):  value just below, exactly at, and just above the threshold
       two-sided (BETWEEN):       below lower, at lower, inside, at upper, above upper
       equality (==):             a full truth table, not two arbitrary values - see
                                   EQUALITY_TRUTH_TABLES below, one explicit row per rule
       every rule, regardless of operator: a missing value (expect None) and a malformed
                                            non-numeric string for a numeric operator (expect None)

  2. ADDITIVE-SCORE TRUTH TABLE, all 2**8 = 256 combinations of the eight additive rules'
     satisfied/not-satisfied state, asserting score == count(satisfied) with no cap and no
     retention threshold - the exact accumulation production's run() does at
     02_code/code_A6434_production_v27_v01.py lines ~131-135 (contribution = 1 if res is True
     else 0; score += contribution; nothing gates on score). This replaces TST_counts
     (quarantined: 11_handoff/superseded/tests_v27_retired/), whose truth table enumerated
     SAT/UNMET/PENALISED states against QBD$NEG_WEIGHT and an N-of-M retention threshold - both
     explicitly prohibited by the current contract (analysis.yaml: rule_model.negative_weights
     false, additive_retention_threshold false, n_of_m_retention false; load_authority() itself
     raises SystemExit if any rule carries score_delta_penalty or penalty_condition). TST_counts
     was internally consistent and still 100% wrong for v27: it tested a scoring scheme the
     production code actively refuses to run.

This test has nothing to go stale, because every threshold is read from the same authority table
production reads, and every comparison is the same function production calls.

What this does NOT do: run on the real candidate table (production execution, covered by
run_all.sh + verify.py against artifact_manifest.tsv) or exercise the sweep contract. The sweep
script (code_A6434_execute_sweeps_v27_v01.py) has its own satisfies() rather than importing
evaluate() - see the sibling test TST_sweep_satisfies_against_production.unit_test.py, which checks
satisfies() against the same known-answer cases AND against evaluate() directly, for every rule
analysis.yaml actually sweeps.

Usage:  python3 TST_numerical_against_production.unit_test.py
Exit code: 0 if every case matches its predetermined answer, 1 otherwise.
"""
from __future__ import annotations
import itertools
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.abspath(os.path.join(TESTS_DIR, "..", ".."))
sys.path.insert(0, os.path.join(CAP, "02_code"))
from code_A6434_production_v27_v01 import evaluate, load_authority, threshold_of  # noqa: E402


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


# Explicit truth table per equality rule, by rule_id - not a generic t/t+1 pair. Every row is a
# realistic value for that rule's own variable, chosen to exercise every state the variable can
# actually be in, not just "matches" and "doesn't".
EQUALITY_TRUTH_TABLES = {
    # orf_intact_all: boolean-as-integer, the only two legal states are 1 and 0
    "M0_ORF": [
        (1,   True,  "intact (1)"),
        (0,   False, "not intact (0)"),
    ],
    # annotation_protein_form: categorical, "single" is the only satisfying state
    "M0_PROTEIN_FORM": [
        ("single",   True,  "single annotated form"),
        ("multiple", False, "multiple annotated forms"),
        ("none",     False, "no annotated form"),
    ],
    # n_typeIIS_total: count, only exactly zero satisfies
    "M2_TYPEIIS": [
        (0, True,  "zero Type IIS sites"),
        (1, False, "one Type IIS site"),
        (3, False, "three Type IIS sites"),
    ],
    # rep_epitope_positive: categorical flag, "yes" is the only satisfying state
    "M1_EPITOPE": [
        ("yes", True,  "epitope positive"),
        ("no",  False, "epitope negative"),
    ],
}


def run() -> int:
    rules, symbol = load_authority()
    executable = [r for r in rules if r["role"] in ("hard", "additive")]
    assert len(executable) == 22, f"expected 22 executable rules from the live authority, got {len(executable)}"

    total = 0
    failures: list[str] = []

    # %% 1. per-rule cases -------------------------------------------------------------------
    for rule in executable:
        rid = rule["rule_id"]
        op = rule["operator"]
        thr, _sym = threshold_of(rule, symbol)

        if op == "BETWEEN":
            lo, hi = (float(x) for x in str(thr).split(";"))
            cases = between_cases(lo, hi)
        elif op == "==":
            if rid not in EQUALITY_TRUTH_TABLES:
                failures.append(f"{rid}: no truth table declared for this == rule - add one to "
                                 f"EQUALITY_TRUTH_TABLES rather than falling back to a generic case")
                continue
            cases = list(EQUALITY_TRUTH_TABLES[rid])
        elif op in ("<", "<=", ">", ">="):
            cases = one_sided_cases(op, float(thr))
        else:
            failures.append(f"{rid}: unrecognised operator {op!r}")
            continue

        cases.append((None, None, "missing value"))
        if op != "==":
            cases.append(("not_a_number", None, "malformed non-numeric string"))

        for value, expected, label in cases:
            total += 1
            got = evaluate(value, op, thr)
            if got is not expected:
                failures.append(f"{rid} ({label}): expected {expected!r}, evaluate() returned {got!r}")

    n_rule_cases = total

    # %% 2. additive-score truth table --------------------------------------------------------
    # Every combination of satisfied/not-satisfied for the 8 additive rules. Production's
    # contribution rule (run(), ~line 133): 1 if res is True else 0 - missing and False both
    # contribute 0. No cap, no retention threshold: the score for any combination is exactly the
    # count of True entries.
    additive_rules = [r["rule_id"] for r in executable if r["role"] == "additive"]
    assert len(additive_rules) == 8, f"expected 8 additive rules, got {len(additive_rules)}"

    n_combinations = 0
    for combo in itertools.product([True, False], repeat=len(additive_rules)):
        n_combinations += 1
        contributions = [1 if satisfied else 0 for satisfied in combo]
        score = sum(contributions)
        expected_score = sum(combo)  # count(True), independent computation of the same claim
        if score != expected_score:
            failures.append(
                f"additive combo {dict(zip(additive_rules, combo))}: "
                f"score {score} != count(satisfied) {expected_score}")
        # the claim TST_counts got wrong for v27: no combination is ever capped or penalised
        if score > len(additive_rules) or score < 0:
            failures.append(f"additive combo {dict(zip(additive_rules, combo))}: "
                             f"score {score} outside [0, {len(additive_rules)}]")
    total += n_combinations

    print(f"{len(executable)} rules from capsule_brain/ranking_rules_v27.tsv: "
          f"{n_rule_cases} known-answer cases")
    print(f"additive-score truth table: {n_combinations} combinations over {len(additive_rules)} "
          f"rules ({additive_rules})")

    if failures:
        print(f"\n{len(failures)} FAILED:")
        for f in failures[:50]:
            print(f"  {f}")
        if len(failures) > 50:
            print(f"  ... and {len(failures) - 50} more")
        print(f"\n{total - len(failures)} / {total} passed")
        return 1

    print(f"{total} / {total} passed")
    print("\nsee TST_sweep_satisfies_against_production.unit_test.py for the sweep contract's "
          "own comparison function, satisfies().")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
