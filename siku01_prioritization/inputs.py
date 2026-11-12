"""From the frozen input tables to one row per orthogroup, and then to one row per orthogroup and route.

Four steps:

    check_inputs()             every file of inputs/ has the checksum recorded in inputs/CHECKSUMS.tsv
    build_literature()         literature evidence per orthogroup (from the two curated literature tables and the locus map)
    assemble_ranking_inputs()  join ten layers on pangenome_id: 1,527 orthogroups x 429 columns
    build_frame()              repeat each orthogroup on each of the six routes: 9,162 candidate rows

`pangenome_id` is the orthogroup identifier (one gene family of the 90-isolate pangenome).

What an absent value means differs by layer, so nothing is filled in. A missing value stays missing, the `<layer>__evaluable` column
says whether the layer measured that orthogroup, and a rule that meets a missing value reports "not evaluable" (see rules.py).

      layer         status column              what an empty value means
      epitope       screened / non_1to1        a present row with 0 is a measured zero
      host          annotated / non_1to1       empty identity means no alignment, never 0
      surface       annotated / no_interproscan / non_1to1     empty count means no InterProScan record, not 0
      literature    screened / non_1to1        empty means absent from the curated list (no search was run)
      conservation  (none)                     absent means outside the core set
      coverage      (none)                     absent means no alignment
"""
import warnings

import pandas as pd

from . import layout
from .tables import read_tsv, sha256_file

REFERENCE_SAMPLE_ID = "SIKU01"

# The eleven core orthogroups in which the SIKU01 member is one of two adjacent calls of a single gene (a split gene call).
# Every alignment-derived measurement for them describes a fragment, so they are excluded, and the exclusion is written to its own
# table. tests/test_inputs.py checks this list against the locus map.
SPLIT_CALL_FAMILIES = ["6490", "6605", "6607", "6633", "6675", "6708", "6853", "6967", "7133", "7232", "7264"]

# The ten layers joined on pangenome_id, in join order. status_col: the column that says whether the representative was measured.
LAYERS = {
    "conservation": dict(
        path="conservation_by_pangenome_id_v01.tsv", status_col=None,
        absent_means="family not in the retained core set; no conservation measured",
        produced_by="Panaroo to conservation > Bio3D conservation"),
    "coverage": dict(
        path="coverage_qc_by_pangenome_id_v01.tsv", status_col=None,
        absent_means="family has no alignment; no occupancy or shared region measured",
        produced_by="Panaroo to conservation > population occupancy"),
    "m0": dict(
        path="m0_gate_by_pangenome_id_v01.tsv", status_col=None,
        absent_means="family outside the core set; no gene-model summary",
        produced_by="Panaroo to conservation > population occupancy"),
    "descriptors_protein": dict(
        path="protein_descriptors_by_pangenome_id_v01.tsv", status_col=None,
        absent_means="family carries no scored protein copy",
        produced_by="Sequence-derived descriptors > orthogroup-level descriptor tables"),
    "descriptors_nucleotide": dict(
        path="nucleotide_descriptors_by_pangenome_id_v01.tsv", status_col=None,
        absent_means="family carries no scored coding sequence",
        produced_by="Sequence-derived descriptors > orthogroup-level descriptor tables"),
    "epitope": dict(
        path="epitope_by_pangenome_id_v01.tsv", status_col="rep_status",
        absent_means="no unambiguous representative; a present row with 0 is a measured zero",
        produced_by="IEDB peptide homology > orthogroup transfer"),
    "host": dict(
        path="host_similarity_by_pangenome_id_v01.tsv", status_col="rep_status",
        absent_means="no unambiguous representative; an empty identity means no alignment, never 0",
        produced_by="Host similarity screen > orthogroup transfer"),
    "surface": dict(
        path="interpro_by_pangenome_id_v02.tsv", status_col="rep_status",
        absent_means="no unambiguous representative; an empty count means no InterProScan record",
        produced_by="Localisation and topology > orthogroup transfer"),
    "literature": dict(
        path="literature_by_pangenome_id_v01.tsv", status_col="rep_status",
        absent_means="no unambiguous representative; an empty count means absent from the curated list",
        produced_by="Literature evidence > orthogroup transfer"),
    "nonspecific": dict(
        path="nonspecific_by_pangenome_id_v01.tsv", status_col="rep_status",
        absent_means="no unambiguous representative; an empty count means no local match measured",
        produced_by="Local non-specific similarity > orthogroup transfer"),
}
GENE_COPIES = "descriptors_by_pangenome_id_v01.tsv.gz"

