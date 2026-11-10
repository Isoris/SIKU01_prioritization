#!/usr/bin/env python3
"""
code_A6434_inputs_v01.py — assemble the ranking input frame at [pangenome_id].

Extends code_ranking_inputs_v01.py, which is carried in 08_source_data/raw_data
as prior art, with the four things the ranking needs and that script did not
attach: the literature layer, the M0 gene-model table, the alignment-coverage
table, and the full-length ratio.

SPINE
    [pangenome_id], the core eligibility set, minus the eleven families in which
    the SIKU01 Panaroo member is one of two adjacent calls of a single gene. The
    exclusion is written to its own table and is not silent.

WHAT AN ABSENT VALUE MEANS, PER LAYER
    Six layers, three missingness grammars, and a single fillna(0) is correct for
    none of them. Every layer's rep_status travels through the join and each gate
    reports pass / fail / not evaluable rather than resolving a missing value to
    a comparison outcome.

      epitope      screened / non_1to1        searched-and-negative is a real 0
      host         annotated / non_1to1       empty identity means no alignment
      surface      annotated / no_interproscan / non_1to1
                                              empty count means no record, not 0
      literature   screened / non_1to1        empty means not on the curated
                                              list; no retrieval was run, so it
                                              is not a searched negative
      conservation no status column           absent means outside the core set
      coverage_qc  no status column           absent means no alignment

FULL-LENGTH RATIO, AND WHY IT IS NOT form_monomorphic
    m0_gate_by_pangenome_id carries form_monomorphic, which asks whether every
    member of the orthogroup agrees on annotated length. That is a property of
    the panel and it fails 328 of 1,538 families. The M0 criterion the framework
    declares is a property of SIKU01: whether its own annotated length equals the
    panel majority length. A family where SIKU01 matches the majority and one
    other isolate differs satisfies the declared criterion and fails
    form_monomorphic. The ratio is computed here and form_monomorphic is carried
    as descriptive.

    The denominator is the panel majority length, never the anchor length: the
    anchor is selected as the longest member and is the reference isolate in most
    families, so an anchor denominator would make the ratio 1.00 by construction.

GATE VALUES COME FROM THE REFERENCE COPY
    RSLV_A6318_DESCRIPTOR_GRAIN_AT_RANKING. Every M1 and M2 criterion is a
    property of a construct that gets expressed, and one sequence gets expressed,
    not a family median. The family summary is attached beside it as population
    context and is never gated on.

Paths resolve from the capsule root via ANL_ROOT.
"""
import argparse
import os
import sys

import pandas as pd

# ----------------------------------------------------------------------------
# %% SETUP
# ----------------------------------------------------------------------------
ROOT = os.environ.get("ANL_ROOT", ".")
RI = os.path.join(ROOT, "08_source_data", "routed_input")
REFERENCE_SAMPLE_ID = "SIKU01"

# The eleven core families in which the SIKU01 Panaroo member is one of two
# adjacent calls of one gene. Verified against MAP_A5093_locus_pangenome_v02:
# these are exactly the core families carrying more than one SIKU01 Prokka call.
SPLIT_CALL_FAMILIES = ["6490", "6605", "6607", "6633", "6675", "6708",
                       "6853", "6967", "7133", "7232", "7264"]

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

# Each transfer table names the successful state in the verb of its own method:
# the host and InterProScan layers annotated, the IEDB and literature layers
# screened, the local non-specific layer swept. All four mean the same thing —
# this representative was measured and the result stands — and the vocabulary
# difference is a naming inconsistency across the sibling MAPs, not a difference
# in what was done. Recorded here rather than renamed in four upstream capsules.
EVALUABLE = {"annotated", "screened", "swept"}
SPINE_OWNED = ["pangenome_class", "carriage_n", "gene_name", "n_copies", "n_samples",
               "n_paralogous_samples"]
GATE_VARS = ["protein_length_aa", "mw_da", "pI", "gravy", "charge_pH_7_0",
             "instability_index", "cds_length_nt", "gc3", "cai_ec", "cai_on", "cai_dr",
             "n_typeIIS_total"]


