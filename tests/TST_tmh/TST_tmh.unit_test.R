#!/usr/bin/env Rscript
# =============================================================================
# TST_tmh.unit_test.R
#
# TST_tmh (M2.1) — transmembrane-helix gate.  Stage M1 mandatory.  Recombinant-protein
# routes only.
#
# THIS GATE IS IMPLEMENTED FOR THE FIRST TIME IN S14b
#   It is declared in Methods and in Table 2 and appears in no deposited code
#   path: no `tmh` term exists anywhere in S14a. The gate sheet records that it
#   is implemented in no code path, so there is no legacy behaviour to reproduce
#   and no deposited count to match.
#
# WHY IT GETS ITS OWN GATE RATHER THAN JOINING THE OTHER M1 MANDATORY RULES
#   It is the only mandatory rule in the framework that is asymmetric across
#   modalities: multiple helices are unfavourable for soluble recombinant
#   production and are not exclusionary for a plasmid DNA route, so the gate
#   applies to four of the six routes and not to the other two. A rule that
#   changes the route set cannot be folded into a rule that does not.
#
#   It is also the only mandatory rule whose input is missing for part of the
#   spine, which is what makes the three-state outcome load-bearing rather than
#   decorative.
#
# THREE STATES, NOT TWO
#   The gate reads a representative-derived count. On the spine 29 families do
#   not have one: their representative has no InterProScan record, or there is no
#   unambiguous representative. A comparison against a missing value drops the
#   row inside dplyr::filter() and a fillna(0) passes it. Neither is a decision
#   anyone made, so the gate reports pass / fail / not evaluable and the
#   unevaluable families appear in the funnel instead of vanishing from it.
#
# Consumes : tmh_count [integer, >= 0, NA allowed]
# Function : passes_tmh(tmh_count, max_tmh)
#
# Usage
#   SIKU01_CODE_DIR=../_shared Rscript TST_tmh.unit_test.R
# =============================================================================

CODE_DIR <- Sys.getenv("SIKU01_CODE_DIR", "../_shared")
HELPER <- file.path(CODE_DIR, "siku01_helpers_and_tests_v04.R")
if (!file.exists(HELPER)) stop("helper not found: ", HELPER)
source(HELPER)

args_full <- commandArgs(trailingOnly = FALSE)
file_arg  <- grep("^--file=", args_full, value = TRUE)
HERE <- if (length(file_arg) == 1L)
  dirname(normalizePath(sub("^--file=", "", file_arg))) else getwd()

FIXTURE <- file.path(HERE, "TST_tmh.synthetic_data.tsv")
if (!file.exists(FIXTURE)) stop("synthetic TST_tmh (M2.1) dataset not found: ", FIXTURE)

spec <- utils::read.delim(FIXTURE, sep = "\t", stringsAsFactors = FALSE,
                          na.strings = "NA", quote = "", comment.char = "")
spec$max_tmh <- as.integer(spec$max_tmh)
spec$tmh_count <- suppressWarnings(as.integer(spec$tmh_count))
spec$evaluable <- as.logical(spec$evaluable)

# The gate as the pipeline applies it: the predicate, then the three-state
# reduction. Both are asserted, because a correct predicate behind a wrong
# state reduction still drops candidates silently.
state3 <- function(evaluable, satisfied)
  ifelse(!evaluable, "not_evaluable", ifelse(satisfied, "pass", "fail"))

obs_pred  <- passes_tmh(spec$tmh_count, spec$max_tmh)
obs_state <- state3(spec$evaluable, obs_pred)

spec$observed_predicate <- obs_pred
spec$observed_state     <- obs_state
spec$test_pass <- (obs_pred == spec$expected_predicate) &
                  (obs_state == spec$expected_state)

cat("\nG5 — transmembrane-helix gate: synthetic unit test\n\n")
print(spec[, c("case_id", "description", "tmh_count", "max_tmh", "evaluable",
               "expected_predicate", "observed_predicate",
               "expected_state", "observed_state", "test_pass")],
      row.names = FALSE)

write.table(spec, file.path(HERE, "TST_tmh_results_v01.tsv"), sep = "\t",
            quote = FALSE, row.names = FALSE, na = "NA")

# Monotonicity is a UNIT claim, not a sensitivity measurement: it has an expected
# answer in advance, so a violation is a defect. Raising the permitted helix
# count can only ever retain more.
mono <- vapply(0:6, function(k) sum(passes_tmh(c(0, 1, 2, 3, 4, 5, 6), k)), integer(1))
mono_ok <- all(diff(mono) >= 0)

test_init(HERE, "TST_tmh")
test_step("TST_M2.1_UNIT_boundary", {
  expect_true(all(spec$test_pass), "every declared case returns its expected predicate and state")
  expect_identical(passes_tmh(2L, 2L), TRUE,  "2 helices passes at a <= 2 gate")
  expect_identical(passes_tmh(3L, 2L), FALSE, "3 helices fails at a <= 2 gate")
  expect_identical(passes_tmh(0L, 2L), TRUE,  "0 helices passes")
  expect_identical(passes_tmh(NA_integer_, 2L), FALSE,
                   "a missing count never satisfies the gate")
  expect_true(mono_ok, "retention is monotone non-decreasing in the permitted helix count")
}, class = "UNIT")
test_step("TST_M2.1_UNIT_three_state", {
  expect_true(all(obs_state[!spec$evaluable] == "not_evaluable"),
              "an unevaluable count reports not_evaluable, never fail")
  expect_true(!any(is.na(obs_pred)), "the predicate never returns NA")
  expect_true(length(obs_pred) == nrow(spec), "length is preserved")
}, class = "UNIT")

r <- test_report(HERE, "TST_tmh", note = "TST_tmh (M2.1) unit")
n_fail <- if (is.null(r)) 0L else sum(r$result == "FAIL")
cat(sprintf("\nSynthetic cases passed: %d / %d\n", sum(spec$test_pass), nrow(spec)))
if (!all(spec$test_pass) || n_fail > 0L) stop("TST_tmh (M2.1) transmembrane-helix unit test failed.")
cat("TST_tmh (M2.1) transmembrane-helix gate: PASS\n")
