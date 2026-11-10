## ============================================================================
## siku01_cli_logging_and_sensitivity_v01.R
##
## Additive module. Source it AFTER siku01_helpers_and_tests_v02.R.
## Nothing here replaces the v02 helper; this adds four things:
##
##   Part 1  a dependency-free command-line parser, so every threshold can be
##           tuned without editing the script
##   Part 2  step banners and echo, so a run narrates itself
##   Part 3  a FILTER AUDIT: every filter records n_in, n_out, n_removed and
##           the rule it applied, written to disk. This is the mechanism that
##           proves each filter actually fired and that no stage silently
##           passed rows through untouched.
##   Part 4  GC3 quantile sensitivity, and two corrected figure panels
##
## Style: this is infrastructure, so it is abstracted. The biological rules
## stay written out in S14a.
## ============================================================================


## ============================================================================
## PART 1 — command line
## ============================================================================

## Accepts  --key=value  and  --key value  and bare  --flag
## Unknown keys are an error, so a typo cannot silently leave a default in place.
parse_cli <- function(spec, argv = commandArgs(trailingOnly = TRUE)) {

  out <- lapply(spec, function(s) s$default)
  names(out) <- names(spec)

  if (any(argv %in% c("-h", "--help"))) { print_cli_help(spec); quit(status = 0) }

  i <- 1L
  positional <- character(0)

  while (i <= length(argv)) {
    a <- argv[i]

    if (!grepl("^--", a)) { positional <- c(positional, a); i <- i + 1L; next }

    key <- sub("^--", "", a)
    val <- NA_character_

    if (grepl("=", key, fixed = TRUE)) {
      val <- sub("^[^=]*=", "", key)
      key <- sub("=.*$", "", key)
    }

    rkey <- gsub("-", "_", key)
    if (!rkey %in% names(spec)) stop("unknown option --", key,
                                     "\n  run with --help to see the options")

    if (is.na(val)) {
      if (identical(spec[[rkey]]$type, "flag")) {
        val <- "TRUE"
      } else {
        i <- i + 1L
        if (i > length(argv)) stop("option --", key, " needs a value")
        val <- argv[i]
      }
    }

    out[[rkey]] <- switch(spec[[rkey]]$type,
      numeric = as.numeric(val),
      integer = as.integer(val),
      flag    = as.logical(val),
      val)

    i <- i + 1L
  }

  out$.positional <- positional
  out
}

print_cli_help <- function(spec) {
  cat("\nOptions (all have defaults; --key=value or --key value):\n\n")
  for (nm in names(spec)) {
    s <- spec[[nm]]
    cat(sprintf("  --%-18s %-8s %s\n              default: %s\n",
                gsub("_", "-", nm), paste0("<", s$type, ">"), s$help,
                paste(s$default, collapse = ", ")))
  }
  cat("\n")
}

## record what the run was actually invoked with, for the provenance table
cli_record <- function(opt) {
  keep <- opt[!names(opt) %in% ".positional"]
  data.frame(option = names(keep),
             value  = vapply(keep, function(v) paste(v, collapse = ","), character(1)),
             stringsAsFactors = FALSE)
}


## ============================================================================
## PART 2 — step banners and echo
## ============================================================================

.LOG <- new.env(parent = emptyenv())
.LOG$t0 <- Sys.time()
.LOG$step <- 0L

step_banner <- function(title, detail = "") {
  .LOG$step <- .LOG$step + 1L
  el <- as.numeric(difftime(Sys.time(), .LOG$t0, units = "secs"))
  cat("\n", strrep("=", 76), "\n", sep = "")
  cat(sprintf(" [%02d] %-56s %6.1fs\n", .LOG$step, title, el))
  if (nzchar(detail)) cat("      ", detail, "\n", sep = "")
  cat(strrep("=", 76), "\n", sep = "")
}

log_n <- function(label, n, of = NA_integer_) {
  if (is.na(of)) cat(sprintf("      %-46s %7s\n", label, format(n, big.mark = ",")))
  else cat(sprintf("      %-46s %7s  (%5.1f%%)\n", label,
                   format(n, big.mark = ","), 100 * n / of))
}

log_value <- function(label, value, fmt = "%.4f") {
  cat(sprintf("      %-46s %7s\n", label, sprintf(fmt, value)))
}


## ============================================================================
## PART 3 — the filter audit
##
## Call log_filter() immediately after every filter(). It prints the effect,
## records it, and asserts the arithmetic. At the end, filter_audit_table()
## returns the whole trace so it can be written next to the results.
##
## Two invariants are checked on every call, which is the point:
##   n_out <= n_in                  a filter can never add rows
##   n_removed == n_in - n_out      the accounting closes
## A filter that removes nothing is reported as PASS-THROUGH rather than hidden.
## ============================================================================

