# The 21 result tables

Every run writes these tables to `results/<run>/tables/`. Their names and contents are those of the deposited tables
(`expected/tables/`), so they are compared file by file. Rows are data rows.

A *candidate* is one orthogroup (`pangenome_id`) on one route. Its key is `<pangenome_id>:<route>`, for example `21:silica`.

## Inputs, assembled (step `inputs`)

| table | rows | one row per | content |
|---|---:|---|---|
| `literature_by_pangenome_id_v01.tsv` | 1,838 | orthogroup with a SIKU01 protein | PubMed identifiers and curated vaccine reference of the SIKU01 protein; `rep_status` says whether the transfer was one-to-one |
| `ranking_inputs_by_pangenome_id_v01.tsv` | 1,527 | candidate orthogroup | the ten input layers joined on `pangenome_id` (429 columns). Columns are prefixed with the layer (`conservation__`, `coverage__`, `m0__`, `descriptors_protein__`, `descriptors_nucleotide__`, `epitope__`, `host__`, `surface__`, `literature__`, `nonspecific__`); `rep__*` are the values of the SIKU01 gene copy; `<layer>__evaluable` says whether the layer measured the orthogroup. Every rule reads one of these columns |
| `tbl_A6434_01_input_audit_v01.tsv` | 10 | input layer | how many of the 1,527 orthogroups each layer covers, and what a missing value means in that layer |
| `tbl_A6434_02_spine_exclusions_v01.tsv` | 11 | excluded orthogroup | the 11 core orthogroups left out because the SIKU01 gene is split into two calls, with the reason |

## The rules applied (step `ranking`)

| table | rows | one row per | content |
|---|---:|---|---|
| `candidate_rule_outcomes_v27_v01.tsv` | 122,160 | candidate and rule | the value the rule read (`observed_value`), the threshold used (`threshold_resolved`), and the outcome: PASS / FAIL / NOT_EVALUABLE for a hard gate, +1 / 0 for an additive component |
| `candidate_route_state_v27_v01.tsv` | 9,162 | candidate | number of hard gates that apply, pass, fail, are not evaluable; **`final_pass`**; the additive score. This is the table the shortlists come from |
| `rule_outcome_counts_v27_v01.tsv` | 80 | rule and route | how many candidates passed, failed, were not evaluable, scored +1 or 0 |

## Threshold sweeps (step `sweeps`)

| table | rows | one row per | content |
|---|---:|---|---|
| `ST_A6434_03_parameter_sweeps_v02.tsv` | 56 | gate and sweep value | the sweep plan with every value resolved and the reason for it |
| `hard_gate_sweep_execution_v01.tsv` | 121 | gate, sweep value and population | how many candidates satisfy the gate at that value, and the overlap (Jaccard) with the set at the reference threshold |
| `hard_gate_sweep_summary_v01.tsv` | 16 | gate and population | the range of those counts and overlaps |

A gate that applies to all routes is swept on the 1,527 entry orthogroups (`M0_ENTRY_REFERENCE`); a route-specific gate on the
candidates of each of its routes. A sweep moves one gate only and counts who satisfies that gate; it is not a new final pass.

## Leave-one-out (step `perturbation`)

| table | rows | one row per | content |
|---|---:|---|---|
| `hard_gate_reference_set_v01.tsv` | 6 | route | the final-pass set of the route and the gates that define it |
| `candidate_route_reference_state_v01.tsv` | 9,162 | candidate | final pass, score and each additive component, as the reference of the leave-one-out analyses |
| `hard_gate_step_reference_v01.tsv` | 52 | route and gate | the sequential funnel: candidates arriving at the gate and passing it, in `rule_order` (for reading; final pass does not depend on the order) |
| `hard_gate_loo_definition_v01.tsv` | 14 | hard gate | what "leave this gate out" means |
| `candidate_hard_gate_loo_v01.tsv` | 79,404 | candidate and omitted gate | final pass with and without the gate; `newly_admitted` (the gate had failed it) or `newly_admitted_not_evaluable` (the gate could not be evaluated) |
| `hard_gate_loo_summary_v01.tsv` | 52 | route and omitted gate | final-pass count without the gate, and the change |
| `additive_reference_execution_v01.tsv` | 28 | route and additive component | among the final-pass candidates, how many score +1 |
| `additive_score_distribution_v01.tsv` | 31 | route and score | number of final-pass candidates with that additive score |
| `additive_perturbation_definition_v01.tsv` | 8 | additive component | what "leave this component out" means |
| `candidate_additive_perturbation_v01.tsv` | 8,429 | final-pass candidate and omitted component | score with and without the component |
| `additive_perturbation_summary_v01.tsv` | 28 | route and omitted component | how many scores change, mean and median score, Spearman correlation of the scores before and after |

## Labels inside the tables that name files of the deposit

So that the tables stay identical to the deposited ones, a few provenance labels are written exactly as deposited. They name files
and scripts of the folder layout of the deposit, not of this repository:

| table | column | value | here it means |
|---|---|---|---|
| `hard_gate_sweep_execution_v01.tsv` | `source_population` | `04_tables/candidate_data_v02.tsv` | the candidate frame (built from `ranking_inputs_by_pangenome_id_v01.tsv`) |
| `hard_gate_sweep_execution_v01.tsv` | `source_contract` | `01_analysis_output/derived/ST_A6434_03_parameter_sweeps_v02.tsv` | `tables/ST_A6434_03_parameter_sweeps_v02.tsv` |
| `hard_gate_reference_set_v01.tsv` | `source_table` | `01_analysis_output/derived/candidate_rule_outcomes_v27_v01.tsv` | `tables/candidate_rule_outcomes_v27_v01.tsv` |
| `candidate_route_reference_state_v01.tsv` | `source_final_audit` | `code_A6434_production_v27_v01.py` | the rule application, here `siku01_prioritization/ranking.py` |
| `ST_A6434_03_parameter_sweeps_v02.tsv` | `value_source` | `frozen_pre_execution_2026-10-06` | the date the sweep values were fixed |

The tier columns (`reference_tier`, `perturbed_tier`, `tier_changed`) read NOT_DECLARED / NOT_APPLICABLE: the rule set defines no
tiers.
