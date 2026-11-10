#!/usr/bin/env python3
"""preflight.py - before anything runs: is everything the ranking stands on present and unchanged, and is the environment the right one?

Four categories, each with its own manifest in preflight/manifests/ (path, sha256 of the newline-normalised content, bytes, role):

  inputs      inputs/       the 13 frozen *_by_pangenome_id tables, the literature inputs, the lock (route_manifest.tsv) and the candidate frame
  contracts   rules/ code/ analysis.yaml run_ranking.py postflight/ expected_outputs/    the 23 rules, the ranking code, what declares the run, the target results
  tests       tests/        the unit, robustness and known-answer suites and their index
  references  environment.yml, docs/, raw/                                                the pinned environment, where each table came from, the raw archives

Usage:  python preflight/preflight.py [--only inputs contracts tests references] [--quiet]
Exit:   0 if every REQUIRED check passes. WARN lines (R missing, other package versions) do not fail the run.
It reads files and writes nothing (the input lock is checked in a temporary working copy that is deleted afterwards).
"""
import argparse, csv, hashlib, os, shutil, subprocess, sys, tempfile
from importlib import metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import workdir

csv.field_size_limit(10**9)
CATS = ["inputs", "contracts", "tests", "references"]
RES = {"fail": 0, "warn": 0, "ok": 0}
LEVEL = {"FAIL": "fail", "WARN": "warn", "OK": "ok"}
PINNED = {"pandas": "2.3.3", "numpy": "2.3.4", "PyYAML": "6.0.3"}
WHY = {
    "inputs": "are the frozen input tables the ones the results were made with (same bytes as when they were locked)?",
    "contracts": "are the 23 rules, the ranking code and the target results unchanged, and is the run declared completely?",
    "tests": "are all the tests that the rules point to present and unchanged?",
    "references": "is the environment the one the results were produced and checked with, and are the raw archives intact?",
}


def say(level, cat, msg, quiet=False):
    RES[LEVEL[level]] += 1
    if not (quiet and level == "OK"):
        print("  %-4s %-10s %s" % (level, cat, msg))


