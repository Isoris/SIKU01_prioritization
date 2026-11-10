#!/usr/bin/env Rscript
# TST_carriage (M0.3) — Core-genome carriage
# SENSITIVITY — a MEASUREMENT. No pass/fail state. Must never abort a run.
#
# Grid : carriage fraction 0.90 / 0.95 / 0.99 / 1.00
# Reported per setting: n_entering, n_passing, pct_change_vs_nominal,
#                       gained, lost, jaccard, canonical marked.
#
# Perturb ONLY this gate's parameter. Every other canonical rule stays fixed.



stop("TST_carriage (M0.3) sensitivity sweep NOT IMPLEMENTED. Deliberate: an unrun sweep must not read as a completed one.")
