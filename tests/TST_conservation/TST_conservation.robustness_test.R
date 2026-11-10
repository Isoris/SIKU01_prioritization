#!/usr/bin/env Rscript
# TST_conservation (M0.6) — Conservation gate
# ROBUSTNESS TEST — input contract, not biology.
#
# Every gate owes the same four guarantees regardless of what it measures:
#
#   R1  NA in  ->  FALSE out, never NA.
#       An NA inside dplyr::filter() drops the row silently, so a gate that
#       propagates NA removes candidates without leaving a trace.
#       
#   R2  a wrong-typed input errors clearly rather than coercing.
#   R3  an empty or zero-length input returns length-zero, not an error.
#   R4  the result is the same length as the input.
#
# Consumes : median_hnorm [double, 0-1, NA allowed]
# Function : passes_conservation(median_hnorm, threshold)

CODE_DIR <- Sys.getenv("SIKU01_CODE_DIR", "../../05_code")
HELPER <- file.path(CODE_DIR, "siku01_helpers_and_tests_v04.R")
if (!file.exists(HELPER)) stop("helper not found: ", HELPER)
source(HELPER)

FN_NAME <- "passes_conservation"
if (!exists(FN_NAME)) {
  stop("TST_conservation (M0.6) robustness test cannot run: ", FN_NAME, " is not defined in the helper. ",
       "Implement the gate function first; do not weaken this test to make it pass.")
}
f <- get(FN_NAME)

chk <- function(name, ok, detail = "") {
  cat(sprintf("  %-34s %s %s\n", name, if (isTRUE(ok)) "PASS" else "FAIL", detail))
  isTRUE(ok)
}

cat("\nG07 robustness\n")
res <- c(
  chk("R1 NA returns FALSE not NA",
      { v <- try(f(NA), silent = TRUE)
        !inherits(v, "try-error") && !is.na(v) && identical(as.logical(v), FALSE) }),
  chk("R3 zero-length input",
      { v <- try(f(numeric(0)), silent = TRUE)
        !inherits(v, "try-error") && length(v) == 0L }),
  chk("R4 length preserved",
      { v <- try(f(c(NA, NA, NA)), silent = TRUE)
        !inherits(v, "try-error") && length(v) == 3L })
)
cat(sprintf("\n  %d / %d passed\n", sum(res), length(res)))
if (!all(res)) stop("TST_conservation (M0.6) robustness test failed.")