# The upstream tables name "this representative was measured" with three different words; all three mean the same thing.
EVALUABLE = {"annotated", "screened", "swept"}
SPINE_OWNED = ["pangenome_class", "carriage_n", "gene_name", "n_copies", "n_samples", "n_paralogous_samples"]
# Rule values are those of the SIKU01 copy of the gene (the sequence that would be expressed), not a family median.
GATE_VARS = ["protein_length_aa", "mw_da", "pI", "gravy", "charge_pH_7_0", "instability_index", "cds_length_nt", "gc3",
             "cai_ec", "cai_on", "cai_dr", "n_typeIIS_total"]


# ------------------------------------------------------------------------------------------------ 1. check the inputs
def check_inputs(inputs_dir=layout.INPUTS):
    """Compare every input file with inputs/CHECKSUMS.tsv. Returns (rows, problems); problems is empty when all is well."""
    rows, problems = [], []
    listed = read_tsv(inputs_dir / "CHECKSUMS.tsv")
    for r in listed:
        p = inputs_dir / r["file"]
        if not p.is_file():
            status = "MISSING"
        elif sha256_file(p) != r["sha256"]:
            status = "CHANGED"
        else:
            status = "OK"
        rows.append(dict(r, status=status))
        if status != "OK":
            problems.append(f"{status}: inputs/{r['file']}")
    known = {r["file"] for r in listed} | {"CHECKSUMS.tsv", "README.md"}
    for p in sorted(inputs_dir.iterdir()):
        if p.is_file() and p.name not in known:
            problems.append(f"UNLISTED: inputs/{p.name} is not in CHECKSUMS.tsv")
    return rows, problems


