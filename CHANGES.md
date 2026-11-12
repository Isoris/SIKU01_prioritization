# Changes

## Version 2 (2026-11-12): reorganisation, same results

The results are unchanged: the 21 result tables are byte-identical to the deposited ones (line endings read as LF), which
`python prioritize.py reproduce` checks on every run. What changed is how the repository is organised.

Version 1 is the state of this repository up to commit `d25d6bb`. It carried the ranking analysis in the folder layout of the
research-management system it was developed in, and ran the original scripts inside a temporary copy that restored that layout.
The original scripts and their full folder are in the Zenodo deposit (10.5281/zenodo.15264953, `SIKU01_2_pipeline_ranking.zip`).

### Code

| version 1 | version 2 | what changed |
|---|---|---|
| `code/` (9 scripts), `run_ranking.py`, `workdir.py` | `siku01_prioritization/` (one module per step), `prioritize.py` | the scripts became functions that receive their paths; the temporary working copy is gone. The computations are the same, line for line where they produce numbers |
| `code/_provenance.py` | removed | it called a research-management engine that is not part of the repository, so every run printed "provenance NOT recorded" warnings. Each run now writes `run_log.json` with the checksum of every table |
| `code/run_A6434_canonical_v01.py`, `analysis.yaml` | `siku01_prioritization/pipeline.py` | the run order was read from a 1,445-line bookkeeping file; it is now seven named steps in one function |
| `satisfies()` in the sweep script and `evaluate()` in the production script | one function, `rules.evaluate` | the two comparison functions gave the same answer for every swept gate (a test of version 1 asserted it); the sweeps now call the same function as the ranking, and refuse to sweep an equality rule |
| `code/code_A6434_rule_authority_test_v02.py` | `rules.check_parameters` and `tests/test_rules.py` | the recomputation of the five population thresholds runs inside every run; the boundary cases moved to the unit tests |
| `preflight/`, `postflight/` | `siku01_prioritization/verify.py`, `inputs.check_inputs`, the `reproduce` command | same checks (inputs unchanged, 21 tables identical, two runs identical, independent recomputation), fewer moving parts |
| `--brain` option, mentions of `tuning/tune.py` | removed | they referred to a tuning tool that was never in the repository |
| frozen candidate frame `inputs/candidate_data_v02.tsv` read by the ranking | frame built from the input tables on every run | the stored frame was a deposit that no script rebuilt. It is now built in `inputs.build_frame`, and a test compares it with the deposited file, kept in `expected/frame/` |

### Rules

| version 1 | version 2 | what changed |
|---|---|---|
| `rules/ranking_rules_v27.tsv`, 32 columns | same file, 19 columns | no rule, route, variable, operator or threshold changed. Removed: 13 bookkeeping columns about earlier implementations and test bindings, several with out-of-date entries such as "NO CURRENT V25 PRODUCTION FUNCTION" or "MISSING_V25_IMPLEMENTATION" for rules that are implemented and tested (`manuscript_name_alt`, `score_delta_penalty`, `penalty_condition`, `implementation_version`, `route_binding`, `code_function`, `test_family_id`, `legacy_test_suite`, `legacy_test_script`, `test_binding_status`, `table_version`, `expression_id`, `criterion_ids`). Line endings are now LF |
| sweep step values written as literals in the freeze script | `rules/sweep_grid_values_v02.tsv` | the 28 values and their reasons moved from code to a table, unchanged |
| `rules/rule_id_crosswalk_v02.tsv` | removed | a map from retired rule identifiers; nothing reads it |
| `rules/test_registry_v03.tsv`, `test_definition_v03.tsv`, `rule_test_contract_v03.tsv`, `test_implementation_binding_v03.tsv` | removed | a registry of 152 registered tests; many entries named test scripts of an earlier layout and carried statuses that were out of date. What is tested is now stated in `tests/README.md` and is what the test files do |
| `rules/test_case_definition_v01.tsv` | `tests/data/rule_boundary_cases.tsv` | the 68 criterion cases are kept and now all run. For the five population thresholds the "exactly at the threshold" input had been rounded to 12 decimals; in three cases (`M2_GC3`, `M2_CAI_ON`, `M2_CAI_DR`) the rounded input lies just below the threshold, so the expected answer "True" was wrong, and version 1 skipped these cases silently. The five inputs are now the frozen threshold values themselves |
| the missing-value policy edit of 2026-10-23 (hard gates `not_evaluable`, additive `skip`) | kept | `rules.load_rules` refuses a table that declares another policy |

### Inputs

| version 1 | version 2 | what changed |
|---|---|---|
| `inputs/route_manifest.tsv` and `preflight/manifests/inputs.tsv` | `inputs/CHECKSUMS.tsv` | one list. The 13 frozen tables keep the SHA-256 and the lock status of the original lock; the lock's four placeholder rows and its paths into the old folder layout are gone; the locus map and the two literature tables, which the lock did not cover, are hashed too; a column says which tables the prioritization reads |
| `inputs/figure_inputs/` | removed | two small tables used for figures, never read by the ranking (they are in the deposit) |
| `raw/` (Panaroo output, input genomes, core alignments: 44 MB of archives) | removed | records that no step here reads; they are in the deposit (`SIKU01_3_inputs_raw_and_frozen.zip`) |

### Tests

| version 1 | version 2 | what changed |
|---|---|---|
| four Python suites that located the scripts inside the working copy and lifted functions out of their source text | `tests/test_*.py` (39 tests, standard library) | the tests import the functions they test. The additive-score truth table of version 1 compared two sums of the same list and could not fail; it is replaced by a test that builds a candidate for each combination and runs the real scoring |
| four R suites run by default (22 minutes) | `tests/r/`, run with `bash run_all.sh --full` | files unchanged. They test the R reference functions of five upstream gate quantities, not the Python code here, and `tests/README.md` now says so |
| three `*.sensitivity_test.R` files | removed | each only stopped with the message "NOT IMPLEMENTED" |

### Outputs

New, next to the 21 tables: `shortlists/` (final-pass candidates per route and across routes), `routes/<route>/` (candidates, gates,
additive components and sweeps of one route), `REPORT.md`. They are rearrangements of the 21 tables.
