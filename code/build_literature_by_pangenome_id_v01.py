#!/usr/bin/env python3
"""
build_literature_by_pangenome_id_v01.py

MAP_A6035_LITERATURE_TO_PANGENOME. One row per pangenome_id carrying the
PubMed-indexed literature evidence of its SIKU01 PGAP representative.

Fills SOCKET_LITERATURE, which FRAME_SINIAE_PRIORITISATION declares
UNFILLED_AT_REQUIRED_GRAIN: the source exists at locus_tag and no transfer node
did. The transfer follows the pattern of the four sibling MAPs exactly, so the
five external layers share one missingness grammar.

ABSENCE IS NOT A MEASURED ZERO HERE
    The deposited assignment table lists only proteins that carry at least one
    identifier. A representative absent from it was never the subject of a
    retrieval whose negative result was recorded: S04 carries a hard-coded
    vector of literals and performs no search, so "no row" means "not on the
    curated list", not "searched and found nothing". rep_pmid_count is therefore
    0 for a screened representative only in the sense of the curated list, and
    that reading is stated in the column definition rather than implied by the
    number.

ONE-TO-ONE ONLY
    Values transfer only where exactly one SIKU01 protein maps to the family.
    The families with two are classified non_1to1_mapping and left unvalued;
    they stay in the ranking universe as not-evaluable.

TWO A6035 OUTPUTS, ONE PER VARIABLE
    The identifier count comes from the assignment table and the curated vaccine
    reference from the cross-reference table, because neither is complete for
    the other's variable. The assignment table lists the 69 proteins carrying at
    least one identifier and labels 10 of them; the cross-reference table labels
    15, the five extra being antigens with a curated label and no indexed
    identifier. Taking the label from the assignment table alone would drop
    those five, which is why FRAME_SINIAE_PRIORITISATION records 15 and not 10.

INPUTS
    ST_A6035_02_protein_literature_assignments_v01.tsv   69 proteins, identifiers
    ST_A6035_03_vaccine_antigen_crossref_v01.tsv         15 proteins, curated label
    MAP_A5093_locus_pangenome_v02.tsv                    locus_tag <-> pangenome_id

OUTPUT
    literature_by_pangenome_id_v01.tsv
    Key columns for registration: pangenome_id and representative_locus_tag.
"""
import argparse
import os

import pandas as pd

# ----------------------------------------------------------------------------
# %% SETUP
# ----------------------------------------------------------------------------
ROOT = os.environ.get("ANL_ROOT", ".")
REPRESENTATIVE_SAMPLE_ID = "SIKU01"
RI = os.path.join(ROOT, "08_source_data", "routed_input")

ap = argparse.ArgumentParser()
ap.add_argument("--assignments", default=os.path.join(
    RI, "ST_A6035_02_protein_literature_assignments_v01.tsv"))
ap.add_argument("--crossref", default=os.path.join(
    RI, "ST_A6035_03_vaccine_antigen_crossref_v01.tsv"))
ap.add_argument("--map", default=os.path.join(RI, "MAP_A5093_locus_pangenome_v02.tsv"))
ap.add_argument("--out", default=os.path.join(
    ROOT, "04_tables", "literature_by_pangenome_id_v01.tsv"))
a = ap.parse_args()

# ----------------------------------------------------------------------------
# %% DATA
# ----------------------------------------------------------------------------
lit = pd.read_csv(a.assignments, sep="\t", dtype=str).fillna("")
lit.columns = [c.strip() for c in lit.columns]
lit = lit.rename(columns={"Locus tag": "locus_tag", "PGAP product": "pgap_product",
                          "Gene": "gene", "Vaccine reference": "vaccine_reference",
                          "PMIDs (n)": "pmid_n", "PMIDs": "pmids"})
lit = lit[lit["locus_tag"].str.startswith("SIKU01")]

xref = pd.read_csv(a.crossref, sep="\t", dtype=str).fillna("")
xref.columns = [c.strip() for c in xref.columns]
xref = xref.rename(columns={"Locus tag": "locus_tag",
                            "Vaccine reference label": "vaccine_reference",
                            "PGAP product": "pgap_product"})
xref = xref[xref["locus_tag"].str.startswith("SIKU01")]

mp = pd.read_csv(a.map, sep="\t", dtype=str).fillna("")
link = mp[(mp["locus_tag"] != "") & (mp["in_proteome"] == "yes")
          & (mp["pangenome_id"] != "")][["locus_tag", "pangenome_id"]].drop_duplicates()
n_loci = link.groupby("pangenome_id")["locus_tag"].nunique()

# an em dash in the deposited table is the absent marker, not a value
DASH = {"—", "-", "--", ""}
lit["pmid_list"] = lit["pmids"].apply(
    lambda s: [p.strip() for p in s.split(";") if p.strip() and p.strip() not in DASH])
xref["vaccine_reference"] = xref["vaccine_reference"].apply(
    lambda s: "" if s.strip() in DASH else s.strip())

