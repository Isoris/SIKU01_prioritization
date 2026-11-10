#!/usr/bin/env Rscript
# ==============================================================================
# MASTER_numeric_range.unit_test.R
#
# MASTER — agnostic numeric operating-range + target-range gate
#
# PURPOSE
#   Lay down one source-independent numeric range gate that can be reused for
#   MW, GRAVY, pI, pH, length, or any other numeric variable with:
#
#     1. an OPERATING RANGE: values considered valid/plausible input
#     2. a TARGET RANGE: values satisfying the scientific/QbD criterion
#
#   The function is route-agnostic and variable-agnostic. The caller supplies:
#     - the desired numeric column
#     - operating low/high
#     - target low/high
#     - inclusive/exclusive operators for every boundary
#
# CANONICAL INPUT CONTRACT
#   sample_id      character   traceability only; not part of gate logic
#   pangenome_id   character   traceability only; not part of gate logic
#   <value_col>    numeric     integer or double accepted
#
# RANGE SPECIFICATION CONTRACT
#   operating_low       finite numeric scalar
#   operating_high      finite numeric scalar; MUST be > operating_low
#   operating_low_op    ">=" or ">"
#   operating_high_op   "<=" or "<"
#
#   target_low          finite numeric scalar
#   target_high         finite numeric scalar; MUST be > target_low
#   target_low_op       ">=" or ">"
#   target_high_op      "<=" or "<"
#
#   The target interval MUST be a subset of the operating interval.
#
# OUTPUT
#   operating_status:
#     INVALID_MISSING
#     OUTSIDE_OPERATING_LOW
#     OPERATING_OK
#     OUTSIDE_OPERATING_HIGH
#
#   target_status:
#     NOT_EVALUATED
#     FAIL_LOW
#     PASS
#     FAIL_HIGH
#
#   observed_result:
#     TRUE only when target_status == "PASS"
#
# DEPENDENCY
#   R package: dplyr
#   dplyr::between() is used for the common inclusive-inclusive case.
#
# ROUNDING
#   No rounding is performed. Values are tested exactly as supplied.
#
# SYNTHETIC TEST DESIGN
#   The synthetic TSV stores:
#     - bounds
#     - operator strings
#     - symbolic positions such as AT_TARGET_LOW / ABOVE_OPERATING_HIGH
#     - test_setup mutations for input-contract failures
#     - expected PASS/FAIL/status
#     - expected configuration/input-contract errors
#
#   Values are therefore generated RELATIVE TO THE SUPPLIED RANGE rather than
#   being tied to one hard-coded MW, GRAVY, or pI scale.
#
# Synthetic data:
#   MASTER_numeric_range.synthetic_data.tsv
# ==============================================================================


# ------------------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------------------

if (!requireNamespace("dplyr", quietly = TRUE)) {
  stop(
    "MASTER numeric range gate requires the dplyr package. ",
    "Add/pin dplyr in environment.yml before running this test."
  )
}

cat(
  sprintf(
    "MASTER numeric range dependency — dplyr %s\n",
    as.character(utils::packageVersion("dplyr"))
  )
)


# ------------------------------------------------------------------------------
# Basic scalar sanity helper
# ------------------------------------------------------------------------------

assert_finite_scalar <- function(x, name) {

  if (length(x) != 1L ||
      is.na(x) ||
      !is.numeric(x) ||
      !is.finite(x)) {
    stop(name, " must be one finite numeric value.")
  }

  invisible(TRUE)
}


# ------------------------------------------------------------------------------
# Validate operating-range + target-range specification
# ------------------------------------------------------------------------------

