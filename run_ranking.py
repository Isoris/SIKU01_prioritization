#!/usr/bin/env python3
"""run_ranking.py - runs the 23-rule candidate ranking. It runs the original ranking code (code/); it contains no ranking logic.

WHAT GOES IN   inputs/  the 13 frozen *_by_pangenome_id tables, the literature inputs, route_manifest.tsv (the lock: their checksums) and candidate_data_v02.tsv
               rules/   ranking_rules_v27.tsv = the 23 rules, their resolved thresholds, the sweep plan, the test contracts
WHAT COMES OUT --out-dir  the 18 ranking tables, among them candidate_route_state_v27_v01.tsv (final_pass per candidate and route), and run_log.json
TARGET         expected_outputs/  the 21 deposited result files; postflight/postflight.py compares a run with them


The 23 rules live in rules/ and the code in code/ is capsule ANL_A6434's own, copied unmodified (PROVENANCE.md records where each file
came from). This file only sets up a clean working copy (workdir.py), runs the scripts in the order of analysis.yaml, and gathers what they write.

Steps, each stopping the stage if it fails
  1  02_code/code_A6434_verify_input_lock_v01.py   the 13 frozen *_by_pangenome_id tables are byte-identical to the lock in
                                                   inputs/route_manifest.tsv
  2  02_code/build_literature_by_pangenome_id_v01.py   literature evidence per pangenome_id (a layer step 3 reads)
  3  02_code/code_A6434_inputs_v01.py              assembles ranking_inputs_by_pangenome_id (1,527 orthogroups x 429 columns) from the
                                                   frozen tables, plus its input audit and spine-exclusion tables
  4  postflight/frame_check.py                     the frozen candidate frame ranking/04_tables/candidate_data_v02.tsv equals the
                                                   step-3 table in every column they share (63 of 69), for all 9,162 rows
  5  02_code/run_A6434_canonical_v01.py            the six scripts of analysis.yaml canonical_run.scripts (literature, production_v27,
                                                   freeze_sweeps, execute_sweeps, perturbation, rule_authority_test)

Why step 4 exists: the capsule has no script that expands ranking_inputs to the route grain (candidate_data_v01 -> v02 is a
deposit; analysis.yaml marks it rebuildable: false). It is therefore frozen, and checked against what the capsule's own code rebuilds.

Writes in --out-dir: the 18 tables of the ranking, ranking_inputs_by_pangenome_id_v01.tsv and its two audit tables, the literature
table, and run_log.json (run id, command, versions, per-step status, output hashes, collection fingerprint).
The capsule's tests run after the ranking (step 6; --tests none to skip). With bash and Rscript on the PATH the capsule's own
tests/run_all_tests_A6434_v01.sh runs all 11 suites (R: TST_carriage, TST_conservation, TST_gene_model, TST_tmh need bio3d, Biostrings,
digest). Without them the 4 Python suites (TST_execution, TST_numerical x2, TST_perturbation) run directly and the R suites are reported
as NOT RUN - never as passed.

Variant runs (tuning): --brain DIR overlays the brain tables found in DIR (same file names as rules/) on the working copy only;
the repo is never touched. The run is then labelled "variant" in run_log.json, and the capsule's rule_authority_test (step 5, script 6)
is skipped, because it asserts the DECLARED rules and a deliberate change to a rule is a change to the declaration. tuning/tune.py drives this.

Usage:  python3 Scripts/12_frozen_inputs_to_ranked_candidates.py --out-dir DIR [--run-id ID] [--tests auto|none] [--brain DIR]
Exit:   0 only if every step passed and no test failed.
"""
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile, time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "postflight"))
sys.path.insert(0, str(HERE))
import workdir
DERIVED = workdir.DERIVED
GATHER = ["04_tables/literature_by_pangenome_id_v01.tsv",
          "04_tables/tbl_A6434_01_input_audit_v01.tsv",
          "04_tables/tbl_A6434_02_spine_exclusions_v01.tsv"]
