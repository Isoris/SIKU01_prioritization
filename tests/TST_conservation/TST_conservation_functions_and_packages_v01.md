# TST_conservation (M0.6) — Conservation gate

**Pipeline position** 8 of 35  ·  **Stage** M1 mandatory  ·  **Type** mandatory_gate

## Rule
median normalized conservation score H.norm > threshold, STRICT

## Canonical values
`0.98`

## Where it lives
`S14a_QbD_Ranking_v06_SIKU01.R` line 669 — see `G08_S14a_excerpt_v01.txt`

## Functions
passes_conservation_gate() (helper); inline copy asserted equal in S14.07

## Packages
dplyr; upstream bio3d::entropy() 2.4-4 in S11

## Unit test — functional correctness
Truth table at the cut point. Every case has an expected answer written before running.

0.979 FAIL; 0.980 FAIL (strict >); 0.981 PASS; NA FAIL

## Sensitivity test — robustness and margins
**Applicable:** yes — absolute, not percentage: +10% gives 1.078 which is outside the possible range

Grid: `absolute grid 0.96 / 0.97 / 0.98 / 0.99`

## Current status
UT-DP-01 IN PROGRESS, reviewer-requested (IT-01 done)

## Notes
bio3d H.norm is a CONSERVATION score, 1 = conserved. Orientation probe required.