.FILT <- new.env(parent = emptyenv())
.FILT$rows <- list()

log_filter <- function(stage, n_in, n_out, rule, expect_shrink = FALSE) {

  removed <- n_in - n_out
  status  <- if (removed == 0L) "pass-through" else "filtered"

  cat(sprintf("      %-30s %6s -> %6s   (-%s)  %s\n", stage,
              format(n_in, big.mark = ","), format(n_out, big.mark = ","),
              format(removed, big.mark = ","),
              if (identical(status, "pass-through")) "[removed nothing]" else ""))

  .FILT$rows[[length(.FILT$rows) + 1L]] <- data.frame(
    order = length(.FILT$rows) + 1L, stage = stage, rule = rule,
    n_in = n_in, n_out = n_out, n_removed = removed,
    pct_removed = if (n_in > 0) round(100 * removed / n_in, 2) else NA_real_,
    status = status, stringsAsFactors = FALSE)

  ## these two are the consistency guarantee, not decoration
  expect_true(n_out <= n_in, paste0("filter '", stage, "' does not add rows"))
  expect_equal(removed, n_in - n_out, paste0("filter '", stage, "' accounting closes"))
  if (expect_shrink)
    expect_true(removed > 0, paste0("filter '", stage, "' actually removed something"))

  invisible(n_out)
}

filter_audit_table <- function() {
  if (!length(.FILT$rows)) return(data.frame())
  do.call(rbind, .FILT$rows)
}

filter_audit_reset <- function() .FILT$rows <- list()

## end-of-run check: every declared stage must appear in the audit exactly once
expect_all_filters_applied <- function(expected_stages) {
  aud <- filter_audit_table()
  missing <- setdiff(expected_stages, aud$stage)
  expect_true(!length(missing),
              paste0("every declared filter ran (missing: ",
                     if (length(missing)) paste(missing, collapse = ", ") else "none", ")"))
  dup <- unique(aud$stage[duplicated(aud$stage)])
  expect_true(!length(dup),
              paste0("no filter stage logged twice (", paste(dup, collapse = ", "), ")"))
}


## ============================================================================
## PART 4 — GC3 quantile sensitivity
##
## GC3 is an empirical quantile of Pre-M1, not an absolute value, so the
## neighbourhood to explore is in quantile space.
##
## Two counts are reported at each setting, and the second is the one that
## matters. "pass_gc3" alone overstates the effect, because a gene that clears
## GC3 may still fail CAI, length or Type IIS. "n_final" holds the other three
## gates fixed and varies only GC3, which is what actually moves the shortlist.
##
## This is hypothesis-generating. It does not validate Q75.
## ============================================================================

gc3_quantile_sensitivity <- function(pre_m1, gates, host,
                                     probs = c(0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90),
                                     canonical = 0.75) {

  thresholds <- vapply(probs, function(p)
    as.numeric(quantile(pre_m1$GC3, p, na.rm = TRUE)), numeric(1))

  n_pass_gc3 <- vapply(thresholds, function(th)
    sum(gates$GC3 >= th, na.rm = TRUE), integer(1))

  ## the other three gates held fixed; only GC3 varies
  n_final <- vapply(thresholds, function(th)
    sum(gates$pass_cai & gates$GC3 >= th & gates$pass_len & gates$pass_iis0,
        na.rm = TRUE), integer(1))

  can_ids <- gates$Locus_tag[gates$pass_cai & gates$pass_gc3 &
                             gates$pass_len & gates$pass_iis0]

  jac <- vapply(thresholds, function(th) {
    ids <- gates$Locus_tag[gates$pass_cai & gates$GC3 >= th &
                           gates$pass_len & gates$pass_iis0]
    u <- length(union(ids, can_ids))
    if (!u) NA_real_ else length(intersect(ids, can_ids)) / u
  }, numeric(1))

  data.frame(
    host             = host,
    gc3_definition   = sprintf("Q%02.0f%s", probs * 100,
                               ifelse(abs(probs - canonical) < 1e-9, " (canonical)", "")),
    quantile         = probs,
    gc3_cutoff       = round(thresholds, 4),
    n_evaluated      = nrow(gates),
    n_pass_gc3       = n_pass_gc3,
    pct_pass_gc3     = round(100 * n_pass_gc3 / nrow(gates), 1),
    n_final_pDNA     = n_final,
    pct_final_pDNA   = round(100 * n_final / nrow(gates), 1),
    jaccard_vs_canon = round(jac, 3),
    stringsAsFactors = FALSE)
}


