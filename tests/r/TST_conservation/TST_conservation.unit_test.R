#!/usr/bin/env Rscript
# =============================================================================
# G07_UNIT_conservation_seed_library_v01.R
#
# Apply controlled substitution noise and gap noise to a frozen library of
# synthetic protein MSAs, then measure the ACTUAL TST_conservation (M0.6) gate quantity:
#
#       median H.norm
#
# Design:
#   200 seed MSAs x 20 perturbation conditions = 4,000 measurements
#
# The 200 seed MSAs ARE the replicates. There is no additional 1,000-replicate
# loop.
#
# For every seed x condition:
#
#   seed MSA
#      -> add substitutions OR gaps
#      -> bio3d::entropy()
#      -> median H.norm
#      -> expected gate: median H.norm > 0.98
#      -> observed gate: production passes_conservation_gate()
#
# Outputs:
#   TST_conservation_seed_condition_results.tsv
#   TST_conservation_condition_summary.tsv
#
# Usage:
#   SIKU01_CODE_DIR=scripts \
#   Rscript G07_UNIT_conservation_seed_library_v01.R \
#       TST_conservation_seed_msa_library_v01.tsv.gz [out_dir]
# =============================================================================

# Added 2026-10-01. A missing dependency is not a failing gate. Without this guard an absent bio3d
# raised a raw library() error, which run_all_gates_A6434_v01.sh classifies as FAIL, while the same
# situation in TST_gene_model and TST_numerical is classified BLOCKED by their guards. Nothing about the test's logic,
# thresholds or assertions changes; only what is reported when the package is not installed.
if (!requireNamespace("bio3d", quietly = TRUE)) {
  stop(
    "TST_conservation (M0.6) requires the bio3d package. ",
    "Add/pin bio3d in environment.yml before running this test."
  )
}

cat(
  sprintf(
    "TST_conservation dependency — bio3d %s\n",
    as.character(utils::packageVersion("bio3d"))
  )
)

suppressPackageStartupMessages(library(bio3d))

args <- commandArgs(trailingOnly = TRUE)

# The library ships beside this test, so an unattended runner needs no argument.
# An explicit path still wins, which is how a caller points the test at a larger
# or a regenerated library.
.here <- dirname(sub("^--file=", "",
  c(grep("^--file=", commandArgs(), value = TRUE), "--file=.")[1]))
.default_lib <- file.path(.here, "TST_conservation_seed_msa_library_v01.tsv.gz")
if (length(args) < 1 && !file.exists(.default_lib))
  stop("Provide the seed MSA library, or generate it with TST_conservation_make_seed_msa_library_v01.R")

LIBRARY <- if (length(args) >= 1) args[1] else .default_lib
OUT_DIR <- if (length(args) >= 2) args[2] else file.path(.here, "results")

dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

CODE_DIR <- Sys.getenv("SIKU01_CODE_DIR", "scripts")
HELPER <- file.path(CODE_DIR, "siku01_helpers_and_tests_v04.R")

if (!file.exists(HELPER))
  stop("Production helper not found: ", HELPER)

source(HELPER)

GATE <- 0.98

AA <- c("A","R","N","D","C","Q","E","G","H","I",
        "L","K","M","F","P","S","T","W","Y","V")

# Exactly 20 conditions:
#   10 substitution-only conditions (including the unperturbed 0% control)
#   10 gap-only conditions
conditions <- rbind(
  data.frame(
    condition_id = sprintf("SUB_%02d", 1:10),
    perturbation = "substitution",
    noise_pct = c(0, 0.5, 1, 2, 5, 10, 20, 30, 50, 100),
    gap_pct = 0
  ),
  data.frame(
    condition_id = sprintf("GAP_%02d", 1:10),
    perturbation = "gap",
    noise_pct = 0,
    gap_pct = c(0.5, 1, 2, 3, 5, 7.5, 10, 15, 20, 30)
  )
)

