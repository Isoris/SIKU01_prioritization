# SIKU01 candidate prioritization

The 23-rule, six-route prioritization of *Streptococcus iniae* SIKU01 vaccine candidates from the data descriptor
"Genome of *Streptococcus iniae* SIKU01 and reverse vaccinology dataset with conservation metadata across 90 isolates"
(Zenodo 10.5281/zenodo.15264953). It takes the frozen input tables, applies the rules, and checks the result against the deposited one.

## Run it

```
git clone <URL of this repository> SIKU01_prioritization
cd SIKU01_prioritization
conda env create -f environment.yml                                       # once; python 3.11, pandas 2.3.3 (pandas must be < 3), R for the R tests
conda activate siku01-ranking
bash run_all.sh                                                           # about 23 minutes with all tests
bash run_all.sh --no-tests                                                # about 70 seconds: everything except the unit tests
```

The ranking itself takes about 30 seconds. Almost all of the 23 minutes is one R test, `TST_conservation` (4,000 simulated conservation measurements, about 22 minutes); times measured in WSL on a 20-core laptop.

On Windows, run it inside WSL (bash and conda are needed).

## What you should see

The last lines are

```
postflight: PASS - the ranking reproduces the deposited results ...
   silica             85
   cellulose         515
   aex               387
   cex               118
   pdna_tilapia      363
   pdna_zebrafish    363
   total            1831   (9162 candidate x route rows)
run_all: PASS
```

and above them `21 of 21 expected files identical`, `21 of 21 files byte-identical between two runs`, `9162 recomputed, 0 differ`. Without Rscript the four R test suites are
reported as NOT RUN (a warning, never a pass); the four Python suites run.

Every `run_all.sh` keeps the run it checked in `runs/<date-time>/` (not tracked by git):

| file | what |
|---|---|
| the 21 `*.tsv` | the results of the checked run (the same files as `expected_outputs/` when it passes) |
| `run_log.json` | the execution trace: command, versions, each step and its exit code, test results, sha256 of every output and of the whole set |
| `stage_run1.log`, `stage_run2.log` | what the ranking itself printed in the two runs |
| `POSTFLIGHT_VERDICT.txt` | PASS or FAIL, and when |
| `run_all.log` | everything `run_all.sh` printed |

## Where things are

| folder | what |
|---|---|
| `inputs/` | the 13 frozen `*_by_pangenome_id` tables, the literature inputs, `candidate_data_v02.tsv`, and `route_manifest.tsv` (the lock: the checksum of every input); `inputs/README.md` says what each file is |
| `rules/` | `ranking_rules_v27.tsv` (the 23 rules), their resolved thresholds, the sweep plan, the test contracts |
| `code/` | the ranking code, the capsule's own (two edits of 2026-10-23 are recorded in `PROVENANCE.md`); `run_ranking.py` runs it |
| `tests/` | unit, robustness and known-answer test suites; `tests/README.md` says what each suite checks |
| `expected_outputs/` | the 21 deposited result files; the final shortlists are `candidate_route_state_v27_v01.tsv` (`final_pass`) |
| `preflight/`, `postflight/` | the checks before and after a run |
| `raw/` | the Panaroo output, input genomes and core alignments the input tables came from (records; not re-run here) |

`analysis.yaml` declares the inputs, the run order and the target outputs. `PROVENANCE.md` says where every file came from.
The inputs are large (the gene table is 97 MB), so clone with enough disk and bandwidth; nothing is downloaded when you run it.

## Where each of the 13 input tables was made

Each frozen table was produced by one analysis of the SIKU01 project. The analyses, with their code and outputs, are in the Zenodo deposit
[10.5281/zenodo.15264953](https://doi.org/10.5281/zenodo.15264953), file `SIKU01_1_capsules.zip`, under `SIKU01_clean_project_2026-10-23/capsules/`.

| input table (`inputs/`) | analysis folder (in `capsules/`) | file there |
|---|---|---|
| `gene_data_by_pangenome_id_v01.tsv.gz` | `ANL_A5093_PANGENOME_CONSERVATION` | `04_tables/gene_data_by_pangenome_id_v01.tsv.gz` |
| `conservation_by_pangenome_id_v01.tsv` | `ANL_A5093_AMINO_ACID_CONSERVATION` | `04_tables/conservation_by_pangenome_id_v01.tsv` (differs in one column, `reference_locus_tag`, which the ranking does not read) |
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

The full record per table (row counts, scripts that write it, lock status) is in `docs/UPSTREAM_PRODUCERS.tsv`.
