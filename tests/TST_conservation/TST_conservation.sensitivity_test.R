#!/usr/bin/env Rscript
# TST_conservation (M0.6) — Conservation gate
# SENSITIVITY — a MEASUREMENT. No pass/fail state. Must never abort a run.
#
# Grid : absolute grid 0.96 / 0.97 / 0.98 / 0.99
# Reported per setting: n_entering, n_passing, pct_change_vs_nominal,
#                       gained, lost, jaccard, canonical marked.
#
# Perturb ONLY this gate's parameter. Every other canonical rule stays fixed.



stop("TST_conservation (M0.6) sensitivity sweep NOT IMPLEMENTED. Deliberate: an unrun sweep must not read as a completed one.")