# ------------------------------------------------------------------------------------------------ 2. literature layer
def build_literature(out_path, inputs_dir=layout.INPUTS):
    """One row per pangenome_id with the PubMed-indexed literature evidence of its SIKU01 protein.

    Values are transferred only where exactly one SIKU01 protein maps to the orthogroup; orthogroups with two are labelled
    non_1to1_mapping and left without values (they stay candidates, not evaluable for this layer).

    Absence is not a measured zero here: the curated tables list only proteins that carry a reference, and no literature search was
    run for the others. rep_pmid_count = 0 therefore means "not on the curated list".

    Two curated tables, one per variable: the identifier count comes from the assignment table (69 proteins), the curated vaccine
    reference from the cross-reference table (15 proteins, five of which have a label but no indexed identifier).
    """
    lit = pd.read_csv(inputs_dir / "ST_A6035_02_protein_literature_assignments_v01.tsv", sep="\t", dtype=str).fillna("")
    lit.columns = [c.strip() for c in lit.columns]
    lit = lit.rename(columns={"Locus tag": "locus_tag", "PGAP product": "pgap_product", "Gene": "gene",
                              "Vaccine reference": "vaccine_reference", "PMIDs (n)": "pmid_n", "PMIDs": "pmids"})
    lit = lit[lit["locus_tag"].str.startswith("SIKU01")]

    xref = pd.read_csv(inputs_dir / "ST_A6035_03_vaccine_antigen_crossref_v01.tsv", sep="\t", dtype=str).fillna("")
    xref.columns = [c.strip() for c in xref.columns]
    xref = xref.rename(columns={"Locus tag": "locus_tag", "Vaccine reference label": "vaccine_reference",
                                "PGAP product": "pgap_product"})
    xref = xref[xref["locus_tag"].str.startswith("SIKU01")]

    mp = pd.read_csv(inputs_dir / "MAP_A5093_locus_pangenome_v02.tsv", sep="\t", dtype=str).fillna("")
    link = mp[(mp["locus_tag"] != "") & (mp["in_proteome"] == "yes")
              & (mp["pangenome_id"] != "")][["locus_tag", "pangenome_id"]].drop_duplicates()
    n_loci = link.groupby("pangenome_id")["locus_tag"].nunique()

    dash = {"—", "-", "--", ""}   # an em dash in the curated tables marks "absent", it is not a value
    lit["pmid_list"] = lit["pmids"].apply(
        lambda s: [p.strip() for p in s.split(";") if p.strip() and p.strip() not in dash])
    xref["vaccine_reference"] = xref["vaccine_reference"].apply(lambda s: "" if s.strip() in dash else s.strip())

    # evidence per SIKU01 protein
    prot = lit.set_index("locus_tag")
    label = dict(zip(xref["locus_tag"], xref["vaccine_reference"]))
    product = dict(zip(xref["locus_tag"], xref["pgap_product"]))
    product.update({lt: r["pgap_product"] for lt, r in prot.iterrows() if r["pgap_product"]})
    rec = {}
    for lt in sorted(set(prot.index) | set(label)):
        pl = prot.loc[lt, "pmid_list"] if lt in prot.index else []
        rec[lt] = dict(rep_pmid_count=len(pl), rep_pmids="; ".join(pl),
                       rep_vaccine_reference=label.get(lt, ""), rep_pgap_product=product.get(lt, ""))

    # transfer to pangenome_id, one-to-one only
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
    t["rep_vaccine_reference_present"] = (t["rep_vaccine_reference"] != "").map({True: "yes", False: "no"})

    multi = n_loci[n_loci > 1].index
    if len(multi):
        nz = pd.DataFrame(index=pd.Index(multi, name="pangenome_id"))
        nz["representative_locus_tag"] = ""
        nz["n_siku01_loci"] = n_loci.reindex(multi).astype(int)
        nz["rep_status"] = "non_1to1_mapping"
        t = pd.concat([t, nz])

    t = t.reset_index().rename(columns={"index": "pangenome_id"})
    t = t[["pangenome_id", "representative_locus_tag", "n_siku01_loci", "rep_status", "rep_literature_present",
           "rep_pmid_count", "rep_pmids", "rep_vaccine_reference_present", "rep_vaccine_reference", "rep_pgap_product"]]
    t["rep_pmid_count"] = t["rep_pmid_count"].astype("Int64").astype("string").fillna("")
    t = t.fillna("")
    t["_k"] = pd.to_numeric(t["pangenome_id"], errors="coerce")
    t = t.sort_values("_k").drop(columns="_k")

    # no identifier may be lost or doubled in the transfer
    assert t["pangenome_id"].is_unique, "pangenome_id is not unique in the literature table"
    carried = set(one["locus_tag"]) & set(lit["locus_tag"])
    declared = t.loc[t["rep_status"] == "screened", "rep_pmid_count"].replace("", "0").astype(int).sum()
    expected = sum(len(prot.loc[lt, "pmid_list"]) for lt in carried)
    assert declared == expected, f"identifiers lost or duplicated in the transfer: {declared} vs {expected}"

    t.to_csv(out_path, sep="\t", index=False, lineterminator="\n")
    withheld = sorted((set(lit["locus_tag"]) | set(label)) - set(one["locus_tag"]))
    return dict(rows=len(t), screened=int((t["rep_status"] == "screened").sum()),
                non_1to1=int((t["rep_status"] == "non_1to1_mapping").sum()),
                with_identifier=int((t["rep_literature_present"] == "yes").sum()),
                with_vaccine_reference=int((t["rep_vaccine_reference_present"] == "yes").sum()),
                identifiers_carried=int(declared), proteins_withheld_not_1to1=withheld)


