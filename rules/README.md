# rules/ - the rules are data

| file | what |
|---|---|
| `ranking_rules_v27.tsv` | the 23 rules: 1 declaration of the entry population (M0.0), 14 hard gates, 8 additive components |
| `rule_parameter_resolution_v02.tsv` | the five thresholds that are statistics of the candidate population, with their frozen values |
| `ST_A6434_03_parameter_sweep_contract_v02.tsv` | the sweep plan: which nine gates are swept, and the steps on each side of the reference threshold |
| `sweep_grid_values_v02.tsv` | the step values of seven of the swept gates, with the reason for each step |

## Columns of `ranking_rules_v27.tsv`

| column | meaning |
|---|---|
| `rule_id`, `layer_position` | the identifier (e.g. `M2_MW`) and the position used in the manuscript (e.g. M2.2) |
| `manuscript_name_short`, `manuscript_name` | the names used in the manuscript |
| `rule_order` | the order of the rule in the sequential funnel (reporting only; final pass does not depend on it) |
| `rule_type`, `role` | `gate` / `hard`: the candidate must pass. `score` / `additive`: +1 when satisfied. `input` / `declaration`: describes the entry population and is not evaluated |
| `stage` | M0 (gene model and conservation), M1 (evidence), M2 (route-specific) |
| `routes`, `n_routes` | `all`, or the routes the rule applies to, separated by `;` |
| `expression` | the rule in words |
| `variable` | the column of the assembled input table the rule reads (`tables/ranking_inputs_by_pangenome_id_v01.tsv` of a run) |
| `operator`, `operator_label` | `==`, `<`, `<=`, `>`, `>=`, or `BETWEEN` (both bounds included) |
| `threshold` | a number, a text value, two numbers `low;high`, or the name of a population threshold (e.g. `Q3_cai_ec`) |
| `unit` | the unit of the variable |
| `score_delta` | 1 for an additive component, 0 for a hard gate |
| `stop_on_fail` | TRUE for a hard gate |
| `missing_policy` | what a missing value does: `not_evaluable` (hard gate) or `skip` (an additive component adds 0). The code refuses a table that says anything else |

## Population thresholds

Five rules compare a candidate with the candidate population itself: `M2_CAI`, `M2_GC3`, `M2_CAI_ON`, `M2_CAI_DR` (at or above the
third quartile) and `M2_CDS_LEN` (at or below the median). The population is the 1,527 entry orthogroups (`M0_ENTRY_REFERENCE`), one
value per orthogroup. The values are frozen in `rule_parameter_resolution_v02.tsv`; every run recomputes them from the data and
stops if one differs.

## Sweep values

The sweep values were fixed before any outcome was computed. For seven gates they are round steps on the measurement scale
(`sweep_grid_values_v02.tsv`, e.g. the molecular-weight bounds moved by 5 or 10 kDa). For the conservation gate they are computed
from the shape of the conservation distribution alone (`conservation_sweep_values` in `siku01_prioritization/sweeps.py`). The
transmembrane-helix gate has its values written in the plan itself.

To change a rule, edit the table, not the code. A run will then, correctly, no longer match `expected/`.
