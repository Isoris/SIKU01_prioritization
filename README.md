# SIKU01 candidate prioritization

The rule-based prioritization of *Streptococcus iniae* SIKU01 vaccine candidates from the data descriptor
"Genome of *Streptococcus iniae* SIKU01 and reverse vaccinology dataset with conservation metadata across 90 isolates"
(data and full analysis record: Zenodo [10.5281/zenodo.15264953](https://doi.org/10.5281/zenodo.15264953)).

**Archived release and data.** This repository at release `v2.0.0` is archived on Zenodo, version DOI
[10.5281/zenodo.24248966](https://doi.org/10.5281/zenodo.24248966), as `SIKU01_9_prioritization_repo_v2.0.0.zip`, together with the data, the
manuscript and the full analysis record (all versions: [10.5281/zenodo.15264953](https://doi.org/10.5281/zenodo.15264953)).
Check the archive against this repository: `git archive v2.0.0` gives the same files; the checksums are in the Zenodo
`SHA256SUMS.txt`.

**Source data at NCBI.** BioProject [PRJNA933632](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA933632); strain SIKU01:
BioSample [SAMN33244440](https://www.ncbi.nlm.nih.gov/biosample/SAMN33244440), reads
[SRR23406922](https://www.ncbi.nlm.nih.gov/sra/SRR23406922), genome
[CP121692.1](https://www.ncbi.nlm.nih.gov/nuccore/CP121692.1) (assemblies GCA_046581345.1 / GCF_046581345.1).
Full list: `ACCESSIONS.tsv` in the Zenodo record.

**Status and how to cite.** The manuscript is **under review**; it has no DOI yet. Until it has one, cite the Zenodo record
(use the version DOI above for this exact release): Andres, Q. L. S., Singchat, W., Srikulnath, K. & Srisapoome, P. (2026).
Genome of *Streptococcus iniae* SIKU01 and reverse vaccinology dataset with conservation metadata across 90 isolates.
Manuscript under review. Zenodo, doi:10.5281/zenodo.24248966. GitHub shows "Cite this repository" from `CITATION.cff`.

It takes 13 frozen input tables, applies 23 rules to 1,527 core orthogroups on six production routes, and writes the result
tables and one shortlist per route. Every run can be checked against the deposited results.

## Run it

```
git clone https://github.com/Isoris/SIKU01_prioritization.git
cd SIKU01_prioritization
conda env create -f environment.yml      # once
conda activate siku01-prioritization
bash run_all.sh                          # about 2 minutes
```

Without conda: `pip install -r requirements.txt` (python 3.11, pandas 2.3.3, numpy 2.3.4) is enough for everything except the R suites.
Without bash (Windows): `python prioritize.py reproduce` and then `python prioritize.py test` do the same two steps.

### What you should see

```
[match]     21 of 21 result tables identical to the deposited tables in expected/tables/
[recompute] 5 of 5 population thresholds reproduced; 9162 candidates recomputed by separate code, 0 differ
[repeat]    54 of 54 files byte-identical between the two runs

final pass per route
   silica             85  ########
   cellulose         515  ####################################################
   aex               387  #######################################
   cex               118  ############
   pdna_tilapia      363  ####################################
   pdna_zebrafish    363  ####################################
   total            1831   (9162 candidates = 1527 orthogroups x 6 routes)
...
reproduce: PASS
...
tests: 43 run, 0 failed, 0 skipped
run_all: PASS
```

and, near the top, `13 of 13 frozen tables and 3 of 3 other inputs identical to their recorded checksum`.

`bash run_all.sh --full` also runs the R test suites of the upstream gate definitions (about 25 minutes, needs Rscript; see `tests/README.md`).

## What comes out

Each run is kept in `results/<date-time>/` (not tracked by git):

| path | what |
|---|---|
| `REPORT.md` | the run in plain words: final pass per route, the rules with the thresholds used |
| `shortlists/final_pass_<route>.tsv` | the final-pass candidates of one route, with the values every rule read (six files) |
| `shortlists/final_pass_all_routes.tsv` | every orthogroup that passes on at least one route, with its state on all six |
| `shortlists/final_pass_summary.tsv` | one row per route: candidates, final pass, fail, not evaluable |
| `routes/<route>/candidates.tsv` | all 1,527 orthogroups on that route: final pass, which gates failed, every rule outcome and value |
| `routes/<route>/gates.tsv` | the hard gates of the route: threshold, pass / fail / not evaluable, the funnel, the effect of removing the gate |
| `routes/<route>/additive_components.tsv` | the additive components of the route |
| `routes/<route>/threshold_sweeps.tsv` | the threshold sweeps of the rules of that route |
| `tables/` | the 21 result tables, the same files as the deposited ones (`docs/OUTPUTS.md` describes each) |
| `run_log.json`, `VERDICT.txt` | versions, steps, checksum of every table; PASS or FAIL of the checks |

`shortlists/` and `routes/` only rearrange what is in `tables/`; the unit tests check that they say the same thing.

## The method in short

- **Candidates.** One candidate is one orthogroup (gene family, `pangenome_id`) on one route. The 1,527 orthogroups are the core
  orthogroups of the 90-isolate pangenome, minus 11 in which the SIKU01 gene is split into two calls.
- **Routes.** Four recombinant-protein routes that differ in the purification step (`silica`, `cellulose`, `aex` = anion exchange,
  `cex` = cation exchange) and two plasmid-DNA routes (`pdna_tilapia`, `pdna_zebrafish`).
- **Rules.** `rules/ranking_rules_v27.tsv` holds the 23 rules: 1 declaration of the entry population, 14 hard gates and 8 additive
  components. Each rule names the routes it applies to, the variable it reads, the operator and the threshold. The code contains no
  threshold; `python prioritize.py rules` prints them.
- **Hard gate.** PASS, FAIL or NOT_EVALUABLE. A candidate is **final pass** on a route when every hard gate of that route is PASS.
  The result does not depend on the order of the gates.
- **Additive component.** +1 when satisfied, 0 otherwise. The additive score counts favourable properties (for example an IEDB
  epitope match, or a codon adaptation index in the top quarter). It never removes a candidate and it is not a ranking of vaccine
  potential.
- **Missing values.** A missing value never satisfies a condition. A hard gate then reports NOT_EVALUABLE (the candidate is not
  final pass, and is counted separately from FAIL); an additive component adds 0. Nothing is filled in.
- **Sensitivity.** Nine gates are re-evaluated at shifted thresholds chosen before any outcome was seen (sweeps), each hard gate
  is removed in turn (leave-one-out), and each additive component is removed in turn.

Example: orthogroup 21 (*polC*) passes every gate shared by all routes, but its protein weighs 165 kDa and the molecular-weight
gate of the protein routes asks for 20 to 60 kDa, so it fails on the four protein routes. `python prioritize.py show polC` prints this.

## Licence

The code is released under the MIT licence (`LICENSE`). The data deposited on Zenodo are CC-BY-4.0.

## Where things are

| path | what |
|---|---|
| `inputs/` | the 13 frozen input tables, the locus map and the two literature tables, with `CHECKSUMS.tsv`; `inputs/README.md` describes each file |
| `rules/` | the rule table, the five frozen population thresholds, the sweep plan; `rules/README.md` |
| `siku01_prioritization/` | the code, one module per step (`inputs`, `rules`, `ranking`, `sweeps`, `perturbation`, `shortlists`, `verify`, `pipeline`, `cli`) |
| `prioritize.py` | the command line |
| `expected/` | the 21 deposited result tables a run is compared with, and the deposited candidate frame; `expected/README.md` |
| `tests/` | the unit tests (Python) and the R suites of the upstream gate definitions; `tests/README.md` |
| `specification/` | the test specification of Data file 2 (which test belongs to which rule, what it asserts, which file implements it), unchanged, and where each bound test is in this repository; `specification/README.md` |
| `docs/OUTPUTS.md` | what each of the 21 result tables contains |
| `docs/UPSTREAM_PRODUCERS.tsv` | which analysis of the project produced each input table |
| `CHANGES.md` | what changed between the first version of this repository and this one |

## Commands

```
python prioritize.py reproduce           run twice, check against the deposited results, keep the run in results/
python prioritize.py run                 run once
python prioritize.py verify DIR          check a finished run
python prioritize.py check-inputs        are the input tables the recorded ones?
python prioritize.py rules --route cex   the rules of one route, with the thresholds used
python prioritize.py show polC           everything about one orthogroup (pangenome_id, gene name or SIKU01 locus tag)
python prioritize.py shortlist silica    the final-pass candidates of a route
python prioritize.py test                the unit tests
```

`rules`, `show` and `shortlist` answer from the deposited tables, so they work before any run.

## What the checks establish

| check | what it shows |
|---|---|
| inputs | every input file has the SHA-256 recorded in `inputs/CHECKSUMS.tsv` (the 13 frozen tables carry the checksum of their original lock) |
| thresholds | the five thresholds that are statistics of the candidate population (four third quartiles, one median) are recomputed from the data and equal the frozen values |
| match | the 21 result tables are identical to the deposited ones (line endings are compared as LF, because one deposited table was written on Windows) |
| recompute | a second implementation of the rules, which shares no code with the first, gives the same state for all 9,162 candidates |
| repeat | two runs give byte-identical files: nothing is random and nothing depends on the date |
| unit tests | known answers for every rule at and around its threshold, for missing values, for the final-pass logic and the additive score; a broken rule table is refused; the shortlists agree with the tables |

## What this repository does not redo

The 13 input tables are results of earlier analyses of the project (pangenome, conservation, sequence descriptors, epitope and
host-similarity screens, domain annotation). They are frozen here and their production is not repeated: the analyses, with their
code, their outputs and the raw Panaroo archives, are in the Zenodo deposit. `inputs/README.md` names the analysis behind each table.