def read(path):
    d = pd.read_csv(path, sep="\t", dtype=str, low_memory=False).fillna("")
    d.columns = [c.strip() for c in d.columns]
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=RI)
    ap.add_argument("--literature", default=os.path.join(ROOT, "04_tables",
                                                        "literature_by_pangenome_id_v01.tsv"))
    ap.add_argument("--gene-copies", default=os.path.join(
        RI, "descriptors_by_pangenome_id_v01.tsv.gz"))
    ap.add_argument("--out", default=os.path.join(ROOT, "01_analysis_output", "derived",
                                                  "ranking_inputs_by_pangenome_id_v01.tsv"))
    ap.add_argument("--audit", default=os.path.join(ROOT, "04_tables",
                                                    "tbl_A6434_01_input_audit_v01.tsv"))
    ap.add_argument("--exclusions", default=os.path.join(ROOT, "04_tables",
                                                         "tbl_A6434_02_spine_exclusions_v01.tsv"))
    a = ap.parse_args()

    # ------------------------------------------------------------------------
    # %% LOAD
    # ------------------------------------------------------------------------
    tables = {}
    for name, spec in LAYERS.items():
        p = a.literature if name == "literature" else os.path.join(a.data_dir, spec["path"])
        if not os.path.exists(p):
            sys.exit(f"missing declared input for layer {name!r}: {p}\n"
                     f"  produced by: {spec['produced_by']}\n"
                     f"  no table from another capsule is substituted for it.")
        tables[name] = read(p)

    # ------------------------------------------------------------------------
    # %% SPINE
    # The eligibility set, not the families that happen to carry a
    # representative. A family with no representative is a candidate with
    # missing annotation, never a non-candidate.
    # ------------------------------------------------------------------------
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
    assert spine["pangenome_id"].is_unique, "spine grain [pangenome_id] is not unique"

    # ------------------------------------------------------------------------
    # %% ATTACH
    # LEFT JOIN each layer, prefix its columns, carry its rep_status. Nothing is
    # filled; a missing value stays missing and is explained by the evaluability
    # flag rather than by a number that looks like a measurement.
    # ------------------------------------------------------------------------
    out = spine.copy()
    audit = []
    for name, spec in LAYERS.items():
        t = tables[name].drop(columns=SPINE_OWNED, errors="ignore").copy()
        assert t["pangenome_id"].is_unique, f"layer {name} is not unique on pangenome_id"
        cols = [c for c in t.columns if c != "pangenome_id"]
        t = t.rename(columns={c: f"{name}__{c}" for c in cols})

        before = len(out)
        out = out.merge(t, on="pangenome_id", how="left")
        assert len(out) == before, f"layer {name} multiplied spine rows: {before} -> {len(out)}"
        newcols = [f"{name}__{c}" for c in cols]
        # normalising NaN to "" keeps missing and empty one token so the
        # evaluability test reads one thing. No numeric column gains a value.
        out[newcols] = out[newcols].fillna("")

        status_col = f"{name}__{spec['status_col']}" if spec["status_col"] else None
        joined = int(out[f"{name}__{cols[0]}"].ne("").sum())
        ev = out[status_col].isin(EVALUABLE) if status_col else out[f"{name}__{cols[0]}"].ne("")
        out[f"{name}__evaluable"] = ev.map({True: "yes", False: "no"})
        audit.append(dict(layer=name, source=spec["path"], produced_by=spec["produced_by"],
                          spine_rows=len(out), rows_joined=joined,
                          rows_evaluable=int(ev.sum()), rows_not_evaluable=int((~ev).sum()),
                          absent_means=spec["absent_means"], fill_applied="none"))

    # ------------------------------------------------------------------------
    # %% REFERENCE COPY
    # ------------------------------------------------------------------------
    gc = pd.read_csv(a.gene_copies, sep="\t", dtype={"pangenome_id": str, "sample_id": str},
                     low_memory=False)
    gc["pangenome_id"] = gc["pangenome_id"].astype(str)
    rep = (gc[gc["sample_id"] == REFERENCE_SAMPLE_ID]
           .drop_duplicates("pangenome_id").set_index("pangenome_id"))
    have = [v for v in GATE_VARS if v in rep.columns]
    out = out.merge(rep[have].rename(columns={v: "rep__" + v for v in have}),
                    left_on="pangenome_id", right_index=True, how="left")
    out["reference_copy_present"] = out["rep__protein_length_aa"].notna().map(
        {True: "yes", False: "no"})

    # whether any copy of the family leaves the M2 base envelope while the
    # reference copy sits inside it: the one quantity the population buys that
    # the reference copy cannot, and it is free
    num = gc.copy()
    for v in ("mw_da", "gravy", "pI"):
        num[v] = pd.to_numeric(num[v], errors="coerce")
    outside = ((num.mw_da < 20000) | (num.mw_da > 100000) | (num.gravy < -1.5)
               | (num.gravy > 1.5) | (num.pI < 2) | (num.pI > 12))
    spread = num.assign(_o=outside).groupby("pangenome_id")["_o"].agg(["sum", "size"])
    out = out.merge(spread.rename(columns={"sum": "n_copies_outside_envelope",
                                           "size": "n_copies_scored"}),
                    left_on="pangenome_id", right_index=True, how="left")
    out["envelope_spread_flag"] = (
        (pd.to_numeric(out.n_copies_outside_envelope, errors="coerce") > 0)
        .map({True: "some_copies_outside", False: "all_copies_inside"}))

    # ------------------------------------------------------------------------
    # %% FULL-LENGTH RATIO
    # The reference copy's annotated length over the panel majority annotated
    # length for its orthogroup. Denominator from m0_gate, which computes the
    # majority over the annotated members.
    # ------------------------------------------------------------------------
    rep_len = pd.to_numeric(out["rep__protein_length_aa"], errors="coerce")
    maj_len = pd.to_numeric(out["m0__majority_len_aa"], errors="coerce")
    out["full_length_ratio"] = (rep_len / maj_len).round(6)
    out["full_length_evaluable"] = (rep_len.notna() & maj_len.notna() & (maj_len > 0)).map(
        {True: "yes", False: "no"})

    # ------------------------------------------------------------------------
    # %% WRITE
    # ------------------------------------------------------------------------
    for p in (a.out, a.audit, a.exclusions):
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    out["_k"] = pd.to_numeric(out["pangenome_id"], errors="coerce")
    out = out.sort_values("_k").drop(columns="_k")
    out.to_csv(a.out, sep="\t", index=False)
    pd.DataFrame(audit).to_csv(a.audit, sep="\t", index=False)
    pd.DataFrame(excl).to_csv(a.exclusions, sep="\t", index=False)

    # ------------------------------------------------------------------------
    # %% REPORT
    # ------------------------------------------------------------------------
    print(f"universe                    : {len(universe):,} families")
    print(f"core eligibility set        : {len(core):,}")
    print(f"split gene calls excluded   : {len(SPLIT_CALL_FAMILIES)}")
    print(f"spine                       : {len(out):,}   grain [pangenome_id], unique "
          f"{out['pangenome_id'].is_unique}")
    print()
    for r in audit:
        print(f"  {r['layer']:22s} joined {r['rows_joined']:>5,}   evaluable "
              f"{r['rows_evaluable']:>5,}   not evaluable {r['rows_not_evaluable']:>5,}")
    print()
    print(f"  reference copy present    : {(out.reference_copy_present == 'yes').sum():,}"
          f" of {len(out):,}")
    fl = pd.to_numeric(out["full_length_ratio"], errors="coerce")
    print(f"  full-length ratio 1.00    : {(fl == 1.0).sum():,} of {fl.notna().sum():,} evaluable")
    print(f"  envelope spread flagged   : {(out.envelope_spread_flag == 'some_copies_outside').sum():,}")
    print()
    print(f"written: {a.out}")
    print(f"audit  : {a.audit}")
    print(f"excl   : {a.exclusions}")


if __name__ == "__main__":
    main()
