#!/usr/bin/env python3
"""
S00_fetch_genomes_v01.py

FETCH. Pull assemblies from NCBI with the datasets CLI and, when the species has
more than you want, take a defensible sample of them.

    S00_fetch_genomes_v01.py --species "Streptococcus uberis" --strains 50
    S00_fetch_genomes_v01.py --taxid 1346 --strains 50 --assembly-level complete

WHY SAMPLING NEEDS A RULE

    Taking the first N genomes NCBI returns samples by accession order, which
    tracks submission date and submitting laboratory. A panel built that way is
    dominated by whichever outbreak was sequenced most, and every downstream
    lineage and module count inherits that.

    --sample even   spreads the draw across assembly submitters and, where the
                    metadata carries it, across collection year and country, so
                    the panel is not one laboratory's collection. This is the
                    default.
    --sample random with --seed, for a reproducible arbitrary draw.
    --sample first  accession order, which is what you get if you do nothing
                    yourself. Available so the comparison can be made, not
                    because it is a good idea.

    Whatever is chosen, the full candidate list and the reason each genome was
    kept or dropped are written out, so the panel is auditable rather than
    asserted.

OUTPUT
    genomes/                 the assemblies, one FASTA each
    genome_metadata_v01.tsv  one row per candidate: accession, organism, strain,
                             level, submitter, year, country, kept
    fetch_report_v01.tsv
"""
import argparse, csv, collections, glob, json, os, random, shutil, subprocess, sys, zipfile
import pandas as pd

AP = argparse.ArgumentParser()
g = AP.add_mutually_exclusive_group(required=True)
g.add_argument("--species", help='e.g. "Streptococcus uberis"')
g.add_argument("--taxid", help="NCBI taxonomy id")
AP.add_argument("--strains", type=int, default=None,
                help="how many genomes to keep. All of them if omitted.")
AP.add_argument("--sample", default="even", choices=["even", "random", "first"])
AP.add_argument("--seed", type=int, default=0)
AP.add_argument("--assembly-level", default=None,
                help="complete, chromosome, scaffold or contig. Any level if omitted.")
AP.add_argument("--reference-only", action="store_true",
                help="restrict to RefSeq reference and representative genomes")
AP.add_argument("--out-dir", default="fetch")
AP.add_argument("--keep-zip", action="store_true")
opt = AP.parse_args()
os.makedirs(opt.out_dir, exist_ok=True)
REPORT = []


def note(step, status, detail):
    REPORT.append(dict(step=step, status=status, detail=detail))
    print(f"  [{status:<7}] {step:<20} {detail}")


if shutil.which("datasets") is None:
    sys.exit("fetch: the NCBI 'datasets' CLI is not installed. It is in "
             "environment.yml as ncbi-datasets-cli.")

taxon = opt.species or opt.taxid
note("taxon", "OK", str(taxon))

# ------------------------------------------------------------------ metadata
meta_cmd = ["datasets", "summary", "genome", "taxon", str(taxon), "--as-json-lines"]
if opt.assembly_level:
    meta_cmd += ["--assembly-level", opt.assembly_level]
if opt.reference_only:
    meta_cmd += ["--reference"]
r = subprocess.run(meta_cmd, capture_output=True, text=True)
if r.returncode != 0:
    sys.exit(f"fetch: datasets summary failed:\n{(r.stderr or '').strip()[-600:]}")
rows = []
for line in r.stdout.splitlines():
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    ai = d.get("assembly_info", {}) or {}
    ba = ai.get("biosample", {}) or {}
    attrs = {a.get("name"): a.get("value") for a in ba.get("attributes", []) or []}
    rows.append(dict(
        accession=d.get("accession", ""),
        organism=(d.get("organism", {}) or {}).get("organism_name", ""),
        strain=(ai.get("biosample", {}) or {}).get("description", {}).get("title", "")
        or attrs.get("strain", ""),
        assembly_level=ai.get("assembly_level", ""),
        submitter=ai.get("submitter", "") or ba.get("submission_date", ""),
        year=str(attrs.get("collection_date", ""))[:4],
        country=attrs.get("geo_loc_name", "") or attrs.get("country", ""),
        refseq_category=ai.get("refseq_category", "")))
