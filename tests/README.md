# tests/ - what is tested

## Unit tests (Python)

`python prioritize.py test` runs them (about one minute; `-v` lists each test). They use only the standard library `unittest`,
so nothing extra has to be installed; `python -m pytest tests` works too.

| file | what it checks |
|---|---|
| `test_rules.py` | the rule table has 23 rules (1 + 14 + 8) and the expected gates per route; every rule gives the known answer just below, at and just above its threshold (68 cases from the rule specification in `data/rule_boundary_cases.tsv`, plus generated ones); both bounds of a BETWEEN rule are included; a full truth table for each equality rule; a missing or non-numeric value is not evaluable; a rule table the code does not implement (removed rule, unknown operator or route, other missing-value policy, weighted component, duplicated identifier) is refused |
| `test_ranking.py` | on constructed candidates with the real rule table: all gates satisfied gives PASS on every route; one failing gate gives FAIL; one missing gate value gives NOT_EVALUABLE; FAIL outranks NOT_EVALUABLE; a gate of another route does not apply; the additive score equals the number of satisfied components for every combination (160 combinations) and never changes final pass; the leave-one-out functions and the Spearman correlation on known answers |
| `test_reproduction.py` | one full run from the input tables: the 21 tables are identical to `expected/tables/`; the independent recomputation agrees on all 9,162 candidates and does detect a changed result; final pass per route is 85 / 515 / 387 / 118 / 363 / 363; the frame built from the inputs equals the deposited candidate frame; the 11 excluded split gene calls are exactly the core orthogroups with two SIKU01 gene calls in the locus map; each sweep at its reference threshold counts exactly the candidates that pass the gate; `shortlists/` and `routes/` agree with the tables |
| `test_cli.py` | the commands `rules`, `check-inputs`, `show`, `shortlist`, `verify` answer correctly and a wrong request exits with an error |
| `test_specification.py` | the test specification in `specification/` (the tables of Data file 2 that link each test to its rule): the five tables are the deposited ones, every rule they name is a rule of the rule table, every hard gate and additive component has a bound test, and every file said to be in this repository exists |

## R suites of the upstream gate definitions (`r/`)

`bash tests/r/run_r_tests.sh` (about 22 minutes), or `--fast` to leave out the one long test. `bash run_all.sh --full` includes them.
They need Rscript with bio3d, Biostrings, digest and dplyr (`environment.yml`).

These suites do not test the Python code of this repository. They test, on synthetic data, the R reference functions
(`r/_shared/siku01_helpers_and_tests_v04.R`) that define five of the gate quantities whose values arrive here inside the frozen
input tables:

| suite | gate | what it checks |
|---|---|---|
| `TST_gene_model/` | M0.1 ORF integrity, M0.2 full length | unit and robustness tests of the gene-model functions |
| `TST_carriage/` | M0.3 core-genome carriage | unit and robustness tests |
| `TST_conservation/` | M0.6 conservation | the conservation measure (median normalised Shannon entropy, `bio3d::entropy`) on 200 synthetic alignments with controlled noise, 4,000 simulated measurements; design notes in the two `.md` files |
| `TST_tmh/` | M2.1 transmembrane helices | unit test of the three-state gate (pass / fail / not evaluable) |

The R files are carried unchanged from the first version of this repository. A test that cannot run (a missing package) is reported
BLOCKED and counted as a failure, never as a pass.
