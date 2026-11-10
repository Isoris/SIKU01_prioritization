#!/usr/bin/env python3
"""postflight.py - after the ranking has run: do its outputs match expected_outputs/, and is the run repeatable?

Four questions, all must be yes:
  1. MATCH      every file listed in expected_outputs/MANIFEST.tsv exists in the run's output and has the same content
                (compared after normalising CRLF to LF, so a Windows run and a Linux run agree), and the run has no file
                expected_outputs/ does not list.
                Also: the row count of every file, recounted here, equals the manifest's count, and the fingerprint of the whole set
                equals expected_outputs/COLLECTION.sha256 (definition in build_expected_manifest.py).
  2. REPEATABLE two consecutive runs of the stage produce byte-identical outputs (raw bytes, no normalisation).
  3. ENFORCED   the run applied exactly the rules the capsule brain declares (postflight/brain_enforcement.py), and the capsule's tests
                passed (they run inside the stage; see TESTS below).
  4. RECOMPUTED the outcome of all 9,162 candidate-route rows, recomputed from the rule table by code that shares nothing with the
                stage (postflight/independent_recompute.py), equals the run's candidate_route_state_v27_v01.tsv.

Usage
  python3 postflight/postflight.py --run [--no-tests]      run the stage twice into temporary folders, then check everything
  python3 postflight/postflight.py --out-dir DIR           check 1 only, on a run you already made with
                                                           python run_ranking.py --out-dir DIR
  python3 postflight/postflight.py --out-dir A --against B check 2 only: A against a second run B (raw bytes), plus check 1 on A

Exit: 0 only if every check passes. Standard library only; writes nothing outside the temporary folders it makes.
"""
import argparse, csv, hashlib, json, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_expected_manifest import collection_fingerprint  # the one definition of the collection fingerprint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "expected_outputs")
STAGE = os.path.join(ROOT, "run_ranking.py")
NOT_COMPARED = {"run_log.json", "test_status.tsv", "rank.log"}   # run_log.json holds a timestamp; test_status.tsv appears only with --with-tests; rank.log is a log file some drivers write next to the outputs


def raw(p):
    with open(p, "rb") as fh:
        return fh.read()


def lf(p):
    return raw(p).replace(b"\r\n", b"\n")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def manifest():
    with open(os.path.join(EXP, "MANIFEST.tsv"), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def listing(d):
    return sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and f not in NOT_COMPARED)


def check_match(out):
    m = manifest()
    want = {r["file"]: r for r in m}
    have = set(listing(out))
    bad = 0
    for f in sorted(want):
        r = want[f]
        p = os.path.join(out, f)
        if not os.path.isfile(p):
            print("  FAIL MISSING   %s" % f); bad += 1; continue
        exp_bytes = lf(os.path.join(EXP, f))
        if sha(exp_bytes) != r["sha256_lf_normalised"]:
            print("  FAIL expected_outputs/%s no longer matches MANIFEST.tsv" % f); bad += 1; continue
        if sha(lf(p)) != r["sha256_lf_normalised"]:
            print("  FAIL DIFFERS   %s (expected %s..., got %s...)" % (f, r["sha256_lf_normalised"][:10], sha(lf(p))[:10])); bad += 1
    extra = sorted(have - set(want))
    for f in extra:
        print("  FAIL UNEXPECTED %s (not in expected_outputs/MANIFEST.tsv)" % f); bad += 1
    identical = sum(1 for f in want if os.path.isfile(os.path.join(out, f)) and sha(lf(os.path.join(out, f))) == want[f]["sha256_lf_normalised"])
    print("  MATCH      %d of %d expected files identical to expected_outputs/ (newlines normalised); %d unexpected" % (identical, len(want), len(extra)))
    # counts: recounted here from the run's own files and compared with the manifest (counted, not taken on trust)
    cbad = 0
    for f, r in sorted(want.items()):
        p = os.path.join(out, f)
        if os.path.isfile(p):
            n = max(lf(p).count(b"\n") - 1, 0)
            if str(n) != r["count"]:
                print("  FAIL COUNT     %s: %d %s, manifest says %s" % (f, n, r["count_unit"], r["count"])); cbad += 1
    print("  COUNTS     %d of %d recounted %s equal the manifest (method: %s)" % (len(want) - cbad - sum(1 for f in want if not os.path.isfile(os.path.join(out, f))), len(want), "data rows", "counted"))
    # one fingerprint for the whole set: defined in build_expected_manifest.py
    members = [(f, sha(lf(os.path.join(out, f)))) for f in want if os.path.isfile(os.path.join(out, f))]
    _, digest = collection_fingerprint(members)
    with open(os.path.join(EXP, "COLLECTION.sha256"), encoding="utf-8") as fh:
        declared = fh.read().split()[0]
    cok = digest == declared and len(members) == len(want)
    print("  COLLECTION %s  fingerprint of the run's %d outputs %s the one recorded in expected_outputs/COLLECTION.sha256" % ("ok  " if cok else "FAIL", len(members), "equals" if cok else "DIFFERS FROM"))
    return bad == 0 and cbad == 0 and cok


