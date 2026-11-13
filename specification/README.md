# specification/ - which test belongs to which rule

The five tables of the test specification, as deposited in **Data file 2** of the paper (worksheets of the same names) and in the
Zenodo record. They are copied here unchanged, byte for byte (`CHECKSUMS.tsv`); nothing in the code reads them. They answer one
question: for each of the 23 rules, which tests is it owed, what does each test assert, and which file implements it.

| file | one row is | rows | what |
|---|---|---|---|
| `rule_test_contract_v03.tsv` | rule x test family | 152 | which test families each rule owes |
| `test_registry_v03.tsv` | test | 152 | the registered test obligations |
| `test_definition_v03.tsv` | test | 152 | what each registered test asserts |
| `test_case_definition_v01.tsv` | test case | 120 | the individual cases with their expected outcomes |
| `test_implementation_binding_v03.tsv` | test | 32 | the link from a test obligation to the rule (`rule_id`) and to the file that implements it (`resolved_test_file`) |
| `test_binding_in_this_repository.tsv` | test | 32 | written for this repository: where each of the 32 bound tests is here |

## How to read the paths

The tables were written for the folder layout of the original analysis (Zenodo, `SIKU01_2_pipeline_ranking.zip`). In this repository:

- `tests/TST_gene_model/...`, `TST_carriage`, `TST_conservation`, `TST_tmh` (9 of the 32 bindings) are `tests/r/TST_.../...` here, the same files.
- `tests/TST_numerical/...` (15 bindings) and `tests/TST_perturbation/...` (7 bindings) are tests of the **original production script**,
  which this repository replaced by the package `siku01_prioritization/`. Those two files are in the Zenodo record, not here.
  `test_binding_in_this_repository.tsv` names the related test of this repository for each of them and says how it differs.
- One binding (`TST_M0.0`) is the declaration of the entry population and has nothing to execute.

`test_case_definition_v01.tsv` is kept as deposited. `tests/data/rule_boundary_cases.tsv` holds the 68 of its cases that the unit tests
run, with three inputs corrected (see `CHANGES.md`).

`tests/test_specification.py` checks that the five tables are the deposited ones, that every rule named in the bindings is a rule of
`rules/ranking_rules_v27.tsv`, that every hard gate and additive component has at least one bound test, and that every file this
folder says is in the repository exists.