validate_range_spec <- function(operating_low,
                                operating_high,
                                operating_low_op,
                                operating_high_op,
                                target_low,
                                target_high,
                                target_low_op,
                                target_high_op) {

  assert_finite_scalar(operating_low, "operating_low")
  assert_finite_scalar(operating_high, "operating_high")
  assert_finite_scalar(target_low, "target_low")
  assert_finite_scalar(target_high, "target_high")

  if (operating_high <= operating_low) {
    stop("operating_high must be strictly greater than operating_low.")
  }

  if (target_high <= target_low) {
    stop("target_high must be strictly greater than target_low.")
  }

  if (!(operating_low_op %in% c(">=", ">"))) {
    stop("operating_low_op must be '>=' or '>'.")
  }

  if (!(operating_high_op %in% c("<=", "<"))) {
    stop("operating_high_op must be '<=' or '<'.")
  }

  if (!(target_low_op %in% c(">=", ">"))) {
    stop("target_low_op must be '>=' or '>'.")
  }

  if (!(target_high_op %in% c("<=", "<"))) {
    stop("target_high_op must be '<=' or '<'.")
  }

  # Target interval must sit numerically inside the operating interval.
  if (target_low < operating_low) {
    stop("target_low cannot be below operating_low.")
  }

  if (target_high > operating_high) {
    stop("target_high cannot be above operating_high.")
  }

  # If both intervals share an endpoint, the target cannot include an endpoint
  # that the operating range explicitly excludes.
  if (target_low == operating_low &&
      operating_low_op == ">" &&
      target_low_op == ">=") {
    stop(
      "Target range cannot include an operating lower endpoint ",
      "that the operating range excludes."
    )
  }

  if (target_high == operating_high &&
      operating_high_op == "<" &&
      target_high_op == "<=") {
    stop(
      "Target range cannot include an operating upper endpoint ",
      "that the operating range excludes."
    )
  }

  invisible(TRUE)
}


# ------------------------------------------------------------------------------
# Generic range predicate
# ------------------------------------------------------------------------------

in_declared_range <- function(x,
                              low,
                              high,
                              low_op = ">=",
                              high_op = "<=") {

  # Missing values never satisfy a range.
  if (length(x) != 1L || is.na(x)) {
    return(FALSE)
  }

  if (!is.numeric(x)) {
    stop("Range input must be numeric (integer or double).")
  }

  # Common inclusive-inclusive case.
  if (low_op == ">=" && high_op == "<=") {
    return(dplyr::between(x, low, high))
  }

  lower_ok <- switch(
    low_op,
    ">=" = x >= low,
    ">"  = x > low,
    stop("low_op must be '>=' or '>'.")
  )

  upper_ok <- switch(
    high_op,
    "<=" = x <= high,
    "<"  = x < high,
    stop("high_op must be '<=' or '<'.")
  )

  lower_ok && upper_ok
}


# ------------------------------------------------------------------------------
# Scalar classifier
# ------------------------------------------------------------------------------

classify_numeric_range <- function(x,
                                   operating_low,
                                   operating_high,
                                   operating_low_op,
                                   operating_high_op,
                                   target_low,
                                   target_high,
                                   target_low_op,
                                   target_high_op) {

  validate_range_spec(
    operating_low = operating_low,
    operating_high = operating_high,
    operating_low_op = operating_low_op,
    operating_high_op = operating_high_op,
    target_low = target_low,
    target_high = target_high,
    target_low_op = target_low_op,
    target_high_op = target_high_op
  )

  if (length(x) != 1L) {
    stop("Numeric range gate expects one scalar value.")
  }

  if (!is.numeric(x)) {
    stop("Numeric range gate input must be numeric (integer or double).")
  }

  if (is.na(x)) {
    return(
      list(
        observed_result = FALSE,
        operating_status = "INVALID_MISSING",
        target_status = "NOT_EVALUATED"
      )
    )
  }

  if (!is.finite(x)) {
    stop("Numeric range gate input must be finite.")
  }

  operating_ok <- in_declared_range(
    x = x,
    low = operating_low,
    high = operating_high,
    low_op = operating_low_op,
    high_op = operating_high_op
  )

  if (!operating_ok) {

    lower_failed <- switch(
      operating_low_op,
      ">=" = x < operating_low,
      ">"  = x <= operating_low
    )

    return(
      list(
        observed_result = FALSE,
        operating_status = if (lower_failed) {
          "OUTSIDE_OPERATING_LOW"
        } else {
          "OUTSIDE_OPERATING_HIGH"
        },
        target_status = "NOT_EVALUATED"
      )
    )
  }

  target_ok <- in_declared_range(
    x = x,
    low = target_low,
    high = target_high,
    low_op = target_low_op,
    high_op = target_high_op
  )

  if (target_ok) {
    return(
      list(
        observed_result = TRUE,
        operating_status = "OPERATING_OK",
        target_status = "PASS"
      )
    )
  }

  lower_failed <- switch(
    target_low_op,
    ">=" = x < target_low,
    ">"  = x <= target_low
  )

  list(
    observed_result = FALSE,
    operating_status = "OPERATING_OK",
    target_status = if (lower_failed) "FAIL_LOW" else "FAIL_HIGH"
  )
}


