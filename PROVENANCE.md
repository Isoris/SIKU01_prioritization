# Provenance

The ranking in this repo is capsule `ANL_A6434_CANDIDATE_RANKING` of the SIKU01 project (ResearchOS 1.0.267, capsule revision `v34_v27_cleanup`), copied into a flat layout on 2026-11-10. The code in `code/` and the rules in `rules/` are the capsule's own files, byte for byte, except the two recorded below. Nothing in `code/`, `rules/` or `tests/` was edited for this repo: the folders are only renamed (the temporary working copy of `workdir.py` gives the code the capsule's folder names back).

## Folder mapping

| this repo | capsule layout |
|---|---|
| `rules/` | `capsule_brain/` |
| `code/` | `02_code/` |
| `tests/` | `tests/` |
| `inputs/` (files) | `08_source_data/routed_input/` |
| `inputs/candidate_data_v02.tsv` | `04_tables/candidate_data_v02.tsv` |
| `expected_outputs/` | the project's `expected_outputs/ranking/` |
| `analysis.yaml` | `analysis.yaml` |
| `run_ranking.py`, `workdir.py`, `preflight/`, `postflight/` | written or adapted for this repo (they hold no ranking logic); originals: `Scripts/12_frozen_inputs_to_ranked_candidates.py` and the pipeline's `preflight/`, `postflight/` |

## Changes the capsule's own files received (recorded when they were made)

| file | date | reason |
|---|---|---|
| `02_code/code_A6434_production_v27_v01.py` | 2026-10-23 | load_authority() stops with MISSING_POLICY_NOT_IMPLEMENTED if a rule's declared missing_policy is not the one implemented (hard: not_evaluable, additive: skip). 9 added lines, nothing else changed. |
| `capsule_brain/ranking_rules_v27.tsv` | 2026-10-23 | missing_policy of the 14 hard rules set to not_evaluable (was fail x13, skip x1 for M2_TMH); no threshold, operator, route or score changed. The code never read the column; the published gate tables report 'not evaluable', so the declaration now says what the code does. |

## Where every carried file came from

`capsule sha256` is the hash of the file in the capsule when it was copied; the column `sha256 (repo)` is the hash now. They are equal unless the file is in the table above.

