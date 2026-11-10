#!/usr/bin/env Rscript
# ==============================================================================
# TST_gene_model.unit_test.R
#
# TST_gene_model (M0.1/M0.2) — CDS / protein pair coherence
#
# PURPOSE
#   Lay down a small, source-independent gate for checking whether one nucleotide
#   CDS and one supplied amino-acid sequence form a coherent ORF pair.
#
# CANONICAL INPUT CONTRACT
#   sample_id      character   traceability only; not part of gate logic
#   orthogroup_id  character   traceability only; not part of gate logic
#   nt             character   CDS nucleotide sequence
#   aa             character   supplied protein translation
#
# DEPENDENCY
#   R package: Biostrings 2.80.0
#   Bioconductor: 3.23
#   R: 4.6
#   Add/pin Biostrings in environment.yml; this script also prints the runtime
#   package version so the executed environment is recorded.
#
# TST_gene_model (M0.1/M0.2) RULE
#   PASS when:
#     1. nt and aa are present and non-empty
#     2. surrounding whitespace/case are normalized
#     3. nucleotide length %% 3 == 0
#     4. first codon is a valid bacterial initiation codon (NCBI code 11)
#     5. final codon is a stop codon
#     6. there is no internal in-frame stop
#     7. Biostrings::translate(nt) agrees with aa
#
# IUPAC
#   Biostrings performs nucleotide parsing/translation.
#   if.fuzzy.codon = "error.if.X" accepts a fuzzy/IUPAC codon only when it has
#   one unambiguous translation; a codon whose translation would be X fails.
#
# INTENTIONALLY OUT OF SCOPE FOR TST_gene_model (M0.1/M0.2)
#   - Whether the protein has the expected full length relative to its
#     orthogroup/population. That is the NEXT gate.
#   - Whether the protein is expressed, functional, or biologically real.
#
# Suggested CPP wording for this gate:
#   "Must contain a coherent CDS–protein pair for each isolate/orthogroup record."
#
# Synthetic data:
#   TST_gene_model.synthetic_data.tsv
# ==============================================================================


# ------------------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------------------

if (!requireNamespace("Biostrings", quietly = TRUE)) {
  stop(
    "TST_gene_model (M0.1/M0.2) requires the Biostrings package. ",
    "Add/pin Biostrings in environment.yml before running this test."
  )
}

cat(
  sprintf(
    "TST_gene_model (M0.1/M0.2) dependency — Biostrings %s\n",
    as.character(utils::packageVersion("Biostrings"))
  )
)


# ------------------------------------------------------------------------------
# G00 production predicate
# ------------------------------------------------------------------------------

CODE_DIR <- Sys.getenv("SIKU01_CODE_DIR", "../_shared")
HELPER <- file.path(CODE_DIR, "siku01_helpers_and_tests_v04.R")
if (!file.exists(HELPER)) stop("helper not found: ", HELPER)
source(HELPER)

# The rule itself lives in the helper as passes_orf_pair(). It was defined here
# in the deposited version; moving it left one definition that both this test and
# the robustness test call, which is the arrangement Part B of the helper
# describes. The body is unchanged.



# ------------------------------------------------------------------------------
# Small wrapper for a sample × orthogroup table
# ------------------------------------------------------------------------------

check_orf_pairs <- function(dat) {

  required <- c("sample_id", "orthogroup_id", "nt", "aa")

  missing_cols <- setdiff(required, names(dat))
  if (length(missing_cols) > 0L) {
    stop(
      "TST_gene_model (M0.1/M0.2) input-contract failure; missing columns: ",
      paste(missing_cols, collapse = ", ")
    )
  }

  # Contract check only. We do not silently rescue/coerce malformed columns.
  bad_type <- !vapply(dat[required], is.character, logical(1))
  if (any(bad_type)) {
    stop(
      "TST_gene_model (M0.1/M0.2) input-contract failure; non-character columns: ",
      paste(required[bad_type], collapse = ", ")
    )
  }

  dat$observed_result <- mapply(
    passes_orf_pair,
    dat$nt,
    dat$aa,
    USE.NAMES = FALSE
  )

  dat
}


# ------------------------------------------------------------------------------
# Locate + read the synthetic dataset
# ------------------------------------------------------------------------------

args_full <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args_full, value = TRUE)

script_dir <- if (length(file_arg) == 1L) {
  dirname(normalizePath(sub("^--file=", "", file_arg)))
} else {
  getwd()
}

synthetic_file <- file.path(
  script_dir,
  "TST_gene_model.synthetic_data.tsv"
)

if (!file.exists(synthetic_file)) {
  stop("Synthetic TST_gene_model (M0.1/M0.2) dataset not found: ", synthetic_file)
}

g00_test <- utils::read.delim(
  synthetic_file,
  header = TRUE,
  sep = "\t",
  quote = "",
  comment.char = "",
  na.strings = "NA",
  stringsAsFactors = FALSE,
  check.names = FALSE
)

g00_test$expected_result <- as.logical(g00_test$expected_result)


# ------------------------------------------------------------------------------
# Run the REAL TST_gene_model (M0.1/M0.2) predicate on the synthetic table
# ------------------------------------------------------------------------------

g00_test <- check_orf_pairs(g00_test)

g00_test$test_pass <- (
  !is.na(g00_test$observed_result) &
  g00_test$observed_result == g00_test$expected_result
)


# ------------------------------------------------------------------------------
# Human-readable echo
# ------------------------------------------------------------------------------

cat("\nG01 — CDS / protein pair coherence: synthetic unit test\n\n")

print(
  g00_test[, c(
    "sample_id",
    "orthogroup_id",
    "description",
    "nt",
    "aa",
    "expected_result",
    "observed_result",
    "test_pass"
  )],
  row.names = FALSE
)

n_pass <- sum(g00_test$test_pass)
n_total <- nrow(g00_test)

cat(sprintf("\nSynthetic cases passed: %d / %d\n", n_pass, n_total))

if (!all(g00_test$test_pass)) {

  cat("\nFAILED SYNTHETIC CASES:\n")

  print(
    g00_test[
      !g00_test$test_pass,
      c(
        "sample_id",
        "orthogroup_id",
        "description",
        "nt",
        "aa",
        "expected_result",
        "observed_result"
      ),
      drop = FALSE
    ],
    row.names = FALSE
  )

  stop("TST_gene_model (M0.1/M0.2) unit test failed.")
}

cat("TST_gene_model (M0.1/M0.2) unit test: PASS\n")