# ----------------------------------------------------------------------------
# %% REPRESENTATIVE-LEVEL EVIDENCE
# ----------------------------------------------------------------------------
prot = lit.set_index("locus_tag")
label = dict(zip(xref["locus_tag"], xref["vaccine_reference"]))
product = dict(zip(xref["locus_tag"], xref["pgap_product"]))
product.update({lt: r["pgap_product"] for lt, r in prot.iterrows() if r["pgap_product"]})

rec = {}
for lt in sorted(set(prot.index) | set(label)):
    pl = prot.loc[lt, "pmid_list"] if lt in prot.index else []
    rec[lt] = dict(rep_pmid_count=len(pl), rep_pmids="; ".join(pl),
                   rep_vaccine_reference=label.get(lt, ""),
                   rep_pgap_product=product.get(lt, ""))

# ----------------------------------------------------------------------------
# %% AGGREGATE TO pangenome_id
# ----------------------------------------------------------------------------
one = link[link["pangenome_id"].map(n_loci) == 1].set_index("pangenome_id")
t = pd.DataFrame(index=one.index)
t["representative_locus_tag"] = one["locus_tag"]
t["n_siku01_loci"] = 1
t["rep_status"] = "screened"

j = one["locus_tag"].map(rec)
t["rep_pmid_count"] = [d["rep_pmid_count"] if isinstance(d, dict) else 0 for d in j]
t["rep_pmids"] = [d["rep_pmids"] if isinstance(d, dict) else "" for d in j]
t["rep_vaccine_reference"] = [d["rep_vaccine_reference"] if isinstance(d, dict) else "" for d in j]
t["rep_pgap_product"] = [d["rep_pgap_product"] if isinstance(d, dict) else "" for d in j]
t["rep_literature_present"] = (t["rep_pmid_count"] > 0).map({True: "yes", False: "no"})
t["rep_vaccine_reference_present"] = (t["rep_vaccine_reference"] != "").map(
    {True: "yes", False: "no"})

multi = n_loci[n_loci > 1].index
if len(multi):
    nz = pd.DataFrame(index=pd.Index(multi, name="pangenome_id"))
    nz["representative_locus_tag"] = ""
    nz["n_siku01_loci"] = n_loci.reindex(multi).astype(int)
    nz["rep_status"] = "non_1to1_mapping"
    t = pd.concat([t, nz])

t = t.reset_index().rename(columns={"index": "pangenome_id"})
t = t[["pangenome_id", "representative_locus_tag", "n_siku01_loci", "rep_status",
       "rep_literature_present", "rep_pmid_count", "rep_pmids",
       "rep_vaccine_reference_present", "rep_vaccine_reference", "rep_pgap_product"]]
t["rep_pmid_count"] = t["rep_pmid_count"].astype("Int64").astype("string").fillna("")
t = t.fillna("")
t["_k"] = pd.to_numeric(t["pangenome_id"], errors="coerce")
t = t.sort_values("_k").drop(columns="_k")

# ----------------------------------------------------------------------------
# %% CHECKS
# ----------------------------------------------------------------------------
assert t["pangenome_id"].is_unique, "pangenome_id is not unique"
carried = set(one["locus_tag"]) & set(lit["locus_tag"])
declared = t.loc[t["rep_status"] == "screened", "rep_pmid_count"].replace("", "0").astype(int).sum()
expected = sum(len(prot.loc[lt, "pmid_list"]) for lt in carried)
assert declared == expected, f"identifiers lost or duplicated in the transfer: {declared} vs {expected}"

os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
t.to_csv(a.out, sep="\t", index=False)

# ----------------------------------------------------------------------------
# %% FREEZE REPORT
# ----------------------------------------------------------------------------
print(f"representative_sample_id:           {REPRESENTATIVE_SAMPLE_ID}")
print()
print(f"Proteins carrying an identifier:    {len(lit):,}")
print(f"Proteins carrying a curated label:  {len(xref):,}")
print(f"Mapped to pangenome_id:             {len(link):,}")
print(f"Resolved uniquely:                  {(n_loci == 1).sum():,}")
print(f"Non-1:1 (>1 SIKU01 locus):          {(n_loci > 1).sum():,}")
print()
print(f"Rows written:                       {len(t):,}")
for k in ["screened", "non_1to1_mapping"]:
    print(f"  {k:33s} {(t['rep_status'] == k).sum():,}")
print()
print(f"families with >=1 identifier        {(t['rep_literature_present'] == 'yes').sum():,}")
print(f"families with a vaccine reference   {(t['rep_vaccine_reference_present'] == 'yes').sum():,}")
print(f"identifiers carried                 {declared:,}")
lost = sorted((set(lit["locus_tag"]) | set(label)) - set(one["locus_tag"]))
if lost:
    print(f"\nproteins on the list whose family is not 1:1, withheld: {'; '.join(lost)}")
print(f"\nwritten: {a.out}  ({len(t):,} rows x {t.shape[1]} columns)")