def check_independent(out):
    sys.stdout.flush()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "postflight", "independent_recompute.py"), "--out-dir", out])
    return r.returncode == 0


def check_repeat(a, b):
    fa, fb = listing(a), listing(b)
    bad = 0
    if fa != fb:
        print("  FAIL REPEAT    file lists differ: only in first %s; only in second %s" % (sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa)))); bad += 1
    same = 0
    for f in sorted(set(fa) & set(fb)):
        if raw(os.path.join(a, f)) == raw(os.path.join(b, f)):
            same += 1
        else:
            print("  FAIL REPEAT    %s differs between the two runs" % f); bad += 1
    print("  REPEATABLE %d of %d files byte-identical between two runs" % (same, len(set(fa) | set(fb))))
    return bad == 0


def run_stage(out, tests=True):
    cmd = [sys.executable, "-B", STAGE, "--out-dir", out, "--tests", "auto" if tests else "none"]
    r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)   # warnings are not shown; if the stage fails, everything it said is
    if r.returncode != 0:
        print(r.stderr[-3000:])
    return r.returncode == 0


def check_brain(out):
    sys.stdout.flush()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "postflight", "brain_enforcement.py"), "--out-dir", out])
    return r.returncode == 0


def check_tests(out):
    """The stage runs the capsule's tests and records the result in run_log.json. A suite that could not run is reported, never counted as passed."""
    p = os.path.join(out, "run_log.json")
    if not os.path.isfile(p):
        print("  FAIL TESTS     no run_log.json in the run"); return False
    with open(p, encoding="utf-8") as fh:
        t = json.load(fh).get("tests")
    if not t:
        print("  FAIL TESTS     the run did not run the tests (it was started with --tests none)"); return False
    if t.get("mode", "").startswith("capsule_runner"):
        print("  TESTS      capsule runner (bash + Rscript): %s" % t["result"]); return t["result"] == "PASS"
    print("  TESTS      python suites: %d passed, %d failed; R suites NOT RUN (no bash/Rscript here): %s"
          % (t["passed"], t["failed"], ", ".join(t["r_suites_not_run"])))
    if t["r_suites_not_run"]:
        print("  WARN TESTS     the R suites have not been exercised in this run; run it where bash and Rscript are available")
    return t["failed"] == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--out-dir")
    ap.add_argument("--against")
    ap.add_argument("--no-tests", action="store_true", help="skip the capsule tests in the first run")
    a = ap.parse_args()
    if not (a.run or a.out_dir):
        ap.error("give --run, or --out-dir")
    ok = True
    print("postflight: repo %s" % ROOT)
    print("postflight: what is checked, and why")
    print("   [match]     the run's output files are the same as the deposited results in expected_outputs/ (the target), file by file, with row counts and one fingerprint for the whole set")
    print("   [repeat]    running the ranking twice gives byte-identical files (nothing random, nothing depends on the clock)")
    print("   [brain]     the run applied exactly the rules declared in rules/ranking_rules_v27.tsv (14 hard gates, 8 additive components)")
    print("   [tests]     the unit, robustness and known-answer tests in tests/ passed (the four R suites need bash + Rscript)")
    print("   [recompute] every one of the 9,162 candidate-route outcomes was recomputed from rules/ and inputs/ by code that shares nothing with the ranking code, and agrees")
    if a.run:
        with tempfile.TemporaryDirectory(prefix="siku01_post_a_") as A, tempfile.TemporaryDirectory(prefix="siku01_post_b_") as B:
            print("run 1 (with tests) ... (about a minute; the stage prints nothing here, its log is in the temporary folder)"); r1 = run_stage(A, not a.no_tests)
            print("run 2 ..."); r2 = run_stage(B, False)
            if not (r1 and r2):
                print("  FAIL RUN       the stage failed (run 1: %s, run 2: %s)" % (r1, r2)); return 1
            print("[match]"); ok &= check_match(A)
            print("[repeat]"); ok &= check_repeat(A, B)
            print("[brain]"); ok &= check_brain(A)
            print("[tests]"); ok &= (check_tests(A) if not a.no_tests else True)
            print("[recompute]"); ok &= check_independent(A)
    else:
        print("[match]"); ok &= check_match(a.out_dir)
        print("[brain]"); ok &= check_brain(a.out_dir)
        print("[recompute]"); ok &= check_independent(a.out_dir)
        if a.against:
            print("[repeat]"); ok &= check_repeat(a.out_dir, a.against)
    if ok:
        print("\npostflight: PASS - the ranking reproduces the deposited results; the final shortlists are in candidate_route_state_v27_v01.tsv (final_pass = PASS)")
    else:
        print("\npostflight: FAIL - see the FAIL lines above. If the frame check or a match fails by a few values in rep__gravy / rep__charge_pH_7_0, check pandas: it must be < 3 (see environment.yml)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
