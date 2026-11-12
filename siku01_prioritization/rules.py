"""The rule table and the one comparison every step uses.

The rules are data, not code: rules/ranking_rules_v27.tsv holds the 23 rules (1 declaration, 14 hard gates, 8 additive components)
with, for each, the routes it applies to, the variable it reads, the operator and the threshold. Nothing about a rule is written in
the code, so a rule cannot drift from its declaration.

    hard gate   PASS / FAIL / NOT_EVALUABLE. A candidate is eligible on a route when every hard gate of that route is PASS.
    additive    +1 when satisfied, 0 otherwise. It never changes eligibility.
    missing     a missing value never satisfies a condition: a hard gate reports NOT_EVALUABLE, an additive component adds 0.

Five thresholds are statistics of the candidate population itself (the third quartile of four codon/GC measures and the median CDS
length over the 1,527 entry orthogroups). Their values are frozen in rules/rule_parameter_resolution_v02.tsv; check_parameters()
recomputes them from the data on every run and stops if they differ.
"""
import math
from collections import Counter

import pandas as pd

from . import layout
from .tables import read_tsv

PASS, FAIL, NOT_EVALUABLE = "PASS", "FAIL", "NOT_EVALUABLE"
MISSING = {"", "NA", "NaN", "nan", "None", "NULL"}
OPERATORS = {"==", "<", "<=", ">", ">=", "BETWEEN"}
MISSING_POLICY = {"hard": "not_evaluable", "additive": "skip"}   # what the code implements; the table must say the same


class RuleTableError(ValueError):
    """The rule table does not describe the rule set this code implements."""


def load_rules(rules_dir=layout.RULES):
    """Read and validate the rule table. Returns (rules, symbol) where symbol maps a threshold name to its frozen value."""
    rules = read_tsv(rules_dir / layout.RULE_TABLE)
    params = read_tsv(rules_dir / layout.PARAMETER_TABLE)
    symbol = {p["declared_symbol"]: float(p["resolved_value"]) for p in params}

    ids = [r["rule_id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise RuleTableError("rule_id is not unique")
    roles = Counter(r["role"] for r in rules)
    if dict(roles) != {"declaration": 1, "hard": 14, "additive": 8}:
        raise RuleTableError(f"expected 1 declaration + 14 hard + 8 additive rules, found {dict(roles)}")
    for r in rules:
        rid, role = r["rule_id"], r["role"]
        if role == "declaration":
            continue
        if r["operator"] not in OPERATORS:
            raise RuleTableError(f"{rid}: unknown operator {r['operator']!r}")
        bad = [x for x in routes_of(r, layout.ROUTES) if x not in layout.ROUTES]
        if bad or not routes_of(r, layout.ROUTES):
            raise RuleTableError(f"{rid}: routes {r['routes']!r} do not all name one of {layout.ROUTES}")
        if r["missing_policy"].strip() != MISSING_POLICY[role]:
            raise RuleTableError(f"{rid}: missing_policy is {r['missing_policy']!r}, the code implements {MISSING_POLICY[role]!r}")
        if r["score_delta"].strip() != ("1" if role == "additive" else "0"):
            raise RuleTableError(f"{rid}: score_delta is {r['score_delta']!r}; an additive component adds 1, a hard gate adds 0")
        thr = r["threshold"].strip()
        if r["operator"] == "BETWEEN":
            lo, hi = (float(t) for t in thr.split(";"))
            if not lo <= hi:
                raise RuleTableError(f"{rid}: BETWEEN bounds {thr!r} are not ordered")
        elif r["operator"] != "==" and thr not in symbol:
            float(thr)   # a numeric rule needs a number or a declared symbol
    return rules, symbol


def executable(rules):
    """The 22 rules that are evaluated (everything except the declaration of the entry population)."""
    return [r for r in rules if r["role"] in ("hard", "additive")]


def routes_of(rule, all_routes):
    spec = rule["routes"].strip()
    if spec == "all":
        return list(all_routes)
    return [x.strip() for x in spec.split(";") if x.strip()]


def threshold_of(rule, symbol):
    """(threshold, symbol name or None). A symbolic threshold such as Q3_cai_ec is replaced by its frozen value."""
    raw = rule["threshold"].strip()
    if raw in symbol:
        return symbol[raw], raw
    return raw, None


def evaluate(value, op, thr):
    """Does `value` satisfy `op thr`? Returns True, False, or None when the value is missing or not a number (not evaluable)."""
    if value is None or str(value).strip() in MISSING:
        return None
    v = str(value).strip()
    if op == "==":
        try:   # compare as numbers when both sides are numbers, as text otherwise ("single", "yes")
            return float(v) == float(thr)
        except (TypeError, ValueError):
            return v == str(thr).strip()
    try:
        x = float(v)
    except ValueError:
        return None
    if op == "BETWEEN":   # both bounds included
        lo, hi = (float(t) for t in str(thr).split(";"))
        return lo <= x <= hi
    t = float(thr)
    return {"<": x < t, "<=": x <= t, ">": x > t, ">=": x >= t}[op]


def reference_population(frame):
    """One row per orthogroup, in first-seen order: the population the distribution-derived thresholds are computed on."""
    ref = {}
    for r in frame:
        ref.setdefault(r["pangenome_id"], r)
    return ref


def check_parameters(frame, rules_dir=layout.RULES):
    """Recompute the five distribution-derived thresholds from the data and compare them with the frozen values.

    Returns the list of comparisons; raises RuleTableError if one differs (tolerance 1e-12) or the population size is not as declared.
    """
    ref = pd.DataFrame(list(reference_population(frame).values()))
    report = []
    for p in read_tsv(rules_dir / layout.PARAMETER_TABLE):
        x = pd.to_numeric(ref[p["source_column"]], errors="coerce").dropna()
        got = float(x.quantile(float(p["quantile_probability"])))   # linear interpolation between order statistics
        want = float(p["resolved_value"])
        ok = len(x) == int(p["n_reference"]) and math.isclose(got, want, rel_tol=0, abs_tol=1e-12)
        report.append(dict(symbol=p["declared_symbol"], rule_id=p["rule_id"], statistic=p["statistic_label"], n=len(x),
                           frozen=want, recomputed=got, ok=ok))
        if not ok:
            raise RuleTableError(f"{p['declared_symbol']}: frozen value {want!r} (n={p['n_reference']}), "
                                 f"recomputed {got!r} (n={len(x)}) from {p['source_column']}")
    return report