| repo path | capsule path | sha256 (repo) | capsule sha256 | same |
|---|---|---|---|---|
| `analysis.yaml` | `analysis.yaml` | `ab85f67f0d556bab` | `ab85f67f0d556bab` | yes |
| `code/build_literature_by_pangenome_id_v01.py` | `02_code/build_literature_by_pangenome_id_v01.py` | `f9fced58be9660f3` | `f9fced58be9660f3` | yes |
| `code/code_A6434_execute_sweeps_v27_v01.py` | `02_code/code_A6434_execute_sweeps_v27_v01.py` | `619adc675c22bfcc` | `619adc675c22bfcc` | yes |
| `code/code_A6434_inputs_v01.py` | `02_code/code_A6434_inputs_v01.py` | `d6a70565291211b1` | `d6a70565291211b1` | yes |
| `code/code_A6434_freeze_sweeps_v02_v01.py` | `02_code/code_A6434_freeze_sweeps_v02_v01.py` | `f4cf40dd09c7136d` | `f4cf40dd09c7136d` | yes |
| `code/code_A6434_perturbation_v27_v01.py` | `02_code/code_A6434_perturbation_v27_v01.py` | `337889a9625e8b0f` | `337889a9625e8b0f` | yes |
| `code/code_A6434_production_v27_v01.py` | `02_code/code_A6434_production_v27_v01.py` | `c0e9d738f783a634` | `0b4ec87a9795026e` | no (recorded above) |
| `code/code_A6434_rule_authority_test_v02.py` | `02_code/code_A6434_rule_authority_test_v02.py` | `fb3b8434cee5ee4f` | `fb3b8434cee5ee4f` | yes |
| `code/code_A6434_verify_input_lock_v01.py` | `02_code/code_A6434_verify_input_lock_v01.py` | `740ee7431c98bc1c` | `740ee7431c98bc1c` | yes |
| `code/run_A6434_canonical_v01.py` | `02_code/run_A6434_canonical_v01.py` | `217f22fbcc79bcb8` | `217f22fbcc79bcb8` | yes |
| `code/_provenance.py` | `02_code/_provenance.py` | `58a1463784829f89` | `58a1463784829f89` | yes |
| `rules/ranking_rules_v27.tsv` | `capsule_brain/ranking_rules_v27.tsv` | `db3e50bf21b22156` | `e6c219cf05bf22a4` | no (recorded above) |
| `rules/rule_id_crosswalk_v02.tsv` | `capsule_brain/rule_id_crosswalk_v02.tsv` | `c7e473db714b2cb3` | `c7e473db714b2cb3` | yes |
| `rules/rule_parameter_resolution_v02.tsv` | `capsule_brain/rule_parameter_resolution_v02.tsv` | `32c654843a96a551` | `32c654843a96a551` | yes |
| `rules/rule_test_contract_v03.tsv` | `capsule_brain/rule_test_contract_v03.tsv` | `a879ce452c26234d` | `a879ce452c26234d` | yes |
| `rules/ST_A6434_03_parameter_sweep_contract_v02.tsv` | `capsule_brain/ST_A6434_03_parameter_sweep_contract_v02.tsv` | `f621c513bff045f9` | `f621c513bff045f9` | yes |
| `rules/test_case_definition_v01.tsv` | `capsule_brain/test_case_definition_v01.tsv` | `3aae6b8f9165f0c1` | `3aae6b8f9165f0c1` | yes |
| `rules/test_definition_v03.tsv` | `capsule_brain/test_definition_v03.tsv` | `988b455c1f98b446` | `988b455c1f98b446` | yes |
| `rules/test_implementation_binding_v03.tsv` | `capsule_brain/test_implementation_binding_v03.tsv` | `1a5d0c380dd5bdae` | `1a5d0c380dd5bdae` | yes |
| `rules/test_registry_v03.tsv` | `capsule_brain/test_registry_v03.tsv` | `a24b9d8432e0f1a8` | `a24b9d8432e0f1a8` | yes |
| `inputs/candidate_data_v02.tsv` | `04_tables/candidate_data_v02.tsv` | `2026a48f161935a3` | `2026a48f161935a3` | yes |
| `inputs/conservation_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/conservation_by_pangenome_id_v01.tsv` | `d34c9bf40336517f` | `d34c9bf40336517f` | yes |
| `inputs/coverage_qc_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/coverage_qc_by_pangenome_id_v01.tsv` | `faf35836412404bf` | `faf35836412404bf` | yes |
| `inputs/descriptors_by_pangenome_id_v01.tsv.gz` | `08_source_data/routed_input/descriptors_by_pangenome_id_v01.tsv.gz` | `91b431a55a0f2f86` | `91b431a55a0f2f86` | yes |
| `inputs/descriptors_by_pangenome_id_v01_excluded.tsv` | `08_source_data/routed_input/descriptors_by_pangenome_id_v01_excluded.tsv` | `2e94c6fc2f2922a6` | `2e94c6fc2f2922a6` | yes |
| `inputs/descriptors_population_by_pangenome_id_v01.tsv.gz` | `08_source_data/routed_input/descriptors_population_by_pangenome_id_v01.tsv.gz` | `6fee1addf3419598` | `6fee1addf3419598` | yes |
| `inputs/host_similarity_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/host_similarity_by_pangenome_id_v01.tsv` | `f0de4d4581e0ca5b` | `f0de4d4581e0ca5b` | yes |
| `inputs/epitope_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/epitope_by_pangenome_id_v01.tsv` | `2a844258f41d0c81` | `2a844258f41d0c81` | yes |
| `inputs/gene_data_by_pangenome_id_v01.tsv.gz` | `08_source_data/routed_input/gene_data_by_pangenome_id_v01.tsv.gz` | `28480ba193b1ba42` | `28480ba193b1ba42` | yes |
| `inputs/interpro_by_pangenome_id_v02.tsv` | `08_source_data/routed_input/interpro_by_pangenome_id_v02.tsv` | `8382f76d8998205b` | `8382f76d8998205b` | yes |
| `inputs/m0_gate_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/m0_gate_by_pangenome_id_v01.tsv` | `c1eadc7c6893f0ae` | `c1eadc7c6893f0ae` | yes |
| `inputs/MAP_A5093_locus_pangenome_v02.tsv` | `08_source_data/routed_input/MAP_A5093_locus_pangenome_v02.tsv` | `ba261314f7e5fbad` | `ba261314f7e5fbad` | yes |
| `inputs/nonspecific_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/nonspecific_by_pangenome_id_v01.tsv` | `52d978067feba05e` | `52d978067feba05e` | yes |
| `inputs/nucleotide_descriptors_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/nucleotide_descriptors_by_pangenome_id_v01.tsv` | `b2921b3e6928eefb` | `b2921b3e6928eefb` | yes |
| `inputs/protein_descriptors_by_pangenome_id_v01.tsv` | `08_source_data/routed_input/protein_descriptors_by_pangenome_id_v01.tsv` | `a12a3ea71d2efaad` | `a12a3ea71d2efaad` | yes |
| `inputs/route_manifest.tsv` | `08_source_data/routed_input/route_manifest.tsv` | `9bcadd9ef4c7098f` | `9bcadd9ef4c7098f` | yes |
| `inputs/ST_A6035_02_protein_literature_assignments_v01.tsv` | `08_source_data/routed_input/ST_A6035_02_protein_literature_assignments_v01.tsv` | `74590d5a2ea83f79` | `74590d5a2ea83f79` | yes |
| `inputs/ST_A6035_03_vaccine_antigen_crossref_v01.tsv` | `08_source_data/routed_input/ST_A6035_03_vaccine_antigen_crossref_v01.tsv` | `37dc4f97e2a9c01c` | `37dc4f97e2a9c01c` | yes |
| `tests/RULE_TEST_INDEX_v27.tsv` | `tests/RULE_TEST_INDEX_v27.tsv` | `8e8916585fa5841f` | `8e8916585fa5841f` | yes |
| `tests/run_all_tests_A6434_v01.sh` | `tests/run_all_tests_A6434_v01.sh` | `c14c2240d88818de` | `c14c2240d88818de` | yes |
| `tests/TST_carriage/TST_carriage.unit_test.R` | `tests/TST_carriage/TST_carriage.unit_test.R` | `ed72a51dda97af5a` | `ed72a51dda97af5a` | yes |
| `tests/TST_carriage/TST_carriage.robustness_test.R` | `tests/TST_carriage/TST_carriage.robustness_test.R` | `2cf174c6b35276a0` | `2cf174c6b35276a0` | yes |
| `tests/TST_carriage/TST_carriage.synthetic_data.tsv` | `tests/TST_carriage/TST_carriage.synthetic_data.tsv` | `dc4b25a5383e84ea` | `dc4b25a5383e84ea` | yes |
| `tests/TST_carriage/TST_carriage.sensitivity_test.R` | `tests/TST_carriage/TST_carriage.sensitivity_test.R` | `21a641cda700e113` | `21a641cda700e113` | yes |
| `tests/TST_conservation/TST_conservation.robustness_test.R` | `tests/TST_conservation/TST_conservation.robustness_test.R` | `d26c2842b530c8ba` | `d26c2842b530c8ba` | yes |
| `tests/TST_conservation/TST_conservation.sensitivity_test.R` | `tests/TST_conservation/TST_conservation.sensitivity_test.R` | `9f05c1c9b9ded63c` | `9f05c1c9b9ded63c` | yes |
| `tests/TST_conservation/TST_conservation.unit_test.R` | `tests/TST_conservation/TST_conservation.unit_test.R` | `e4b1544057acdd8f` | `e4b1544057acdd8f` | yes |
| `tests/TST_conservation/TST_conservation_design_v01.md` | `tests/TST_conservation/TST_conservation_design_v01.md` | `6b0323d88e4cd257` | `6b0323d88e4cd257` | yes |
| `tests/TST_conservation/TST_conservation_functions_and_packages_v01.md` | `tests/TST_conservation/TST_conservation_functions_and_packages_v01.md` | `82b4f5b98a436a88` | `82b4f5b98a436a88` | yes |
| `tests/TST_conservation/TST_conservation_seed_msa_library_v01.tsv.gz` | `tests/TST_conservation/TST_conservation_seed_msa_library_v01.tsv.gz` | `981518bb7fe22071` | `981518bb7fe22071` | yes |
| `tests/TST_execution/TST_execution_against_data.unit_test.py` | `tests/TST_execution/TST_execution_against_data.unit_test.py` | `bb3de646e4fb57cd` | `bb3de646e4fb57cd` | yes |
| `tests/TST_gene_model/TST_gene_model.robustness_test.R` | `tests/TST_gene_model/TST_gene_model.robustness_test.R` | `7659368ed17bee0e` | `7659368ed17bee0e` | yes |
| `tests/TST_gene_model/TST_gene_model.sensitivity_test.R` | `tests/TST_gene_model/TST_gene_model.sensitivity_test.R` | `5f3361fd0ee4bf11` | `5f3361fd0ee4bf11` | yes |
| `tests/TST_gene_model/TST_gene_model.synthetic_data.tsv` | `tests/TST_gene_model/TST_gene_model.synthetic_data.tsv` | `723b42b859da830e` | `723b42b859da830e` | yes |
| `tests/TST_gene_model/TST_gene_model.unit_test.R` | `tests/TST_gene_model/TST_gene_model.unit_test.R` | `37259bb53cedd3d7` | `37259bb53cedd3d7` | yes |
| `tests/_shared/MASTER_numeric_range.synthetic_data.tsv` | `tests/_shared/MASTER_numeric_range.synthetic_data.tsv` | `491daa6545c44c2a` | `491daa6545c44c2a` | yes |
| `tests/_shared/siku01_helpers_and_tests_v04.R` | `tests/_shared/siku01_helpers_and_tests_v04.R` | `5df9911d18030326` | `5df9911d18030326` | yes |
| `tests/_shared/MASTER_numeric_range_unit_test.R` | `tests/_shared/MASTER_numeric_range_unit_test.R` | `3b780f6117f19c10` | `3b780f6117f19c10` | yes |
| `tests/_shared/siku01_cli_logging_and_sensitivity_v01.R` | `tests/_shared/siku01_cli_logging_and_sensitivity_v01.R` | `e6b54a432e9afa54` | `e6b54a432e9afa54` | yes |
| `tests/TST_tmh/TST_tmh.synthetic_data.tsv` | `tests/TST_tmh/TST_tmh.synthetic_data.tsv` | `9adad0bb558e2ff9` | `9adad0bb558e2ff9` | yes |
| `tests/TST_tmh/TST_tmh.unit_test.R` | `tests/TST_tmh/TST_tmh.unit_test.R` | `fa2a82a7baa19e58` | `fa2a82a7baa19e58` | yes |
| `tests/TST_numerical/TST_numerical_against_production.unit_test.py` | `tests/TST_numerical/TST_numerical_against_production.unit_test.py` | `ec2c89bcd9f7953a` | `ec2c89bcd9f7953a` | yes |
| `tests/TST_numerical/TST_sweep_satisfies_against_production.unit_test.py` | `tests/TST_numerical/TST_sweep_satisfies_against_production.unit_test.py` | `8487a198bfe3cab7` | `8487a198bfe3cab7` | yes |
| `tests/TST_perturbation/TST_perturbation_against_production.unit_test.py` | `tests/TST_perturbation/TST_perturbation_against_production.unit_test.py` | `1f5dc7217b3b45a9` | `1f5dc7217b3b45a9` | yes |

## Not carried

The capsule's bookkeeping (`artifact_manifest.tsv`, `SOURCE_CAPSULE.tsv`, `MODIFICATIONS.tsv`, `verify.py`, `run_all.sh`), the retired pre-v27 scripts, the manuscript-table and figure builders and the older versions of the scripts that were replaced are in the SIKU01 Zenodo deposit (10.5281/zenodo.15264953), where the full capsule layout is kept.
