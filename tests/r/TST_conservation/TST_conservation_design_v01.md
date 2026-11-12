# TST_conservation (M0.6) design sheet — Conservation gate

Stage M1 mandatory · position 8/35 · canonical `0.98`

---

## PART A — UNIT TEST (functional correctness)

Discrete inputs, exact expected outputs. Fill this in BEFORE writing code.
If you cannot write the expected answer here first, it is a measurement, not a test.

Suggested cases: 0.979 FAIL; 0.980 FAIL (strict >); 0.981 PASS; NA FAIL

| # | input | expected output | assert or report |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 (NA) |  |  |  |

Class: UNIT / DATA_QC / REGRESSION

A failure of this test means:

---

## PART B — SENSITIVITY TEST (robustness and margins)

Applicable: yes. absolute, not percentage: +10% gives 1.078 which is outside the possible range

Grid: absolute grid 0.96 / 0.97 / 0.98 / 0.99

Population entering this gate:

Reported per setting: n_entering · n_passing · pct_change_vs_nominal · gained · lost · Jaccard

This is a MEASUREMENT. It has no pass/fail state and must never abort the run.

| setting | expected direction | note |
|---|---|---|
| below nominal |  |  |
| nominal |  |  |
| above nominal |  |  |

Monotonicity assertions (these ARE unit tests, keep them in Part A):

---

## Open decision
bio3d H.norm is a CONSERVATION score, 1 = conserved. Orientation probe required.
