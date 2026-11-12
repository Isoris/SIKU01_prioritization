"""Where things are in the repository, and the names that never change."""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INPUTS = REPO / "inputs"
RULES = REPO / "rules"
EXPECTED = REPO / "expected"
EXPECTED_TABLES = EXPECTED / "tables"
EXPECTED_FRAME = EXPECTED / "frame" / "candidate_data_v02.tsv"
RESULTS = REPO / "results"

# The six production routes, in the order of the deposited candidate frame.
ROUTES = ["silica", "cellulose", "aex", "cex", "pdna_tilapia", "pdna_zebrafish"]
ROUTE_LABEL = {
    "silica": "recombinant protein, silica-affinity purification",
    "cellulose": "recombinant protein, cellulose-affinity purification",
    "aex": "recombinant protein, anion-exchange purification",
    "cex": "recombinant protein, cation-exchange purification",
    "pdna_tilapia": "plasmid DNA vaccine, Nile tilapia",
    "pdna_zebrafish": "plasmid DNA vaccine, zebrafish",
}

# Rule tables (rules/).
RULE_TABLE = "ranking_rules_v27.tsv"
RULESET_ID = "ranking_rules_v27"
PARAMETER_TABLE = "rule_parameter_resolution_v02.tsv"
SWEEP_CONTRACT = "ST_A6434_03_parameter_sweep_contract_v02.tsv"
SWEEP_GRID = "sweep_grid_values_v02.tsv"

# The reference population of the distribution-derived thresholds: one row per orthogroup that enters the prioritization.
REFERENCE_POPULATION = "M0_ENTRY_REFERENCE"
N_REFERENCE = 1527

# The 21 result tables, by the step that writes them. The names are those of the deposited tables and are kept unchanged.
T_LITERATURE = "literature_by_pangenome_id_v01.tsv"
T_RANKING_INPUTS = "ranking_inputs_by_pangenome_id_v01.tsv"
T_INPUT_AUDIT = "tbl_A6434_01_input_audit_v01.tsv"
T_EXCLUSIONS = "tbl_A6434_02_spine_exclusions_v01.tsv"
T_OUTCOMES = "candidate_rule_outcomes_v27_v01.tsv"
T_STATE = "candidate_route_state_v27_v01.tsv"
T_COUNTS = "rule_outcome_counts_v27_v01.tsv"
T_SWEEPS = "ST_A6434_03_parameter_sweeps_v02.tsv"
T_SWEEP_EXECUTION = "hard_gate_sweep_execution_v01.tsv"
T_SWEEP_SUMMARY = "hard_gate_sweep_summary_v01.tsv"
T_REFERENCE_SET = "hard_gate_reference_set_v01.tsv"
T_REFERENCE_STATE = "candidate_route_reference_state_v01.tsv"
T_STEP_REFERENCE = "hard_gate_step_reference_v01.tsv"
T_LOO_DEFINITION = "hard_gate_loo_definition_v01.tsv"
T_LOO_CANDIDATES = "candidate_hard_gate_loo_v01.tsv"
T_LOO_SUMMARY = "hard_gate_loo_summary_v01.tsv"
T_ADDITIVE_REFERENCE = "additive_reference_execution_v01.tsv"
T_SCORE_DISTRIBUTION = "additive_score_distribution_v01.tsv"
T_LOCO_DEFINITION = "additive_perturbation_definition_v01.tsv"
T_LOCO_CANDIDATES = "candidate_additive_perturbation_v01.tsv"
T_LOCO_SUMMARY = "additive_perturbation_summary_v01.tsv"

RESULT_TABLES = [
    T_LITERATURE, T_RANKING_INPUTS, T_INPUT_AUDIT, T_EXCLUSIONS,
    T_OUTCOMES, T_STATE, T_COUNTS,
    T_SWEEPS, T_SWEEP_EXECUTION, T_SWEEP_SUMMARY,
    T_REFERENCE_SET, T_REFERENCE_STATE, T_STEP_REFERENCE,
    T_LOO_DEFINITION, T_LOO_CANDIDATES, T_LOO_SUMMARY,
    T_ADDITIVE_REFERENCE, T_SCORE_DISTRIBUTION,
    T_LOCO_DEFINITION, T_LOCO_CANDIDATES, T_LOCO_SUMMARY,
]
assert len(RESULT_TABLES) == len(set(RESULT_TABLES)) == 21
