"""workdir.py - the one place that knows how this repo's folders map onto the layout the ranking code was written for.

The ranking code (code/) is the original capsule code (two recorded edits, see PROVENANCE.md). It looks for its files by the capsule's own folder names, so each run
builds a temporary working copy in which the repo folders appear under those names:

    repo                                   working copy (what the code sees)
    analysis.yaml                      ->  analysis.yaml
    rules/                             ->  capsule_brain/
    code/                              ->  02_code/
    inputs/candidate_data_v02.tsv      ->  04_tables/candidate_data_v02.tsv
    inputs/*  (files, not subfolders)  ->  08_source_data/routed_input/
    tests/                             ->  tests/

Nothing in the repo is written to; the working copy is deleted at the end of the run.
"""
import shutil
from pathlib import Path

DERIVED = "01_analysis_output/derived"
CANDIDATE = "candidate_data_v02.tsv"
FOLDERS = [("rules", "capsule_brain"), ("code", "02_code")]


def build(repo, work, with_tests=True, say=None):
    """Create the working copy of the repo at `work`. Returns the list of (repo path, working-copy path) it made."""
    repo, work = Path(repo), Path(work)
    made = []
    ign = shutil.ignore_patterns("__pycache__", "*.pyc")

    def put(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=ign)
        else:
            shutil.copy2(src, dst)
        made.append((str(src.relative_to(repo)).replace("\\", "/"), str(dst.relative_to(work)).replace("\\", "/")))
        if say:
            say("   %-34s -> %s" % made[-1])

    put(repo / "analysis.yaml", work / "analysis.yaml")
    for a, b in FOLDERS:
        put(repo / a, work / b)
    put(repo / "inputs" / CANDIDATE, work / "04_tables" / CANDIDATE)
    ri = work / "08_source_data" / "routed_input"
    ri.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted((repo / "inputs").iterdir()):
        if f.is_file() and f.name != CANDIDATE and f.suffix != ".md":   # inputs/README.md is documentation, not an input
            shutil.copy2(f, ri / f.name)
            n += 1
    made.append(("inputs/ (%d files)" % n, "08_source_data/routed_input/"))
    if say:
        say("   %-34s -> %s" % made[-1])
    if with_tests:
        put(repo / "tests", work / "tests")
    for d in (DERIVED, "04_tables"):
        (work / d).mkdir(parents=True, exist_ok=True)
    return made
