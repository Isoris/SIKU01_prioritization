# inputs/ - what each file is

Everything the prioritization reads is in this folder. Nothing is downloaded and nothing outside the repository is read.
`pangenome_id` is the orthogroup identifier (one gene family of the 90-isolate pangenome); every table is keyed by it, directly or
through a locus tag. Row counts are data rows (header not counted).

`CHECKSUMS.tsv` lists every file with its SHA-256, size, row count, role, and whether the prioritization reads it. Every run starts
by comparing the files with it (`python prioritize.py check-inputs`). The files are stored byte for byte as they were frozen
(`.gitattributes` switches off line-ending conversion), so the checksums of the 13 tables are those of their original lock.

## The 13 frozen tables

Ten are read by the prioritization. Three belong to the frozen input set of the analysis and are kept with it, but no rule needs
them (marked "not read").

| file | what | rows | read |
|---|---|---:|---|
| `conservation_by_pangenome_id_v01.tsv` | amino-acid conservation per orthogroup (normalised Shannon entropy, median and mean, alignment length, sequences, paralog handling) | 1,538 | yes |
| `coverage_qc_by_pangenome_id_v01.tsv` | alignment coverage and occupancy per orthogroup (shared columns, longest shared run, anchor locus) | 1,538 | yes |
| `m0_gate_by_pangenome_id_v01.tsv` | gene-model summary per orthogroup: ORF intact, majority length, annotated forms, topology | 1,538 | yes |
| `interpro_by_pangenome_id_v02.tsv` | InterPro and surface-architecture annotation of the SIKU01 protein (signal peptide, transmembrane helices, LPxTG, LysM, GW, Pfam) | 1,838 | yes |
| `host_similarity_by_pangenome_id_v01.tsv` | identity of the SIKU01 protein to host proteomes | 1,838 | yes |
| `nonspecific_by_pangenome_id_v01.tsv` | local exact-match hits against host proteins, with the null comparison | 1,838 | yes |
| `epitope_by_pangenome_id_v01.tsv` | epitope-database (IEDB) hits of the SIKU01 protein | 1,838 | yes |
| `protein_descriptors_by_pangenome_id_v01.tsv` | protein descriptors per orthogroup as summary statistics (n, median, quartiles); it also carries the pangenome class (core, soft-core, shell, cloud) that defines the candidate set | 3,001 | yes |
| `nucleotide_descriptors_by_pangenome_id_v01.tsv` | nucleotide descriptors per orthogroup as summary statistics: CDS length, GC3, CAI, restriction-site counts | 3,001 | yes |
| `descriptors_by_pangenome_id_v01.tsv.gz` | the same descriptors per gene copy and isolate; the values of the SIKU01 copy (`rep__*`) are what the route rules read | 171,880 | yes |
| `descriptors_by_pangenome_id_v01_excluded.tsv` | the records left out of the descriptor tables, with the step and the reason | 516 | not read |
| `descriptors_population_by_pangenome_id_v01.tsv.gz` | per orthogroup and descriptor: member count, reference value, panel median, quartiles, range | 43,064 | not read |
| `gene_data_by_pangenome_id_v01.tsv.gz` | the gene-level record per orthogroup and isolate: locus tag, pangenome class, product, length, protein and DNA sequence (97 MB) | 171,880 | not read |

## Other inputs

| file | what | rows |
|---|---|---:|
| `MAP_A5093_locus_pangenome_v02.tsv` | the map of the SIKU01 loci (PGAP locus tag and Prokka locus tag) to `pangenome_id`; used to attach the literature evidence, and it is where the 11 split gene calls are seen | 1,996 |
| `ST_A6035_02_protein_literature_assignments_v01.tsv` | SIKU01 proteins with published references: locus tag, product, gene, vaccine reference, PubMed IDs | 69 |
| `ST_A6035_03_vaccine_antigen_crossref_v01.tsv` | cross-reference of vaccine antigens to SIKU01 loci | 15 |