read_library <- function(path) {
  con <- if (grepl("\\.gz$", path, ignore.case = TRUE)) gzfile(path) else path
  read.delim(
    con,
    sep = "\t",
    header = TRUE,
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
}

lib <- read_library(LIBRARY)

required <- c("seed_id", "sample_id", "sequence")
missing <- setdiff(required, names(lib))
if (length(missing))
  stop("Library missing columns: ", paste(missing, collapse = ", "))

seed_ids <- unique(lib$seed_id)

cat("\nG07 conservation seed-library test\n")
cat("seed MSAs:  ", length(seed_ids), "\n", sep = "")
cat("conditions: ", nrow(conditions), "\n", sep = "")
cat("measurements expected: ", length(seed_ids) * nrow(conditions), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

strings_to_matrix <- function(seqs) {

  lens <- nchar(seqs)

  if (length(unique(lens)) != 1L)
    stop("Sequences within a seed MSA have unequal lengths.")

  do.call(
    rbind,
    strsplit(seqs, "", fixed = TRUE)
  )
}

add_perturbation <- function(msa, sub_rate = 0, gap_rate = 0) {

  out <- msa
  n <- length(out)

  if (sub_rate > 0) {
    mask <- matrix(runif(n) < sub_rate, nrow = nrow(out), ncol = ncol(out))
    idx <- which(mask)

    if (length(idx)) {
      current <- out[idx]

      replacement <- vapply(
        current,
        function(x) sample(AA[AA != x], 1),
        character(1)
      )

      out[idx] <- replacement
    }
  }

  if (gap_rate > 0) {
    mask <- matrix(runif(n) < gap_rate, nrow = nrow(out), ncol = ncol(out))
    out[mask] <- "-"
  }

  out
}

# -----------------------------------------------------------------------------
# 200 seeds x 20 conditions
# -----------------------------------------------------------------------------

set.seed(20260826)

rows <- vector("list", length(seed_ids) * nrow(conditions))
k <- 0L

for (seed_id in seed_ids) {

  seed <- lib[lib$seed_id == seed_id, ]
  msa0 <- strings_to_matrix(seed$sequence)

  for (i in seq_len(nrow(conditions))) {

    cnd <- conditions[i, ]

    msa <- add_perturbation(
      msa0,
      sub_rate = cnd$noise_pct / 100,
      gap_rate = cnd$gap_pct / 100
    )

    hnorm <- median(bio3d::entropy(msa)$H.norm)

    expected <- !is.na(hnorm) && hnorm > GATE
    observed <- passes_conservation_gate(hnorm, GATE)

    k <- k + 1L

    rows[[k]] <- data.frame(
      seed_id = seed_id,
      condition_id = cnd$condition_id,
      perturbation = cnd$perturbation,
      noise_pct = cnd$noise_pct,
      gap_pct = cnd$gap_pct,
      median_hnorm = hnorm,
      expected_gate = ifelse(expected, "PASS", "FAIL"),
      observed_gate = ifelse(observed, "PASS", "FAIL"),
      status = ifelse(identical(as.logical(observed), as.logical(expected)),
                      "PASS", "FAIL"),
      stringsAsFactors = FALSE
    )
  }
}

results <- do.call(rbind, rows)

# -----------------------------------------------------------------------------
# Condition-level summary across the 200 seed MSAs
# -----------------------------------------------------------------------------

summarise_condition <- function(d) {

  q <- quantile(
    d$median_hnorm,
    c(0.025, 0.25, 0.50, 0.75, 0.975),
    na.rm = TRUE,
    names = FALSE
  )

  data.frame(
    condition_id = d$condition_id[1],
    perturbation = d$perturbation[1],
    noise_pct = d$noise_pct[1],
    gap_pct = d$gap_pct[1],
    n_seeds = nrow(d),
    hnorm_q025 = q[1],
    hnorm_q25 = q[2],
    median_hnorm = q[3],
    hnorm_q75 = q[4],
    hnorm_q975 = q[5],
    gate_pass_n = sum(d$observed_gate == "PASS"),
    gate_fail_n = sum(d$observed_gate == "FAIL"),
    gate_pass_pct = 100 * mean(d$observed_gate == "PASS"),
    test_fail_n = sum(d$status == "FAIL"),
    stringsAsFactors = FALSE
  )
}

summary <- do.call(
  rbind,
  lapply(
    split(results, results$condition_id),
    summarise_condition
  )
)

# Preserve intended condition order.
summary <- merge(
  conditions,
  summary,
  by = c("condition_id", "perturbation", "noise_pct", "gap_pct"),
  sort = FALSE
)

summary <- summary[
  match(conditions$condition_id, summary$condition_id),
]

# -----------------------------------------------------------------------------
# Write + report
# -----------------------------------------------------------------------------

results_path <- file.path(
  OUT_DIR,
  "TST_conservation_seed_condition_results.tsv"
)

summary_path <- file.path(
  OUT_DIR,
  "TST_conservation_condition_summary.tsv"
)

write.table(
  results,
  results_path,
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

write.table(
  summary,
  summary_path,
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

cat("== Condition summary ==\n")
print(
  summary[, c(
    "condition_id",
    "perturbation",
    "noise_pct",
    "gap_pct",
    "median_hnorm",
    "hnorm_q025",
    "hnorm_q975",
    "gate_pass_pct",
    "test_fail_n"
  )],
  row.names = FALSE
)

n_failed <- sum(results$status == "FAIL")

cat("\nrows measured: ", nrow(results), "\n", sep = "")
cat("expected/observed mismatches: ", n_failed, "\n", sep = "")
cat("results: ", results_path, "\n", sep = "")
cat("summary: ", summary_path, "\n", sep = "")

if (n_failed > 0L)
  stop("At least one expected/observed gate comparison failed.")

cat("\nAll expected/observed gate comparisons passed.\n")