cand = pd.DataFrame(rows).drop_duplicates("accession")
if cand.empty:
    sys.exit(f"fetch: no genomes found for {taxon}")
note("candidates", "OK", f"{len(cand):,} genomes; levels "
                         f"{dict(collections.Counter(cand.assembly_level))}")

# ------------------------------------------------------------------ sampling
n = opt.strains or len(cand)
if n >= len(cand):
    keep = cand.copy()
    note("sampling", "SKIP", f"{n} requested, {len(cand)} available: taking all")
elif opt.sample == "first":
    keep = cand.head(n).copy()
    note("sampling", "OK", f"first {n} by accession order")
elif opt.sample == "random":
    keep = cand.sample(n=n, random_state=opt.seed).copy()
    note("sampling", "OK", f"{n} at random, seed {opt.seed}")
else:
    # round-robin over the strata that exist, so no submitter, year or country
    # dominates the draw
    strata = [c for c in ("submitter", "year", "country") if cand[c].astype(str).str.strip().any()]
    key = (cand[strata].astype(str).agg("|".join, axis=1) if strata
           else pd.Series(["all"] * len(cand), index=cand.index))
    buckets = collections.OrderedDict()
    rng = random.Random(opt.seed)
    for k, idx in cand.groupby(key).groups.items():
        idx = list(idx)
        rng.shuffle(idx)
        buckets[k] = idx
    picked = []
    while len(picked) < n and any(buckets.values()):
        for k in list(buckets):
            if buckets[k] and len(picked) < n:
                picked.append(buckets[k].pop())
    keep = cand.loc[picked].copy()
    note("sampling", "OK", f"{len(keep)} spread evenly over {len(buckets)} strata "
                           f"({', '.join(strata) or 'none available'})")

cand["kept"] = cand["accession"].isin(set(keep["accession"])).map({True: "yes", False: "no"})
cand.to_csv(os.path.join(opt.out_dir, "genome_metadata_v01.tsv"), sep="\t", index=False)

# ------------------------------------------------------------------ download
acc_file = os.path.join(opt.out_dir, "accessions.txt")
open(acc_file, "w").write("\n".join(keep["accession"]) + "\n")
zip_path = os.path.join(opt.out_dir, "ncbi_dataset.zip")
r = subprocess.run(["datasets", "download", "genome", "accession",
                    "--inputfile", acc_file, "--include", "genome",
                    "--filename", zip_path], capture_output=True, text=True)
if r.returncode != 0:
    sys.exit(f"fetch: datasets download failed:\n{(r.stderr or '').strip()[-600:]}")

gdir = os.path.join(opt.out_dir, "genomes")
os.makedirs(gdir, exist_ok=True)
n_out = 0
with zipfile.ZipFile(zip_path) as z:
    for member in z.namelist():
        if not member.endswith((".fna", ".fa", ".fasta")):
            continue
        acc = next((a for a in keep["accession"] if a in member), None)
        if acc is None:
            continue
        with z.open(member) as src, open(os.path.join(gdir, f"{acc}.fna"), "wb") as dst:
            shutil.copyfileobj(src, dst)
        n_out += 1
if not opt.keep_zip:
    os.remove(zip_path)
note("download", "OK" if n_out == len(keep) else "PARTIAL",
     f"{n_out} of {len(keep)} assemblies written to {gdir}/")

pd.DataFrame(REPORT).to_csv(os.path.join(opt.out_dir, "fetch_report_v01.tsv"),
                            sep="\t", index=False)
if n_out == 0:
    sys.exit("fetch: no assemblies were written; nothing downstream can run.")
print(f"\nnext: annotate with Prokka, run Panaroo, then point run.py at the Panaroo output")
