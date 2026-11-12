# expected/ - the deposited results a run is compared with

| path | what |
|---|---|
| `tables/` | the 21 result tables of the prioritization as deposited (Zenodo 10.5281/zenodo.15264953). `docs/OUTPUTS.md` describes each |
| `MANIFEST.tsv` | for each of the 21 tables: SHA-256 (line endings read as LF), size as deposited, number of data rows |
| `frame/candidate_data_v02.tsv` | the candidate frame as deposited: 1,527 orthogroups x 6 routes = 9,162 rows |

`python prioritize.py reproduce` (and `verify DIR`) compares every table of a run with `tables/` through `MANIFEST.tsv`. The files
are kept byte for byte as deposited. One of them (`literature_by_pangenome_id_v01.tsv`) was written on Windows and has CRLF line
endings; a run writes LF everywhere, so the comparison reads CRLF as LF. Nothing else is normalised.

## The candidate frame

In the deposit, the rules were applied to a stored file, `candidate_data_v02.tsv`. This repository does not read that file: it
builds the frame from the input tables on every run (`build_frame` in `siku01_prioritization/inputs.py`). The deposited file is kept
here so that the two can be compared, and `tests/test_reproduction.py` does so: same 9,162 rows in the same order, and the same text
in each of the 64 columns they share, which include every column a rule reads. The deposited file has five further columns: two
labels (`candidate_id`, `route_id`) and three scores of an earlier rule set (`score_m1_general`, `score_m1_protein`,
`score_m2_pdna`) that no current rule reads.

## Changing the reference

`expected/` changes only when the results are meant to change (a rule, a threshold or an input table was changed on purpose and the
new results were reviewed). Then copy the new `tables/` of the run here and run `python prioritize.py manifest`.
