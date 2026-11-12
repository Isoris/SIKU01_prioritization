# inputs/ - what each file is

Everything the ranking reads is in this folder. Nothing is downloaded and nothing outside the repo is read.
`pangenome_id` is the orthogroup identifier (one gene family of the 90-isolate pangenome); every table is keyed by it, directly or through a locus tag.
The ranking is fed by the **13 frozen `*_by_pangenome_id` tables** (checksums in `route_manifest.tsv`, checked first by the run), plus the candidate frame and two literature tables.
Row counts are data rows (header not counted).

## The candidate frame

| file | what | rows |
|---|---|---|
| `candidate_data_v02.tsv` | the frozen candidate frame: 1,527 orthogroups x 6 routes (silica, cellulose, AEX, CEX, pDNA tilapia, pDNA zebrafish), 69 columns. The ranking reads it; `postflight/frame_check.py` compares it with what the code rebuilds from the 13 tables (63 of 69 columns shared). It is a deposit and is not rebuilt here | 9,162 |

## The 13 frozen tables (locked in `route_manifest.tsv`)

| file | what | rows |
|---|---|---|
| `conservation_by_pangenome_id_v01.tsv` | amino-acid conservation per orthogroup (normalised Shannon entropy, median and mean, alignment length, sequences, paralog handling) | 1,538 |
| `coverage_qc_by_pangenome_id_v01.tsv` | alignment coverage and occupancy per orthogroup (shared columns, longest shared run, anchor locus) | 1,538 |
| `m0_gate_by_pangenome_id_v01.tsv` | the M0 gate per orthogroup: ORF intact, majority length, single annotated form, topology, pass or fail with the reason | 1,538 |
| `interpro_by_pangenome_id_v02.tsv` | InterPro and surface-architecture annotation of the representative protein (signal peptide, TMH, LPxTG, LysM, GW, Pfam) | 1,838 |
| `host_similarity_by_pangenome_id_v01.tsv` | identity to host proteomes (seabass, tilapia, gariepinus, ...) of the representative protein | 1,838 |
| `nonspecific_by_pangenome_id_v01.tsv` | local exact-match hits against host proteins, with the null comparison | 1,838 |
| `epitope_by_pangenome_id_v01.tsv` | epitope-database hits of the representative protein (peptide hits, e-value, identity, coverage) | 1,838 |
| `protein_descriptors_by_pangenome_id_v01.tsv` | protein descriptors per orthogroup as summary statistics (n, median, quartiles): length, molecular weight, pI, charge at pH 6.8 / 7.0 / 7.4, GRAVY, ... | 3,001 |
| `nucleotide_descriptors_by_pangenome_id_v01.tsv` | nucleotide descriptors per orthogroup as summary statistics: CDS length, GC3, CAI for several hosts, restriction-site counts | 3,001 |
| `descriptors_by_pangenome_id_v01.tsv.gz` | the same descriptors per gene copy and isolate (protein and nucleotide, 171,880 records) | 171,880 |
| `descriptors_by_pangenome_id_v01_excluded.tsv` | the records left out of the descriptor tables, with the step and the reason | 516 |
| `descriptors_population_by_pangenome_id_v01.tsv.gz` | per orthogroup and descriptor: member count, reference value, panel median / quartiles / range, whether the reference lies within the IQR | 43,064 |
| `gene_data_by_pangenome_id_v01.tsv.gz` | the gene-level record per orthogroup and isolate: locus tag, pangenome class (core, softcore, shell, cloud), carriage, product, length, protein and DNA sequence (97 MB) | 171,880 |

The lock status in `route_manifest.tsv` (`LOCKED_VERIFIED`, `LOCKED_PRODUCER_DIVERGED`, `LOCKED_NO_PRODUCER_COPY_FOUND`) is the label written when the files were frozen.
Which project capsule produced each table, and whether that capsule's copy is byte-identical, is in `docs/UPSTREAM_PRODUCERS.tsv`.
`conservation_by_pangenome_id_v01.tsv` differs from its producer's copy in one column only (`reference_locus_tag`: empty here, filled by the producer's chain); the ranking does not read that column.

## Other files the code reads

| file | what | rows |
|---|---|---|
| `route_manifest.tsv` | the lock: for each input its role, status, location and checksum. `code/code_A6434_verify_input_lock_v01.py` checks the 13 tables against it before anything else | 17 |
| `MAP_A5093_locus_pangenome_v02.tsv` | the map of the SIKU01 loci (PGAP locus tag and Prokka locus tag, bridged where both exist) to `pangenome_id`, with the match status and pangenome class; used to attach the literature evidence and to flag genes called more than once | 1,996 |
| `ST_A6035_02_protein_literature_assignments_v01.tsv` | SIKU01 loci with a published vaccine reference: locus tag, PGAP product, gene, reference, PubMed IDs | 69 |
| `ST_A6035_03_vaccine_antigen_crossref_v01.tsv` | cross-reference of vaccine antigens to SIKU01 loci with the PubMed IDs | 15 |

## `figure_inputs/` (not read by the ranking)

| file | what |
|---|---|
| `ion_exchange_buffers.tsv` | the buffers and their buffering pH ranges used for the ion-exchange routes in the figures |
| `codon_usages.tsv` | the codon-usage tables of the host species used for the CAI values |

They are kept here because the figures and the manuscript tables use them; the ranking never opens them.

## Checksums

`preflight/manifests/inputs.tsv` lists every file in this folder with its sha256; the preflight stops the run if any file differs.
