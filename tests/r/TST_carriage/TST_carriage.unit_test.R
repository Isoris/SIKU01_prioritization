#!/usr/bin/env Rscript
# ==============================================================================
# TST_carriage.unit_test.R      v02
#
# TST_carriage (M0.3) — core-genome carriage
#
# WHAT CHANGED, AND WHY
#   v01 re-did the paralog decision inside the gate: it read the graph flag and
#   excluded flagged clusters itself. With S07c/S07d upstream that is wrong
#   twice over. S07d step 2 already excludes flagged clusters and step 3b
#   already collapses extra copies, so by the time a row reaches TST_carriage (M0.3) the work
#   is done — and TST_carriage (M0.3) re-deciding it can only ever disagree with what was
#   actually aligned.
#
#   v02 does the opposite. It VERIFIES THE UPSTREAM CLAIM instead of repeating
#   the work. That is a stronger test: an upstream step that says it collapsed
#   and did not is a defect this gate now catches, and v01 could not.
#
# NEW COLUMN
#   paralog_handling   character   what upstream did to this PID
#
#     COLLAPSED   S07d step 3b reduced it to one sequence per isolate.
#                 The gate ASSERTS that: if any sample appears twice the claim
#                 is false and the row FAILS with "collapse claimed but not
#                 applied". This is the case v01 had no way to express.
#     EXCLUDED    S07d step 2 dropped it. Its presence at TST_carriage (M0.3) is a contract
#                 violation, so it FAILS regardless of carriage.
#     NONE        no upstream handling. The legacy path applies: exclude_paralogs
#                 governs, exactly as in v01.
#     UNKNOWN     provenance not recorded. Treated as NONE, deliberately: an
#                 unrecorded claim is not a claim.
#
#   `paralog` (the graph flag) is RETAINED but demoted. After COLLAPSED it is
#   history, not a veto — C14 proves a flagged cluster still passes once it has
#   been collapsed, which is the whole point of collapsing rather than excluding.
#
# STILL TRUE FROM v01
#   carriage = n_distinct(sample_id) / n_genomes >= threshold, default 0.99
#   from S07_Generate_pangenome_IDs_Panaroo.py::_class_from_prop, matching Table 2.
#   n_distinct(sample_id) <= n_genomes, checked before biology.
#   C05 stays. It cannot arise from S07d output, and that is exactly why it
#   stays: "collapsed upstream" is an assumption with an expiry date.
#
# ORDER OF CHECKS IS LOAD-BEARING
#   contract -> upstream claim -> integrity -> paralog policy -> carriage.
#   An EXCLUDED row must fail as a contract violation, not be silently rescued
#   by having good carriage.
#
# MEASURED ON THE REAL DEPOSIT (90 genomes, 3,001 clusters)
#   carriage >= 0.99                    1,538   == class "core" exactly
#   of those flagged paralog == 1           0   exclusion is inert at this cut
#   of those WITH EXTRA COPIES             99   541 surplus sequences
#   So on this cohort COLLAPSED is the branch that matters and EXCLUDED never
#   fires. The gate must handle both anyway.
#
# Synthetic data: TST_carriage.synthetic_data.tsv
# Not executed: written without an R installation available.
# ==============================================================================

`%||%` <- function(a, b) if (is.null(a)) b else a

VALID_HANDLING <- c("NONE", "COLLAPSED", "EXCLUDED", "UNKNOWN")

passes_core_carriage <- function(sample_id,
                                 paralog          = "0",
                                 paralog_handling = "NONE",
                                 n_genomes,
                                 threshold        = 0.99,
                                 exclude_paralogs = TRUE) {

  if (length(n_genomes) != 1L || is.na(n_genomes) || !is.numeric(n_genomes) ||
      n_genomes <= 0)
    return(structure(FALSE, reason = "invalid n_genomes"))
  if (length(threshold) != 1L || is.na(threshold) ||
      threshold < 0 || threshold > 1)
    return(structure(FALSE, reason = "invalid threshold"))

  hand <- unique(toupper(as.character(paralog_handling)))
  if (length(hand) != 1L)
    return(structure(FALSE, reason = "paralog_handling not constant for this PID"))
  if (!hand %in% VALID_HANDLING)
    return(structure(FALSE, reason = paste0("unknown paralog_handling: ", hand)))

  s         <- sample_id[!is.na(sample_id) & trimws(as.character(sample_id)) != ""]
  n_rows    <- length(s)
  n_present <- length(unique(s))

  # 1. upstream claim, before anything else
  if (hand == "EXCLUDED")
    return(structure(FALSE, reason = "EXCLUDED upstream; must not reach this gate",
                     n_present = n_present))
  if (hand == "COLLAPSED" && n_rows != n_present)
    return(structure(FALSE,
                     reason = sprintf("collapse claimed but not applied: %d rows over %d samples",
                                      n_rows, n_present),
                     n_present = n_present))

  # 2. integrity
  if (n_present > n_genomes)
    return(structure(FALSE, reason = "n_present exceeds n_genomes",
                     n_present = n_present))

  # 3. paralog policy, legacy path only
  if (hand %in% c("NONE", "UNKNOWN")) {
    par <- unique(as.character(paralog))
    if (isTRUE(exclude_paralogs) && any(!is.na(par) & par %in% c("1", "TRUE", "true")))
      return(structure(FALSE, reason = "paralogous cluster excluded at the gate",
                       n_present = n_present))
  }

  # 4. biology
  carriage <- n_present / n_genomes
  structure(carriage >= threshold,
            reason    = if (carriage >= threshold) "carriage meets threshold"
                        else "carriage below threshold",
            n_present = n_present, carriage = carriage)
}

