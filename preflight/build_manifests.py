#!/usr/bin/env python3
"""build_manifests.py - (re)write preflight/manifests/{inputs,contracts,tests,references}.tsv from the files as they are NOW.

Run it only when a frozen file is changed on purpose. The manifests are what preflight.py checks against; regenerating them
after an accidental edit would hide the edit, so review the diff before committing.
Columns: path (relative to the repo root), sha256_lf (newline-normalised), bytes, role.
"""
import csv, hashlib, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(ROOT, "preflight", "manifests")
os.makedirs(M, exist_ok=True)


def sha_lf(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()


def walk(rel):
    base = os.path.join(ROOT, rel)
    if os.path.isfile(base):
        yield rel
        return
    for r, ds, fs in os.walk(base):
        ds[:] = sorted(d for d in ds if d != "__pycache__")
        for f in sorted(fs):
            if f.endswith(".pyc"):
                continue
            yield os.path.relpath(os.path.join(r, f), ROOT).replace(os.sep, "/")


CATS = {
    "inputs": [("inputs", "the 13 frozen *_by_pangenome_id tables, the literature inputs, the lock (route_manifest.tsv), the candidate frame, the figure inputs")],
    "contracts": [("analysis.yaml", "canonical_run order and declared parameters (what is input, what is the target output)"),
                  ("rules", "the 23 rules, their resolved parameters, the sweep plan and the test contracts"),
                  ("code", "the ranking code, unchanged from capsule ANL_A6434"),
                  ("run_ranking.py", "the stage launcher"), ("workdir.py", "the folder mapping used by the launcher and the preflight"),
                  ("postflight", "the post-flight checks (a change to a checker is a change to what counts as passing)"),
                  ("expected_outputs", "the target results a run is compared with")],
    "tests": [("tests", "unit, robustness and known-answer suites, shared helpers, RULE_TEST_INDEX_v27.tsv")],
    "references": [("environment.yml", "the pinned environment"), ("docs", "where each frozen table came from"),
                   ("raw", "the raw archives (Panaroo output, input genomes, core alignments) and their records")],
}
for cat, items in CATS.items():
    rows = []
    for rel, role in items:
        for f in walk(rel):
            rows.append((f, sha_lf(os.path.join(ROOT, f)), os.path.getsize(os.path.join(ROOT, f)), role))
    with open(os.path.join(M, cat + ".tsv"), "w", newline="\n", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["path", "sha256_lf", "bytes", "role"])
        w.writerows(rows)
    print("%-11s %4d files" % (cat, len(rows)))
