"""Checks on a finished run. Three questions:

    compare_with_expected   are the 21 result tables the same as the deposited ones (expected/tables/)?
    compare_runs            do two runs give byte-identical files (nothing random, nothing depends on the clock)?
    independent_recompute   does a second, separate implementation of the rules give the same state for all 9,162 candidates?

independent_recompute deliberately uses nothing from rules.py or ranking.py: it reads the rule table and the assembled input table
with its own code, recomputes the five population thresholds with its own quantile function, and evaluates every rule with its own
comparison. If the two implementations agree, the result does not rest on one piece of code.

File contents are compared after reading CRLF as LF, because one deposited table was written on Windows.
"""
import csv
import hashlib
import math

from . import layout

csv.field_size_limit(2**31 - 1)
MANIFEST = "MANIFEST.tsv"


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _lf(path):
    with open(path, "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def _sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------ expected tables
def build_manifest(expected_dir=layout.EXPECTED):
    """(Re)write expected/MANIFEST.tsv from the files in expected/tables/. Only for a deliberate, reviewed change of the reference."""
    lines = ["file\tsha256_lf\tbytes_as_deposited\tdata_rows\n"]
    for p in sorted((expected_dir / "tables").iterdir(), key=lambda q: q.name.encode()):
        b = _lf(p)
        n_rows = max(b.count(b"\n") - 1, 0)
        lines.append(f"{p.name}\t{_sha(b)}\t{p.stat().st_size}\t{n_rows}\n")
    with open(expected_dir / MANIFEST, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(lines)
    return len(lines) - 1


def compare_with_expected(tables_dir, expected_dir=layout.EXPECTED):
    """Returns (n identical, n expected, problems)."""
    want = {r["file"]: r for r in _rows(expected_dir / MANIFEST)}
    problems, same = [], 0
    for name, r in sorted(want.items()):
        ref = expected_dir / "tables" / name
        if not ref.is_file() or _sha(_lf(ref)) != r["sha256_lf"]:
            problems.append(f"expected/tables/{name} is missing or no longer matches expected/{MANIFEST}")
            continue
        p = tables_dir / name
        if not p.is_file():
            problems.append(f"MISSING  {name}")
            continue
        b = _lf(p)
        rows = max(b.count(b"\n") - 1, 0)
        if _sha(b) == r["sha256_lf"]:
            same += 1
        else:
            problems.append(f"DIFFERS  {name} ({rows} rows; expected {r['data_rows']})")
    for p in sorted(tables_dir.iterdir()):
        if p.is_file() and p.name not in want:
            problems.append(f"UNEXPECTED  {p.name} is not one of the expected tables")
    return same, len(want), problems


# ------------------------------------------------------------------------------------------------ two runs
def compare_runs(run_a, run_b, ignore=("run_log.json", "VERDICT.txt", "reproduce.log")):
    """Compare every file of two run folders byte for byte. Returns (n identical, n files, problems)."""
    def listing(d):
        return {str(p.relative_to(d)).replace("\\", "/"): p for p in d.rglob("*") if p.is_file() and p.name not in ignore}
    a, b = listing(run_a), listing(run_b)
    problems = [f"only in one run: {n}" for n in sorted(set(a) ^ set(b))]
    same = 0
    for n in sorted(set(a) & set(b)):
        if a[n].read_bytes() == b[n].read_bytes():
            same += 1
        else:
            problems.append(f"differs between the two runs: {n}")
    return same, len(set(a) | set(b)), problems


# ------------------------------------------------------------------------------------------------ independent recomputation
_MISSING = ("", "NA", "NaN", "nan", "None", "NULL")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _quantile(xs, p):
    """Linear interpolation between order statistics (R type 7, the default of numpy and pandas)."""
    xs = sorted(xs)
    h = (len(xs) - 1) * p
    lo, hi = math.floor(h), math.ceil(h)
    return xs[lo] + (xs[hi] - xs[lo]) * (h - lo)


def independent_recompute(tables_dir, rules_dir=layout.RULES):
    """Recompute the state of every candidate from the rule table and the assembled inputs; compare with the run's state table.

    Returns a dict: thresholds (n recomputed, n equal), rows (recomputed, differing, missing, extra), examples, ok.
    """
    rules = [r for r in _rows(rules_dir / layout.RULE_TABLE) if r["role"] in ("hard", "additive")]
    params = _rows(rules_dir / layout.PARAMETER_TABLE)
    inputs = _rows(tables_dir / layout.T_RANKING_INPUTS)
    run_state = {r["candidate_key"]: r for r in _rows(tables_dir / layout.T_STATE)}

    resolved, thr_bad = {}, []
    for p in params:
        xs = [x for x in (_num(r[p["source_column"]]) for r in inputs) if x is not None]
        resolved[p["declared_symbol"]] = _quantile(xs, float(p["quantile_probability"]))
        if abs(resolved[p["declared_symbol"]] - float(p["resolved_value"])) >= 1e-12 or len(xs) != int(p["n_reference"]):
            thr_bad.append(p["declared_symbol"])

    def holds(rule, row):
        raw = row[rule["variable"]].strip()
        op, th = rule["operator"], rule["threshold"].strip()
        if raw in _MISSING:
            return None
        x = _num(raw)
        if op == "==":
            return (x == float(th)) if (x is not None and _num(th) is not None) else raw == th
        if x is None:
            return None
        if op == "BETWEEN":
            lo, hi = (float(t) for t in th.split(";"))
            return lo <= x <= hi
        t = resolved[th] if th in resolved else float(th)
        return {">=": x >= t, ">": x > t, "<=": x <= t, "<": x < t}[op]

    n = differ = missing = 0
    examples, seen = [], set()
    for route in layout.ROUTES:
        applicable = [x for x in rules if x["routes"].strip() == "all" or route in [t.strip() for t in x["routes"].split(";")]]
        for row in inputs:
            key = f"{row['pangenome_id']}:{route}"
            seen.add(key)
            hp = hf = hn = add = nadd = 0
            for x in applicable:
                v = holds(x, row)
                if x["role"] == "hard":
                    hp, hf, hn = hp + (v is True), hf + (v is False), hn + (v is None)
                else:
                    nadd += 1
                    add += 1 if v else 0
            final = "FAIL" if hf else ("NOT_EVALUABLE" if hn else "PASS")
            o = run_state.get(key)
            if o is None:
                missing += 1
                continue
            n += 1
            mine = (str(hp + hf + hn), str(hp), str(hf), str(hn), str(add), str(nadd), final)
            theirs = (o["n_hard_applicable"], o["n_hard_pass"], o["n_hard_fail"], o["n_hard_not_evaluable"],
                      o["additive_score"], o["n_additive_applicable"], o["final_pass"])
            if mine != theirs:
                differ += 1
                if len(examples) < 3:
                    examples.append(f"{key}: recomputed {mine}, run {theirs}")
    extra = len(set(run_state) - seen)
    ok = not thr_bad and differ == 0 and missing == 0 and extra == 0 and n == len(inputs) * len(layout.ROUTES)
    return dict(thresholds=len(params), thresholds_equal=len(params) - len(thr_bad), rows=n, differ=differ, missing=missing,
                extra=extra, examples=examples, ok=ok)