# (the files the working copy is built from, and where they land, are listed in workdir.py)


STEP_WHY = {"1_input_lock": "are the 13 frozen input tables byte-identical to the lock?",
            "2_literature": "attach the literature evidence per orthogroup",
            "3_assemble_ranking_inputs": "join the 13 tables into one row per orthogroup",
            "4_frame_check": "does the frozen candidate frame equal what the code rebuilds from the tables?",
            "5_canonical_ranking": "apply the 23 rules, the sweeps and the perturbation analyses"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ver(pkg):
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def run_tests(work, env, out):
    """Run the capsule's tests in the working copy. Returns (record for run_log.json, return code)."""
    sh, rs = shutil.which("bash"), shutil.which("Rscript")
    status = out / "test_status.tsv"
    if sh and rs:
        t = subprocess.run([sh, "tests/run_all_tests_A6434_v01.sh"], cwd=str(work), env=dict(env, SIKU01_GATE_STATUS=str(status)))
        return {"mode": "capsule_runner (bash + Rscript)", "result": "PASS" if t.returncode == 0 else "FAIL rc=%d" % t.returncode}, t.returncode
    rows, failed, passed = [], 0, 0
    env2 = dict(env, SIKU01_CODE_DIR=str(work / "tests" / "_shared"))
    for f in sorted((work / "tests").glob("TST_*/*unit_test.py")):
        r = subprocess.run([sys.executable, "-B", f.name], cwd=str(f.parent), env=env2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rows.append((f.parent.name, "unit", f.name, "PASS" if r.returncode == 0 else "FAIL"))
        passed += r.returncode == 0
        failed += r.returncode != 0
    not_run = sorted(d.name for d in (work / "tests").glob("TST_*") if not list(d.glob("*unit_test.py")) or list(d.glob("*unit_test.R")))
    for d in not_run:
        rows.append((d, "unit", "*.R", "NOT_RUN_NO_BASH_OR_RSCRIPT"))
    with open(status, "w", encoding="utf-8", newline="") as fh:
        fh.write("suite\tkind\tscript\tresult\n" + "".join("\t".join(r) + "\n" for r in rows))
    print("tests (python only; no %s on PATH): %d passed, %d failed; R suites NOT RUN: %s" % ("bash/Rscript", passed, failed, ", ".join(not_run)))
    return {"mode": "python_only", "passed": passed, "failed": failed, "r_suites_not_run": not_run}, (1 if failed else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", default=None, help="identifier of this run; use the run folder name so the two link (default: name of --out-dir)")
    ap.add_argument("--brain", default=None, help="a folder of tuned brain tables to overlay on the working copy (variant run; see tuning/)")
    ap.add_argument("--repo-root", default=str(HERE), help="the repo folder (default: this folder)")
    ap.add_argument("--tests", choices=["auto", "none"], default="auto", help="run the capsule's tests after the ranking (default: auto)")
    a = ap.parse_args()
    root = Path(a.repo_root).resolve()
    out = Path(a.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    missing = [n for n in ("analysis.yaml", "rules", "code", "inputs/candidate_data_v02.tsv", "inputs/route_manifest.tsv") if not (root / n).exists()]
    if missing:
        print("repo %s lacks: %s" % (root, ", ".join(missing)), file=sys.stderr)
        return 2
    print("ranking: repo    = %s" % root)
    print("ranking: inputs  = inputs/ (13 frozen tables + literature inputs + candidate frame; route_manifest.tsv locks their checksums)")
    print("ranking: rules   = rules/ (ranking_rules_v27.tsv = the 23 rules)")
    print("ranking: results = %s ; postflight/postflight.py compares them with expected_outputs/" % out, flush=True)
    log = {"stage": "12_frozen_inputs_to_ranked_candidates", "run_id": a.run_id or out.name, "command": sys.argv,
           "tool_versions": {"python": sys.version.split()[0], "PyYAML": ver("PyYAML"), "pandas": ver("pandas"), "numpy": ver("numpy")},
           "platform": platform.platform(), "repo_root": str(root), "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "steps": [], "tests": None}
    rc = 0
    with tempfile.TemporaryDirectory(prefix="siku01_rank_") as tmp:
        work = Path(tmp) / "cap"
        print("ranking: building a temporary working copy (the code looks for the capsule's folder names):")
        workdir.build(root, work, with_tests=(a.tests == "auto"), say=print)
        if a.brain:
            bdir = Path(a.brain).resolve()
            overlay = {}
            for f in sorted(p for p in bdir.iterdir() if p.is_file()):
                if not (work / "capsule_brain" / f.name).is_file():
                    print("--brain: %s is not a brain table of this capsule" % f.name, file=sys.stderr)
                    return 2
                shutil.copy2(f, work / "capsule_brain" / f.name)
                overlay[f.name] = sha256(f)
            log["variant"] = True
            log["brain_overlay_dir"] = str(bdir)
            log["brain_overlay_sha256"] = overlay
            log["skipped"] = ["02_code/code_A6434_rule_authority_test_v02.py (asserts the declared rules)"]
            print("VARIANT RUN: brain tables overlaid from %s: %s" % (bdir, ", ".join(overlay)))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0", ANL_ROOT=str(work))
        py = [sys.executable, "-B"]
        steps = [("1_input_lock", py + ["02_code/code_A6434_verify_input_lock_v01.py"]),
                 ("2_literature", py + ["02_code/build_literature_by_pangenome_id_v01.py"]),
                 ("3_assemble_ranking_inputs", py + ["02_code/code_A6434_inputs_v01.py"]),
                 ("4_frame_check", py + [str(HERE / "postflight" / "frame_check.py"),
                                         "--ranking-inputs", str(work / DERIVED / "ranking_inputs_by_pangenome_id_v01.tsv"),
                                         "--candidate-data", str(work / "04_tables" / "candidate_data_v02.tsv")]),
                 ("5_canonical_ranking", py + ["02_code/run_A6434_canonical_v01.py", str(work)])]
        if a.brain:   # the capsule's own order (analysis.yaml canonical_run.scripts), minus the declaration test
            import yaml
            order = (yaml.safe_load((work / "analysis.yaml").read_text(encoding="utf-8"))["analysis"].get("canonical_run") or {}).get("scripts") or []
            steps = steps[:-1] + [("5_%s" % Path(sc).stem, py + [sc] + ([str(work)] if "freeze_sweeps" in sc else []))
                                  for sc in order if "rule_authority_test" not in sc]
        for name, cmd in steps:
            print("== step %s  (%s)" % (name, STEP_WHY.get(name, "")), flush=True)
            r = subprocess.run(cmd, cwd=str(work), env=env)
            log["steps"].append({"step": name, "returncode": r.returncode})
            if r.returncode != 0:
                print("step %s failed (rc=%d); the stage stops here" % (name, r.returncode), file=sys.stderr)
                rc = r.returncode
                break
        if rc == 0:
            produced = sorted((work / DERIVED).glob("*.tsv")) + [work / g for g in GATHER]
            for p in produced:
                shutil.copy2(p, out / p.name)
            log["outputs"] = {p.name: sha256(out / p.name) for p in produced}
            from build_expected_manifest import collection_fingerprint
            log["output_collection_sha256"] = collection_fingerprint(
                (n, hashlib.sha256((out / n).read_bytes().replace(b"\r\n", b"\n")).hexdigest()) for n in log["outputs"])[1]
            print("ranking: %d tables written to %s" % (len(log["outputs"]), out))
            if a.tests == "auto":
                log["tests"], trc = run_tests(work, env, out)
                rc = rc or trc
    log["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["returncode"] = rc
    (out / "run_log.json").write_text(json.dumps(log, indent=1, sort_keys=True), encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
