# SIKU01 candidate prioritization

The 23-rule, six-route prioritization of *Streptococcus iniae* SIKU01 vaccine candidates from the data descriptor
"Genome of *Streptococcus iniae* SIKU01 and reverse vaccinology dataset with conservation metadata across 90 isolates"
(Zenodo 10.5281/zenodo.15264953). It takes the frozen input tables, applies the rules, and checks the result against the deposited one.

## Run it

```
conda env create -f environment.yml && conda activate siku01-ranking      # python 3.11, pandas 2.3.3 (pandas must be < 3)
bash run_all.sh                                                           # about 2-3 minutes
```

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

## Where things are

| folder | what |
|---|---|
| `inputs/` | the 13 frozen `*_by_pangenome_id` tables, the literature inputs, `candidate_data_v02.tsv`, and `route_manifest.tsv` (the lock: the checksum of every input) |
| `rules/` | `ranking_rules_v27.tsv` (the 23 rules), their resolved thresholds, the sweep plan, the test contracts |
| `code/` | the ranking code, the capsule's own (two edits of 2026-10-23 are recorded in `PROVENANCE.md`); `run_ranking.py` runs it |
| `tests/` | unit, robustness and known-answer test suites |
| `expected_outputs/` | the 21 deposited result files; the final shortlists are `candidate_route_state_v27_v01.tsv` (`final_pass`) |
| `preflight/`, `postflight/` | the checks before and after a run |
| `raw/` | the Panaroo output, input genomes and core alignments the input tables came from (records; not re-run here) |

`analysis.yaml` declares the inputs, the run order and the target outputs. `PROVENANCE.md` says where every file came from.
The inputs are large (the gene table is 97 MB), so clone with enough disk and bandwidth; nothing is downloaded when you run it.
