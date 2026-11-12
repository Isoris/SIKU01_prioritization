# tests/ - what each test suite checks

The tests run automatically inside every ranking run (step 6 of `run_ranking.py`, after the ranking); `postflight/postflight.py` fails the run if any test fails.
With bash and Rscript available, `run_all_tests_A6434_v01.sh` runs all suites; without them only the four Python suites run and the R suites are reported as NOT RUN, never as passed.

| suite | language | what it checks | rules |
|---|---|---|---|
| `TST_gene_model/` | R | unit, robustness and sensitivity tests of the gene-model gates on synthetic data | M0.1 ORF intact, M0.2 full length |
| `TST_carriage/` | R | the same for core-genome carriage | M0.3 |
| `TST_conservation/` | R | the conservation measure (median normalised Shannon entropy, `bio3d::entropy`) on 200 synthetic alignments with controlled noise (`TST_conservation_seed_msa_library_v01.tsv.gz`); design notes in the two `.md` files | M0.6 |
| `TST_tmh/` | R | the transmembrane-helix gate on synthetic data | M2.1 |
| `TST_numerical/` | Python | known-answer tests: every hard and additive rule evaluated by the production code itself (`evaluate()`), and the comparison function the sweeps use (`satisfies()`) | all 22 hard and additive rules |
| `TST_perturbation/` | Python | known-answer tests of the leave-one-rule-out functions (`final_pass()`, `score()`) | all rules |
| `TST_execution/` | Python | re-derives the reference execution and the sensitivity sweeps from the real input frame with the production functions, and checks every deposited row | all rules |
| `_shared/` | R | helpers the R suites load (numeric-range checks, logging) | - |

Other files:

- `RULE_TEST_INDEX_v27.tsv`: for each of the 23 rules, which unit, robustness, sensitivity, known-answer and sweep tests cover it.
- `run_all_tests_A6434_v01.sh`: runs every suite (`--suite NAME` for one, `--with-sens` adds the sensitivity sweeps). It writes one status line per test (PASS, FAIL, NOT_IMPLEMENTED, BLOCKED); a missing test is never counted as a pass.

The full test specification (152 registered tests, 120 test cases) is in `rules/` (`test_registry_v03.tsv`, `test_definition_v03.tsv`, `test_case_definition_v01.tsv`, `rule_test_contract_v03.tsv`, `test_implementation_binding_v03.tsv`) and in Data file 2 of the deposit.