# ------------------------------------------------------------------------------
# Small wrapper for a sample × pangenome table
# ------------------------------------------------------------------------------

check_numeric_range <- function(dat,
                                value_col,
                                operating_low,
                                operating_high,
                                operating_low_op = ">=",
                                operating_high_op = "<=",
                                target_low,
                                target_high,
                                target_low_op = ">=",
                                target_high_op = "<=") {

  validate_range_spec(
    operating_low = operating_low,
    operating_high = operating_high,
    operating_low_op = operating_low_op,
    operating_high_op = operating_high_op,
    target_low = target_low,
    target_high = target_high,
    target_low_op = target_low_op,
    target_high_op = target_high_op
  )

  required <- c("sample_id", "pangenome_id", value_col)

  missing_cols <- setdiff(required, names(dat))
  if (length(missing_cols) > 0L) {
    stop(
      "Numeric range input-contract failure; missing columns: ",
      paste(missing_cols, collapse = ", ")
    )
  }

  if (!is.character(dat$sample_id)) {
    stop("sample_id must be character.")
  }

  if (!is.character(dat$pangenome_id)) {
    stop("pangenome_id must be character.")
  }

  # R integer and double columns are both numeric and both are accepted.
  if (!is.numeric(dat[[value_col]])) {
    stop(
      value_col,
      " must be numeric (integer or double)."
    )
  }

  classified <- lapply(
    dat[[value_col]],
    classify_numeric_range,
    operating_low = operating_low,
    operating_high = operating_high,
    operating_low_op = operating_low_op,
    operating_high_op = operating_high_op,
    target_low = target_low,
    target_high = target_high,
    target_low_op = target_low_op,
    target_high_op = target_high_op
  )

  dat$observed_result <- vapply(
    classified,
    function(z) z$observed_result,
    logical(1)
  )

  dat$operating_status <- vapply(
    classified,
    function(z) z$operating_status,
    character(1)
  )

  dat$target_status <- vapply(
    classified,
    function(z) z$target_status,
    character(1)
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

# A caller (a per-gate wrapper) may point this at its own fixture. Unset, the
# MASTER script tests itself on its own data, exactly as before.
fixture_env <- Sys.getenv("MASTER_RANGE_FIXTURE", "")
synthetic_file <- if (nzchar(fixture_env)) {
  if (file.exists(fixture_env)) fixture_env else file.path(script_dir, fixture_env)
} else {
  file.path(script_dir, "MASTER_numeric_range.synthetic_data.tsv")
}

if (!file.exists(synthetic_file)) {
  stop("Synthetic numeric-range dataset not found: ", synthetic_file)
}

test_spec <- utils::read.delim(
  synthetic_file,
  header = TRUE,
  sep = "\t",
  quote = "",
  comment.char = "",
  na.strings = "NA",
  stringsAsFactors = FALSE,
  check.names = FALSE
)

test_spec$expected_result <- as.logical(test_spec$expected_result)
test_spec$expected_error  <- as.logical(test_spec$expected_error)

if (!("test_setup" %in% names(test_spec))) {
  stop("Synthetic numeric-range dataset is missing column: test_setup")
}


# ------------------------------------------------------------------------------
# Synthetic-value materializer
#
# This is TEST DATA plumbing only. It does not decide PASS/FAIL.
# It converts symbolic positions from the TSV into values relative to that row's
# supplied operating/target ranges.
# ------------------------------------------------------------------------------

materialize_test_value <- function(value_case,
                                   operating_low,
                                   operating_high,
                                   target_low,
                                   target_high) {

  # Error-case rows may deliberately supply invalid/missing bounds. The
  # materializer is not the validator, so use a harmless placeholder value in
  # those rows and let validate_range_spec() produce the expected error.
  if (anyNA(c(operating_low, operating_high, target_low, target_high))) {
    return(0)
  }

  operating_width <- operating_high - operating_low
  target_width <- target_high - target_low

  # Small deterministic offsets remain proportional to the supplied ranges.
  op_eps <- operating_width / 1000
  target_eps <- target_width / 1000

  switch(
    value_case,

    "BELOW_OPERATING_LOW" =
      operating_low - op_eps,

    "AT_OPERATING_LOW" =
      operating_low,

    "BETWEEN_OPERATING_LOW_TARGET_LOW" =
      (operating_low + target_low) / 2,

    "JUST_BELOW_TARGET_LOW" =
      target_low - target_eps,

    "AT_TARGET_LOW" =
      target_low,

    "MID_TARGET" =
      (target_low + target_high) / 2,

    "AT_TARGET_HIGH" =
      target_high,

    "JUST_ABOVE_TARGET_HIGH" =
      target_high + target_eps,

    "BETWEEN_TARGET_HIGH_OPERATING_HIGH" =
      (target_high + operating_high) / 2,

    "AT_OPERATING_HIGH" =
      operating_high,

    "ABOVE_OPERATING_HIGH" =
      operating_high + op_eps,

    "MISSING" =
      NA_real_,

    stop("Unknown synthetic value_case: ", value_case)
  )
}


# ------------------------------------------------------------------------------
# Run one synthetic case
# ------------------------------------------------------------------------------

run_synthetic_case <- function(row) {

  expected_error <- isTRUE(row$expected_error)

  result <- tryCatch(
    {

      x <- materialize_test_value(
        value_case = row$value_case,
        operating_low = row$operating_low,
        operating_high = row$operating_high,
        target_low = row$target_low,
        target_high = row$target_high
      )

      if (row$input_type == "integer") {
        x <- as.integer(x)
      } else if (row$input_type == "double") {
        x <- as.double(x)
      } else if (row$input_type == "character") {
        x <- as.character(x)
      } else {
        stop("Unknown synthetic input_type: ", row$input_type)
      }

      dat <- data.frame(
        sample_id = as.character(row$sample_id),
        pangenome_id = as.character(row$pangenome_id),
        stringsAsFactors = FALSE
      )

      dat[["x"]] <- x

      # Deliberate table-contract failures encoded in the TSV.
      if (row$test_setup == "MISSING_VALUE_COLUMN") {
        dat[["x"]] <- NULL
      } else if (row$test_setup == "SAMPLE_ID_NUMERIC") {
        dat$sample_id <- 1
      } else if (row$test_setup == "PANGENOME_ID_NUMERIC") {
        dat$pangenome_id <- 1
      } else if (row$test_setup != "NORMAL") {
        stop("Unknown synthetic test_setup: ", row$test_setup)
      }

      checked <- check_numeric_range(
        dat = dat,
        value_col = "x",
        operating_low = row$operating_low,
        operating_high = row$operating_high,
        operating_low_op = row$operating_low_op,
        operating_high_op = row$operating_high_op,
        target_low = row$target_low,
        target_high = row$target_high,
        target_low_op = row$target_low_op,
        target_high_op = row$target_high_op
      )

      list(
        error = FALSE,
        observed_result = checked$observed_result[1],
        operating_status = checked$operating_status[1],
        target_status = checked$target_status[1],
        message = NA_character_
      )
    },
    error = function(e) {
      list(
        error = TRUE,
        observed_result = NA,
        operating_status = NA_character_,
        target_status = NA_character_,
        message = conditionMessage(e)
      )
    }
  )

  error_ok <- identical(result$error, expected_error)

  if (expected_error) {
    return(
      c(
        result,
        list(test_pass = error_ok)
      )
    )
  }

  result_ok <- (
    !is.na(result$observed_result) &&
    identical(result$observed_result, isTRUE(row$expected_result))
  )

  operating_ok <- identical(
    result$operating_status,
    row$expected_operating_status
  )

  target_ok <- identical(
    result$target_status,
    row$expected_target_status
  )

  c(
    result,
    list(
      test_pass = error_ok &&
        result_ok &&
        operating_ok &&
        target_ok
    )
  )
}


# ------------------------------------------------------------------------------
# Execute all synthetic cases
# ------------------------------------------------------------------------------

observed <- lapply(
  seq_len(nrow(test_spec)),
  function(i) run_synthetic_case(test_spec[i, , drop = FALSE])
)

test_spec$observed_error <- vapply(
  observed,
  function(z) z$error,
  logical(1)
)

test_spec$observed_result <- vapply(
  observed,
  function(z) {
    if (length(z$observed_result) == 0L || is.na(z$observed_result)) {
      NA
    } else {
      z$observed_result
    }
  },
  logical(1)
)

test_spec$observed_operating_status <- vapply(
  observed,
  function(z) {
    if (length(z$operating_status) == 0L ||
        is.na(z$operating_status)) {
      NA_character_
    } else {
      z$operating_status
    }
  },
  character(1)
)

test_spec$observed_target_status <- vapply(
  observed,
  function(z) {
    if (length(z$target_status) == 0L ||
        is.na(z$target_status)) {
      NA_character_
    } else {
      z$target_status
    }
  },
  character(1)
)

test_spec$error_message <- vapply(
  observed,
  function(z) {
    if (length(z$message) == 0L || is.na(z$message)) {
      NA_character_
    } else {
      z$message
    }
  },
  character(1)
)

test_spec$test_pass <- vapply(
  observed,
  function(z) z$test_pass,
  logical(1)
)


# ------------------------------------------------------------------------------
# Human-readable echo
# ------------------------------------------------------------------------------

cat("\nMASTER — agnostic numeric operating/target range: synthetic unit test\n\n")

print(
  test_spec[, c(
    "test_id",
    "description",
    "operating_low_op",
    "operating_high_op",
    "target_low_op",
    "target_high_op",
    "value_case",
    "input_type",
    "test_setup",
    "expected_result",
    "observed_result",
    "expected_operating_status",
    "observed_operating_status",
    "expected_target_status",
    "observed_target_status",
    "expected_error",
    "observed_error",
    "test_pass"
  )],
  row.names = FALSE
)


# ------------------------------------------------------------------------------
# PASS / FAIL reason counts for successful-classification cases
# ------------------------------------------------------------------------------

classified <- test_spec[
  !test_spec$expected_error,
  ,
  drop = FALSE
]

expected_final_status <- ifelse(
  classified$expected_operating_status == "OPERATING_OK",
  classified$expected_target_status,
  classified$expected_operating_status
)

observed_final_status <- ifelse(
  classified$observed_operating_status == "OPERATING_OK",
  classified$observed_target_status,
  classified$observed_operating_status
)

status_levels <- unique(c(
  expected_final_status,
  observed_final_status
))

expected_counts <- table(
  factor(expected_final_status, levels = status_levels)
)

observed_counts <- table(
  factor(observed_final_status, levels = status_levels)
)

count_summary <- data.frame(
  status = status_levels,
  expected_n = as.integer(expected_counts),
  observed_n = as.integer(observed_counts),
  observed_percent = round(
    100 * as.integer(observed_counts) / nrow(classified),
    2
  ),
  stringsAsFactors = FALSE
)

cat("\nExpected versus observed PASS / FAIL reason counts:\n\n")
print(count_summary, row.names = FALSE)


# ------------------------------------------------------------------------------
# Final assertion
# ------------------------------------------------------------------------------

n_pass <- sum(test_spec$test_pass)
n_total <- nrow(test_spec)

cat(sprintf(
  "\nSynthetic cases passed: %d / %d\n",
  n_pass,
  n_total
))

if (!all(test_spec$test_pass)) {

  cat("\nFAILED SYNTHETIC CASES:\n\n")

  print(
    test_spec[
      !test_spec$test_pass,
      c(
        "test_id",
        "description",
        "value_case",
        "test_setup",
        "expected_result",
        "observed_result",
        "expected_operating_status",
        "observed_operating_status",
        "expected_target_status",
        "observed_target_status",
        "expected_error",
        "observed_error",
        "error_message"
      ),
      drop = FALSE
    ],
    row.names = FALSE
  )

  stop("MASTER numeric range unit test failed.")
}

cat("MASTER numeric range unit test: PASS\n")