check_core_carriage <- function(dat) {
  required <- c("case_id", "pangenome_id", "sample_id", "paralog",
                "paralog_handling", "n_genomes", "threshold",
                "exclude_paralogs", "expected_result")
  miss <- setdiff(required, names(dat))
  if (length(miss)) stop("TST_carriage (M0.3) input-contract failure; missing: ",
                         paste(miss, collapse = ", "))

  keys <- unique(dat[, c("case_id", "pangenome_id")])
  out <- do.call(rbind, lapply(seq_len(nrow(keys)), function(i) {
    sub <- dat[dat$case_id == keys$case_id[i] &
               dat$pangenome_id == keys$pangenome_id[i], , drop = FALSE]
    for (cl in c("n_genomes", "threshold", "exclude_paralogs",
                 "paralog_handling", "expected_result")) {
      if (length(unique(sub[[cl]])) != 1L)
        stop("TST_carriage (M0.3) fixture failure: '", cl, "' is not constant within case ",
             keys$case_id[i])
    }
    res <- passes_core_carriage(
      sample_id        = sub$sample_id,
      paralog          = sub$paralog,
      paralog_handling = sub$paralog_handling[1],
      n_genomes        = as.numeric(sub$n_genomes[1]),
      threshold        = as.numeric(sub$threshold[1]),
      exclude_paralogs = as.logical(sub$exclude_paralogs[1]))
    data.frame(case_id = keys$case_id[i], pangenome_id = keys$pangenome_id[i],
      n_rows = nrow(sub), n_present = attr(res, "n_present") %||% 0L,
      n_genomes = as.numeric(sub$n_genomes[1]),
      threshold = as.numeric(sub$threshold[1]),
      paralog = sub$paralog[1], handling = sub$paralog_handling[1],
      expected_result = sub$expected_result[1],
      observed_result = if (isTRUE(as.logical(res))) "PASS" else "FAIL",
      reason = attr(res, "reason"), description = sub$description[1],
      stringsAsFactors = FALSE)
  }))
  out$test_pass <- out$observed_result == out$expected_result
  out
}

args_full  <- commandArgs(trailingOnly = FALSE)
file_arg   <- grep("^--file=", args_full, value = TRUE)
script_dir <- if (length(file_arg) == 1L)
  dirname(normalizePath(sub("^--file=", "", file_arg))) else getwd()

synthetic_file <- file.path(script_dir, "TST_carriage.synthetic_data.tsv")
if (!file.exists(synthetic_file))
  stop("Synthetic TST_carriage (M0.3) dataset not found: ", synthetic_file)

g02 <- utils::read.delim(synthetic_file, header = TRUE, sep = "\t", quote = "",
                         comment.char = "", na.strings = "NA",
                         stringsAsFactors = FALSE, check.names = FALSE,
                         colClasses = "character")

res <- check_core_carriage(g02)
cat("\nG02 — core-genome carriage: synthetic unit test (v02)\n\n")
print(res[, c("case_id", "n_rows", "n_present", "n_genomes", "threshold",
              "paralog", "handling", "expected_result", "observed_result",
              "reason", "test_pass")], row.names = FALSE)
cat(sprintf("\nSynthetic cases passed: %d / %d\n", sum(res$test_pass), nrow(res)))
if (!all(res$test_pass)) {
  cat("\nFAILED SYNTHETIC CASES:\n")
  print(res[!res$test_pass, ], row.names = FALSE)
  stop("TST_carriage (M0.3) unit test failed.")
}
cat("TST_carriage (M0.3) unit test: PASS\n")