## Where each frozen table was made

Each table was produced by one analysis of the SIKU01 project. The analyses, with their code and outputs, are in the Zenodo deposit
[10.5281/zenodo.15264953](https://doi.org/10.5281/zenodo.15264953), file `SIKU01_1_capsules.zip`, under
`SIKU01_clean_project_2026-10-23/capsules/`.

| input table | analysis folder (in `capsules/`) | file there |
|---|---|---|
| `gene_data_by_pangenome_id_v01.tsv.gz` | `ANL_A5093_PANGENOME_CONSERVATION` | `04_tables/gene_data_by_pangenome_id_v01.tsv.gz` |
| `conservation_by_pangenome_id_v01.tsv` | `ANL_A5093_AMINO_ACID_CONSERVATION` | `04_tables/conservation_by_pangenome_id_v01.tsv` (differs in one column, `reference_locus_tag`, which no rule reads) |
| `m0_gate_by_pangenome_id_v01.tsv` | `ANL_A5093_POPULATION_OCCUPANCY` | `04_tables/m0_gate_by_pangenome_id_v01.tsv` |
| `coverage_qc_by_pangenome_id_v01.tsv` | `ANL_A5093_POPULATION_OCCUPANCY` | `04_tables/coverage_qc_by_pangenome_id_v01.tsv` |
| `descriptors_by_pangenome_id_v01.tsv.gz` | `ANL_A6318_SEQUENCE_DESCRIPTORS` | `04_tables/descriptors_by_pangenome_id_v01.tsv.gz` |
| `descriptors_by_pangenome_id_v01_excluded.tsv` | `ANL_A6318_SEQUENCE_DESCRIPTORS` | `01_analysis_output/derived/descriptors_by_pangenome_id_v01_excluded.tsv` |
| `descriptors_population_by_pangenome_id_v01.tsv.gz` | `ANL_A6318_SEQUENCE_DESCRIPTORS` | `01_analysis_output/derived/descriptors_population_by_pangenome_id_v01.tsv.gz` |
| `protein_descriptors_by_pangenome_id_v01.tsv` | `ANL_A6318_SEQUENCE_DESCRIPTORS` | `01_analysis_output/derived/protein_descriptors_by_pangenome_id_v01.tsv` |
| `nucleotide_descriptors_by_pangenome_id_v01.tsv` | `ANL_A6318_SEQUENCE_DESCRIPTORS` | `01_analysis_output/derived/nucleotide_descriptors_by_pangenome_id_v01.tsv` |
| `interpro_by_pangenome_id_v02.tsv` | `ANL_A3168_SURFACE_ARCHITECTURE` | `04_tables/interpro_by_pangenome_id_v02.tsv` |
| `host_similarity_by_pangenome_id_v01.tsv` | `ANL_A4173_HOST_SIMILARITY` | `04_tables/host_similarity_by_pangenome_id_v01.tsv` |
| `nonspecific_by_pangenome_id_v01.tsv` | `ANL_A2731_LOCAL_HOST_SIMILARITY` | `04_tables/nonspecific_by_pangenome_id_v01.tsv` |
| `epitope_by_pangenome_id_v01.tsv` | `ANL_A8506_EPITOPE` | `04_tables/epitope_by_pangenome_id_v01.tsv` |

`lock_status` in `CHECKSUMS.tsv` is the label written when the tables were frozen: `LOCKED_VERIFIED` (byte-identical to the copy of
the producing analysis at that time), `LOCKED_PRODUCER_DIVERGED` (the conservation table: the producer copy now differs in the one
column named above), `LOCKED_NO_PRODUCER_COPY_FOUND` (no byte copy was located at the time of the lock; `docs/UPSTREAM_PRODUCERS.tsv`
records where the copy was found later). The raw Panaroo output, the input genomes and the core alignments these tables derive from
are in the same deposit (`SIKU01_3_inputs_raw_and_frozen.zip`).