# ------------------------------------------------------------------------------------------------ 3. one row per orthogroup
def _read(path):
    d = pd.read_csv(path, sep="\t", dtype=str, low_memory=False).fillna("")
    d.columns = [c.strip() for c in d.columns]
    return d


def assemble_ranking_inputs(literature_path, out_path, audit_path, exclusions_path, inputs_dir=layout.INPUTS):
    """Join the ten layers on pangenome_id and attach the SIKU01 copy's own values.

    The rows are the core orthogroups (pangenome_class == core) minus the eleven split gene calls: 1,527 orthogroups. An orthogroup
    without a representative in some layer stays a candidate with a missing value; it is never dropped.

    full_length_ratio = annotated length of the SIKU01 copy / majority annotated length of the orthogroup across the panel.
    (The denominator is the panel majority, not the alignment anchor: the anchor is the longest member and is usually SIKU01
    itself, which would make the ratio 1.00 by construction.)
    """
    tables = {}
    for name, spec in LAYERS.items():
        p = literature_path if name == "literature" else inputs_dir / spec["path"]
        if not p.exists():
            raise FileNotFoundError(f"missing input for layer {name!r}: {p} (produced by: {spec['produced_by']})")
        tables[name] = _read(p)

    # the candidate orthogroups
    prot = tables["descriptors_protein"]
    universe = prot[["pangenome_id"] + SPINE_OWNED].drop_duplicates("pangenome_id")
    core = universe[universe["pangenome_class"] == "core"].copy()
    excl = []
    for fam in SPLIT_CALL_FAMILIES:
        in_core = fam in set(core["pangenome_id"])
        excl.append(dict(
            pangenome_id=fam, on_core_spine="yes" if in_core else "no",
            exclusion="split_gene_call",
            reason="the SIKU01 Panaroo member is one of two adjacent calls of one gene, so every "
                   "alignment-derived measurement for this family describes a fragment",
            detected_in="MAP_A5093_locus_pangenome_v02.tsv, more than one SIKU01 Prokka call",
            why_nothing_downstream_catches_it=
                "n_sequences is 90, keep:longest reduces the split to its longer piece, the anchor "
                "role falls to another isolate's whole gene, and median H.norm is 1.000 because the "
                "90 records agree on every column the fragment reaches",
            produced_by="Panaroo to conservation > pangenome harmonisation"))
    spine = core[~core["pangenome_id"].isin(SPLIT_CALL_FAMILIES)].copy()
    assert spine["pangenome_id"].is_unique, "pangenome_id is not unique among the candidate orthogroups"

    # left-join each layer; prefix its columns with the layer name; fill nothing
    out = spine.copy()
    audit = []
    warnings.simplefilter("ignore", pd.errors.PerformanceWarning)   # 429 columns are added one layer at a time; speed is not an issue
    for name, spec in LAYERS.items():
        t = tables[name].drop(columns=SPINE_OWNED, errors="ignore").copy()
        assert t["pangenome_id"].is_unique, f"layer {name} is not unique on pangenome_id"
        cols = [c for c in t.columns if c != "pangenome_id"]
        t = t.rename(columns={c: f"{name}__{c}" for c in cols})
        before = len(out)
        out = out.merge(t, on="pangenome_id", how="left")
        assert len(out) == before, f"layer {name} multiplied rows: {before} -> {len(out)}"
        newcols = [f"{name}__{c}" for c in cols]
        out[newcols] = out[newcols].fillna("")   # "missing" and "empty" become one token; no numeric cell gains a value
        status_col = f"{name}__{spec['status_col']}" if spec["status_col"] else None
        joined = int(out[f"{name}__{cols[0]}"].ne("").sum())
        ev = out[status_col].isin(EVALUABLE) if status_col else out[f"{name}__{cols[0]}"].ne("")
        out[f"{name}__evaluable"] = ev.map({True: "yes", False: "no"})
        audit.append(dict(layer=name, source=spec["path"], produced_by=spec["produced_by"],
                          spine_rows=len(out), rows_joined=joined,
                          rows_evaluable=int(ev.sum()), rows_not_evaluable=int((~ev).sum()),
                          absent_means=spec["absent_means"], fill_applied="none"))

    # the SIKU01 copy's own values (rep__*): these are what the M2 rules read
    gc = pd.read_csv(inputs_dir / GENE_COPIES, sep="\t", dtype={"pangenome_id": str, "sample_id": str}, low_memory=False)
    gc["pangenome_id"] = gc["pangenome_id"].astype(str)
    rep = gc[gc["sample_id"] == REFERENCE_SAMPLE_ID].drop_duplicates("pangenome_id").set_index("pangenome_id")
    have = [v for v in GATE_VARS if v in rep.columns]
    out = out.merge(rep[have].rename(columns={v: "rep__" + v for v in have}),
                    left_on="pangenome_id", right_index=True, how="left")
    out["reference_copy_present"] = out["rep__protein_length_aa"].notna().map({True: "yes", False: "no"})

    # descriptive only (no rule reads it): does any copy of the family fall outside a wide physicochemical envelope?
    num = gc.copy()
    for v in ("mw_da", "gravy", "pI"):
        num[v] = pd.to_numeric(num[v], errors="coerce")
    outside = ((num.mw_da < 20000) | (num.mw_da > 100000) | (num.gravy < -1.5) | (num.gravy > 1.5) | (num.pI < 2) | (num.pI > 12))
    spread = num.assign(_o=outside).groupby("pangenome_id")["_o"].agg(["sum", "size"])
    out = out.merge(spread.rename(columns={"sum": "n_copies_outside_envelope", "size": "n_copies_scored"}),
                    left_on="pangenome_id", right_index=True, how="left")
    out["envelope_spread_flag"] = ((pd.to_numeric(out.n_copies_outside_envelope, errors="coerce") > 0)
                                   .map({True: "some_copies_outside", False: "all_copies_inside"}))

    # full-length ratio
    rep_len = pd.to_numeric(out["rep__protein_length_aa"], errors="coerce")
    maj_len = pd.to_numeric(out["m0__majority_len_aa"], errors="coerce")
    out["full_length_ratio"] = (rep_len / maj_len).round(6)
    out["full_length_evaluable"] = (rep_len.notna() & maj_len.notna() & (maj_len > 0)).map({True: "yes", False: "no"})

    out["_k"] = pd.to_numeric(out["pangenome_id"], errors="coerce")
    out = out.sort_values("_k").drop(columns="_k")
    out.to_csv(out_path, sep="\t", index=False, lineterminator="\n")
    pd.DataFrame(audit).to_csv(audit_path, sep="\t", index=False, lineterminator="\n")
    pd.DataFrame(excl).to_csv(exclusions_path, sep="\t", index=False, lineterminator="\n")
    return dict(orthogroups_in_pangenome=len(universe), core_orthogroups=len(core),
                split_gene_calls_excluded=len(SPLIT_CALL_FAMILIES), candidate_orthogroups=len(out), columns=out.shape[1],
                reference_copy_present=int((out.reference_copy_present == "yes").sum()), layers=audit)


# ------------------------------------------------------------------------------------------------ 4. one row per orthogroup and route
def build_frame(ranking_inputs_path):
    """The candidate frame: every orthogroup of the assembled table on each of the six routes (1,527 x 6 = 9,162 rows).

    The table is read back from the file as text, so every rule sees exactly the characters that are in the result table.
    """
    rows = read_tsv(ranking_inputs_path)
    return [dict(r, route=route) for route in layout.ROUTES for r in rows]
