#!/usr/bin/env Rscript
# TST_carriage (M0.3) — Core-genome carriage
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
# Consumes : pan_class [character, "core"/"accessory", never NA]
# Function : passes_core_genome(pan_class, carriage = NULL)

CODE_DIR <- Sys.getenv("SIKU01_CODE_DIR", "../../05_code")
HELPER <- file.path(CODE_DIR, "siku01_helpers_and_tests_v04.R")
if (!file.exists(HELPER)) stop("helper not found: ", HELPER)
source(HELPER)

FN_NAME <- "passes_core_genome"
if (!exists(FN_NAME)) {
  stop("TST_carriage (M0.3) robustness test cannot run: ", FN_NAME, " is not defined in the helper. ",
       "Implement the gate function first; do not weaken this test to make it pass.")
}
f <- get(FN_NAME)

chk <- function(name, ok, detail = "") {
  cat(sprintf("  %-34s %s %s\n", name, if (isTRUE(ok)) "PASS" else "FAIL", detail))
  isTRUE(ok)
}

cat("\nG02 robustness\n")
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
if (!all(res)) stop("TST_carriage (M0.3) robustness test failed.")