## ============================================================================
## PART 5 — figure panels that need correcting
##
## The 12-panel manuscript figure is produced by S14b, which holds the original
## plotting code verbatim. Only the panels with an identified defect are
## rebuilt here, so nothing already correct gets silently restyled.
## ============================================================================

theme_siku <- function(base = 11) {
  ggplot2::theme_bw(base_size = base) +
  ggplot2::theme(
    panel.grid.minor = ggplot2::element_blank(),
    panel.border     = ggplot2::element_blank(),
    axis.line        = ggplot2::element_line(colour = "black"),
    plot.title       = ggplot2::element_text(face = "bold", hjust = 0, size = ggplot2::rel(1.0)),
    axis.title       = ggplot2::element_text(face = "bold", size = ggplot2::rel(0.9)),
    legend.position  = "none")
}

## ---------------------------------------------------------------------------
## Panel b, corrected.
##
## The published panel plots post-gate survivors for the four protein routes
## but PRE-gate counts for the two pDNA routes, so pDNA appears to be the two
## best platforms when its final yield is the lowest. This version plots final
## survivors for all six and, optionally, the evaluated count behind them.
## ---------------------------------------------------------------------------
plot_survivors_per_platform <- function(counts_final, counts_evaluated = NULL,
                                        denominator, title = "Final survivors per platform") {
  df <- data.frame(platform = names(counts_final),
                   n = as.integer(counts_final), stringsAsFactors = FALSE)
  df$pct <- round(100 * df$n / denominator, 1)
  df$platform <- factor(df$platform, levels = df$platform[order(df$n)])

  p <- ggplot2::ggplot(df, ggplot2::aes(platform, n, fill = platform)) +
    ggplot2::geom_col(width = 0.7) +
    ggplot2::geom_text(ggplot2::aes(label = sprintf("%d\n%.1f%%", n, pct)),
                       vjust = -0.3, size = 3, fontface = "bold") +
    ggplot2::labs(title = title, x = NULL, y = "Number of candidates") +
    ggplot2::expand_limits(y = max(df$n) * 1.2) +
    theme_siku()

  if (!is.null(counts_evaluated)) {
    ev <- data.frame(platform = names(counts_evaluated),
                     n = as.integer(counts_evaluated), stringsAsFactors = FALSE)
    ev$platform <- factor(ev$platform, levels = levels(df$platform))
    p <- p + ggplot2::geom_col(data = ev, ggplot2::aes(platform, n),
                               fill = NA, colour = "grey40", linetype = 2, width = 0.7)
  }
  p
}

## ---------------------------------------------------------------------------
## pDNA gate funnel, with the count type stated on the plot itself.
## ---------------------------------------------------------------------------
plot_pdna_funnel <- function(funnel_df, host, count_type = "sequential") {
  d <- funnel_df[funnel_df$host == host & funnel_df$count_type == count_type, ]
  d$stage <- factor(d$stage, levels = d$stage)

  ggplot2::ggplot(d, ggplot2::aes(stage, n)) +
    ggplot2::geom_col(width = 0.7, fill = "#4E79A7") +
    ggplot2::geom_text(ggplot2::aes(label = n), vjust = -0.3, size = 3, fontface = "bold") +
    ggplot2::labs(title = sprintf("pDNA gates, %s", host),
                  subtitle = sprintf("%s counts: each bar conditioned on all previous gates",
                                     count_type),
                  x = NULL, y = "pDNA-route survivors") +
    ggplot2::expand_limits(y = max(d$n) * 1.2) +
    theme_siku() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 20, hjust = 1))
}

## ---------------------------------------------------------------------------
## GC3 sensitivity: pass-GC3 versus final pDNA, side by side.
## ---------------------------------------------------------------------------
plot_gc3_sensitivity <- function(sens) {
  long <- rbind(
    data.frame(quantile = sens$quantile, n = sens$n_pass_gc3,   metric = "passes GC3 gate"),
    data.frame(quantile = sens$quantile, n = sens$n_final_pDNA, metric = "final pDNA (other gates fixed)"))

  ggplot2::ggplot(long, ggplot2::aes(quantile, n, colour = metric, shape = metric)) +
    ggplot2::geom_line(linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::geom_vline(xintercept = 0.75, linetype = 2, colour = "grey40") +
    ggplot2::annotate("text", x = 0.75, y = max(long$n), label = " canonical Q75",
                      hjust = 0, size = 3, colour = "grey30") +
    ggplot2::labs(title = sprintf("GC3 design-space sensitivity, %s", sens$host[1]),
                  subtitle = "hypothesis-generating; does not validate Q75",
                  x = "GC3 quantile of Pre-M1 used as the gate",
                  y = "Candidates retained", colour = NULL, shape = NULL) +
    theme_siku() +
    ggplot2::theme(legend.position = "bottom")
}