def sha_lf(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def rows(p):
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def ver(pkg):
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def check_manifest(cat, quiet):
    mp = os.path.join(ROOT, "preflight", "manifests", cat + ".tsv")
    if not os.path.isfile(mp):
        say("FAIL", cat, "manifest missing: " + mp)
        return
    n = bad = 0
    for r in rows(mp):
        n += 1
        p = os.path.join(ROOT, r["path"])
        if not os.path.isfile(p):
            bad += 1
            say("FAIL", cat, "MISSING  " + r["path"])
        elif sha_lf(p) != r["sha256_lf"]:
            bad += 1
            say("FAIL", cat, "CHANGED  %s (expected %s..., found %s...)" % (r["path"], r["sha256_lf"][:10], sha_lf(p)[:10]))
    say("OK" if not bad else "FAIL", cat, "%d files listed in %s.tsv, %d missing or changed" % (n, cat, bad), quiet and not bad)


def yaml_load(p):
    try:
        import yaml
    except ImportError:
        return None
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def structural_inputs(quiet):
    with tempfile.TemporaryDirectory(prefix="siku01_pre_") as tmp:
        work = os.path.join(tmp, "cap")
        workdir.build(ROOT, work, with_tests=False)
        lock = os.path.join(work, "02_code", "code_A6434_verify_input_lock_v01.py")
        r = subprocess.run([sys.executable, "-B", lock], cwd=work, env=dict(os.environ, ANL_ROOT=work, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True)
    last = [l for l in r.stdout.strip().split("\n") if l.strip()][-1:] or [r.stderr.strip()[-200:]]
    say("OK" if r.returncode == 0 else "FAIL", "inputs", "the input lock (route_manifest.tsv, checked by code/code_A6434_verify_input_lock_v01.py): " + last[0], quiet and r.returncode == 0)
    t = rows(os.path.join(ROOT, "inputs", "candidate_data_v02.tsv"))
    ids = {r["pangenome_id"] for r in t if "pangenome_id" in r}
    ok = len(t) == 9162 and len(ids) == 1527
    say("OK" if ok else "FAIL", "inputs", "candidate_data_v02: %d rows, %d distinct pangenome_id (expected 9,162 = 1,527 orthogroups x 6 routes)" % (len(t), len(ids)), quiet and ok)
    rm = rows(os.path.join(ROOT, "inputs", "route_manifest.tsv"))
    st = {}
    for r in rm:
        st[r.get("status", "")] = st.get(r.get("status", ""), 0) + 1
    say("OK", "inputs", "route_manifest.tsv lists %d inputs: %s (the step 'assemble_ranking_inputs' of run_ranking.py joins them into one table)"
        % (len(rm), ", ".join("%s=%d" % kv for kv in sorted(st.items()))), quiet)


def structural_contracts(quiet):
    rules = rows(os.path.join(ROOT, "rules", "ranking_rules_v27.tsv"))
    ids = [r["rule_id"] for r in rules]
    cnt = {k: sum(1 for r in rules if r["role"] == k) for k in ("hard", "additive", "declaration")}
    ok = len(rules) == 23 and len(set(ids)) == 23 and cnt == {"hard": 14, "additive": 8, "declaration": 1}
    say("OK" if ok else "FAIL", "contracts",
        "ranking_rules_v27: %d records, %s, ids unique=%s (expected 23 = 14 hard + 8 additive + 1 declaration)" % (len(rules), cnt, len(set(ids)) == len(ids)), quiet and ok)
    for fn in ("rule_parameter_resolution_v02.tsv", "ST_A6434_03_parameter_sweep_contract_v02.tsv", "rule_test_contract_v03.tsv", "test_implementation_binding_v03.tsv"):
        t = rows(os.path.join(ROOT, "rules", fn))
        col = "rule_id" if t and "rule_id" in t[0] else None
        unknown = sorted({r[col] for r in t if r.get(col) and r[col] not in ids}) if col else []
        note = (", rule_ids not in ranking_rules_v27: " + ", ".join(unknown[:6])) if unknown else (", every rule_id is in ranking_rules_v27" if col else "")
        say("OK" if not unknown else "WARN", "contracts", "%s: %d rows%s" % (fn, len(t), note), quiet and not unknown)
    implemented = {"hard": "not_evaluable", "additive": "skip"}
    wrong = sorted(r["rule_id"] for r in rules if implemented.get(r["role"]) and r.get("missing_policy") != implemented[r["role"]])
    say("OK" if not wrong else "FAIL", "contracts",
        "missing_policy: hard rules 'not_evaluable', additive rules 'skip' - what the code implements%s" % ("" if not wrong else "; differs for " + ", ".join(wrong)), quiet and not wrong)
    a = yaml_load(os.path.join(ROOT, "analysis.yaml"))
    if a is None:
        say("WARN", "contracts", "PyYAML not installed: the run order in analysis.yaml was not checked (run_ranking.py needs PyYAML)")
        return
    scripts = ((a.get("analysis") or {}).get("canonical_run") or {}).get("scripts") or []
    miss = [s for s in scripts if not os.path.isfile(os.path.join(ROOT, "code", os.path.basename(s)))]
    ok = bool(scripts) and not miss
    say("OK" if ok else "FAIL", "contracts", "analysis.yaml canonical_run: %d scripts declared (in code/), %d missing" % (len(scripts), len(miss)), quiet and ok)


def structural_tests(quiet):
    idx = rows(os.path.join(ROOT, "tests", "RULE_TEST_INDEX_v27.tsv"))
    refs = set()
    for r in idx:
        for k, v in r.items():
            if k and k.endswith("_test") and v:
                for f in v.replace(";", ",").split(","):
                    if f.strip():
                        refs.add(f.strip())
    miss = sorted(f for f in refs if not os.path.isfile(os.path.join(ROOT, f)))
    say("OK" if not miss else "FAIL", "tests", "tests/RULE_TEST_INDEX_v27: %d rules, %d distinct test files named, %d missing%s"
        % (len(idx), len(refs), len(miss), ("" if not miss else ": " + ", ".join(miss[:5]))), quiet and not miss)
    b = rows(os.path.join(ROOT, "rules", "test_implementation_binding_v03.tsv"))
    res = [r["resolved_test_file"] for r in b if r.get("resolved_test_file")]
    miss = [f for f in res if not os.path.isfile(os.path.join(ROOT, f))]
    say("OK" if not miss else "FAIL", "tests", "rules/test_implementation_binding_v03: %d of %d rows resolve to a test file, %d of those missing" % (len(res), len(b), len(miss)), quiet and not miss)
    rs = shutil.which("Rscript")
    if not rs:
        say("WARN", "tests", "Rscript not on PATH: the four R suites (TST_carriage, TST_conservation, TST_gene_model, TST_tmh) cannot run; the Python suites can")
        return
    expr = "for(p in c('bio3d','Biostrings','digest','dplyr')) cat(p, if (requireNamespace(p, quietly=TRUE)) as.character(packageVersion(p)) else 'MISSING', '\\n')"
    out = subprocess.run([rs, "-e", expr], capture_output=True, text=True).stdout.split("\n")
    lack = [l.split()[0] for l in out if l.strip().endswith("MISSING")]
    say("OK" if not lack else "WARN", "tests", "R found; packages: " + "; ".join(l.strip() for l in out if l.strip()), quiet and not lack)


def structural_references(quiet):
    with open(os.path.join(ROOT, "environment.yml"), encoding="utf-8") as fh:
        s = fh.read()
    need = ["python =3.11", "pandas =2.3.3", "numpy =2.3.4", "pyyaml =6.0.3", "r-base 4.3.3", "r-bio3d 2.4.4", "mafft 7.505", "bioconductor-biostrings", "r-digest"]
    lack = [n for n in need if n not in s]
    say("OK" if not lack else "FAIL", "references", ("environment.yml pins " + ", ".join(need)) if not lack else "environment.yml lacks: " + ", ".join(lack), quiet and not lack)
    pv = ver("pandas")
    if pv is None:
        say("FAIL", "references", "pandas is not installed (the ranking needs pandas %s)" % PINNED["pandas"])
    elif int(pv.split(".")[0]) >= 3:
        say("FAIL", "references", "pandas %s is installed; this ranking was produced and is checked with pandas %s. pandas 3 writes some floats with a different last digit, "
            "so the frame check fails on rep__gravy (114 rows) and rep__charge_pH_7_0 (6 rows). Install the environment in environment.yml (pandas < 3) and run again." % (pv, PINNED["pandas"]))
    else:
        dev = ["%s %s (pinned %s)" % (k, ver(k), v) for k, v in PINNED.items() if ver(k) != v]
        py = sys.version.split()[0]
        if not py.startswith("3.11"):
            dev.append("python %s (pinned 3.11)" % py)
        if dev:
            say("WARN", "references", "environment differs from the pinned one: " + "; ".join(dev) + ". Results should still reproduce, but they were only checked with the pinned versions.")
        else:
            say("OK", "references", "python %s, pandas %s, numpy %s, PyYAML %s: the pinned environment" % (py, ver("pandas"), ver("numpy"), ver("PyYAML")), quiet)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", nargs="+", choices=CATS)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    fns = {"inputs": structural_inputs, "contracts": structural_contracts, "tests": structural_tests, "references": structural_references}
    print("preflight: repo %s" % ROOT)
    print("preflight: checks, before anything runs, that everything the ranking stands on is present and unchanged. It writes nothing.")
    for cat in (a.only or CATS):
        print("[%s]  %s" % (cat, WHY[cat]))
        check_manifest(cat, a.quiet)
        try:
            fns[cat](a.quiet)
        except Exception as e:  # a check that cannot run is a failure, never a silent pass
            say("FAIL", cat, "structural check could not run: %s: %s" % (type(e).__name__, e))
    print("\npreflight summary: %d ok, %d warn, %d FAIL" % (RES["ok"], RES["warn"], RES["fail"]))
    if RES["fail"]:
        print("preflight: FAIL - something is missing, changed or the wrong version; fix it before running the ranking")
    else:
        print("preflight: PASS - inputs, rules, code, tests and environment are as locked%s" % (" (%d warning(s) above)" % RES["warn"] if RES["warn"] else ""))
    return 1 if RES["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
