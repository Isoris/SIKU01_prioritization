## ============================================================================
## siku01_helpers_and_tests_v04.R
##
##   Part A  versioned, non-clobbering, atomic output
##   Part B  the QbD RULES, defined once and used by both the pipeline and the
##           tests, so the two cannot drift apart
##   Part C  test framework, with an explicit class per assertion
##   Part D  domain assertions
##   Part E  design-space sensitivity engine
##
## v02 changes over v01
##   - every gate is now a named function in Part B. S14 calls them; the tests
##     call the same objects. v01 had the rule written twice.
##   - assertions carry a class: UNIT (logic that must always hold) vs
##     DATA_QC (properties of this SIKU01 dataset) vs REGRESSION (a frozen
##     count) vs SENSITIVITY. Only UNIT failures are defects; a DATA_QC or
##     REGRESSION failure may simply mean the data legitimately changed.
##   - the bio3d orientation test is deterministic. The random alignment is
##     gone; a named artificial stress case replaces it.
##   - expect_unique / expect_no_na / expect_same_rows added, for join integrity
##   - in stop mode the partial report is flushed to disk BEFORE stopping, so a
##     failed run still leaves a readable trace
##
## v04 changes over v03
##   - THE TOP BANNER now carries POS_WEIGHT and NEG_WEIGHT, and every scored
##     criterion goes through one score_criterion(). v03 spread nine weights
##     across nine expressions, which is how three of them drifted from the
##     specification unnoticed.
##   - every weight is +1 / -1. The deposited 0 to +-3 weights were
##     author-selected with no calibration, and under them five of nineteen
##     components could not change retention at any data: a +1 could never
##     break a tie against components moving in steps of 2 or 3.
##   - a retention threshold is "at least N of M criteria met", not a score
##     cut. retained_at_n() is the only comparison.
##   - molecular weight is scored once, at M1 general; host codon adaptation is
##     the M1 pDNA gate and is not scored again at M2.
##   - the spine is [pangenome_id]. The gate functions are unchanged predicates;
##     what changed is the grain they are applied at and the weights above.
##   - score_silica_z(), score_mw_protein(), score_cai_pdna() and
##     score_cai_m2_pdna() are RETIRED, not rewritten: the silica tiers and the
##     two duplicated codon-adaptation scores no longer exist as scored terms.
##     They stay in v03 for provenance.
##
## NOT IN SCOPE: S03 and S13 are Python. Their assertions belong in those
## files. An R helper cannot honestly police them.
## ============================================================================

.io_have <- function(pkg) requireNamespace(pkg, quietly = TRUE)

## ============================================================================
## PART A — versioned, non-clobbering, atomic output
## ============================================================================
.io_esc <- function(s) {
  # R's default TRE engine rejects { and } inside a character class
  # ("Invalid contents of {}"), so escape each metacharacter explicitly
  # rather than relying on a class. This runs on every vwrite().
  for (ch in c("\\\\", ".", "|", "(", ")", "[", "]", "{", "}", "^", "$", "*", "+", "?"))
    s <- gsub(ch, paste0("\\\\", ch), s, fixed = TRUE)
  s
}
.io_hash_file <- function(p) {
  # braces are required: at top level R terminates the if-expression at the
  # newline and then sees an orphaned `else`
  if (.io_have("digest")) digest::digest(file = p, algo = "sha256")
  else paste0("md5:", unname(tools::md5sum(p)))
}

vversions <- function(stem, ext = "tsv", dir = ".") {
  pat <- sprintf("^%s_v([0-9]+)\\.%s$", .io_esc(stem), .io_esc(ext))
  f <- list.files(dir, pattern = pat)
  if (!length(f)) return(data.frame(version = integer(0), file = character(0),
                                    path = character(0), stringsAsFactors = FALSE))
  v <- as.integer(sub(pat, "\\1", f)); o <- order(v)
  data.frame(version = v[o], file = f[o], path = file.path(dir, f[o]),
             stringsAsFactors = FALSE)
}

vlatest <- function(stem, ext = "tsv", dir = ".", must_exist = TRUE) {
  vs <- vversions(stem, ext, dir)
  if (!nrow(vs)) { if (must_exist) stop("no versions of '", stem, ".", ext, "' in ",
                    normalizePath(dir, mustWork = FALSE)); return(NA_character_) }
  p <- vs$path[nrow(vs)]
  message(sprintf("  reading    %s   (v%02d of %d)", basename(p), vs$version[nrow(vs)], nrow(vs)))
  p
}

vpath <- function(stem, ext = "tsv", dir = ".", width = 2) {
  vs <- vversions(stem, ext, dir)
  nxt <- if (nrow(vs)) max(vs$version) + 1L else 1L
  file.path(dir, sprintf(paste0("%s_v%0", width, "d.%s"), stem, nxt, ext))
}

.io_audit <- function(dir, stem, ext, path, status, nrows, hash, note) {
  f <- file.path(dir, "_audit_runs.tsv"); new <- !file.exists(f)
  scr <- tryCatch(basename(sub("^--file=", "",
    grep("^--file=", commandArgs(), value = TRUE)[1])), error = function(e) NA_character_)
  row <- data.frame(timestamp = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"), script = scr,
    stem = stem, ext = ext, file = if (is.na(path)) NA_character_ else basename(path),
    status = status, nrows = nrows, sha256 = hash, note = note, stringsAsFactors = FALSE)
  write.table(row, f, sep = "\t", row.names = FALSE, quote = FALSE,
              col.names = new, append = !new)
  invisible(row)
}

.io_default_writer <- function(ext) switch(ext,
  tsv = function(x, p) if (.io_have("data.table")) data.table::fwrite(x, p, sep = "\t", quote = FALSE)
                       else write.table(x, p, sep = "\t", row.names = FALSE, quote = FALSE),
  csv = function(x, p) if (.io_have("data.table")) data.table::fwrite(x, p) else write.csv(x, p, row.names = FALSE),
  rds = function(x, p) saveRDS(x, p),
  txt = function(x, p) writeLines(as.character(x), p),
  stop("no default writer for '", ext, "'"))

vwrite <- function(x, stem, ext = "tsv", dir = ".", writer = NULL,
                   note = "", dedup = TRUE, quiet = FALSE) {
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  writer <- if (is.null(writer)) .io_default_writer(ext) else writer
  tmp <- tempfile(pattern = paste0(".", stem, "_"), tmpdir = dir, fileext = paste0(".", ext))
  on.exit(if (file.exists(tmp)) unlink(tmp), add = TRUE)
  writer(x, tmp)
  if (!file.exists(tmp)) stop("writer produced no file for '", stem, "'")
  h <- .io_hash_file(tmp)
  n <- tryCatch(nrow(x), error = function(e) NA_integer_)
  if (is.null(n)) n <- tryCatch(length(x), error = function(e) NA_integer_)
  vs <- vversions(stem, ext, dir)
  if (dedup && nrow(vs) && identical(.io_hash_file(vs$path[nrow(vs)]), h)) {
    unlink(tmp)
    if (!quiet) message(sprintf("  unchanged  %s   (%s rows)", basename(vs$path[nrow(vs)]),
                                format(n, big.mark = ",")))
    .io_audit(dir, stem, ext, vs$path[nrow(vs)], "unchanged", n, h, note)
    return(invisible(vs$path[nrow(vs)]))
  }
  target <- vpath(stem, ext, dir)
  if (!file.rename(tmp, target)) { file.copy(tmp, target, overwrite = FALSE); unlink(tmp) }
  if (!quiet) message(sprintf("  wrote      %s   (%s rows)%s", basename(target),
    format(n, big.mark = ","),
    if (nrow(vs)) sprintf("  [changed vs v%02d]", max(vs$version)) else "  [new]"))
  .io_audit(dir, stem, ext, target, if (nrow(vs)) "changed" else "new", n, h, note)
  invisible(target)
}

vggsave <- function(plot, stem, ext = "png", dir = ".", ...) {
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  p <- vpath(stem, ext, dir); ggplot2::ggsave(p, plot, ...)
  .io_audit(dir, stem, ext, p, "new", NA_integer_, .io_hash_file(p), "figure")
  invisible(p)
}

## ============================================================================
## PART B — THE RULES. Defined once. The pipeline and the tests both use these.
##
## Every expert-selected threshold in the QbD funnel lives here as a default
## argument. Nothing downstream should hard-code a number, and no test should
## re-implement a rule. This is what stops the tests and the implementation
## from drifting, and it is also what makes the sensitivity sweeps in Part E
## possible without duplicating the pipeline.
## ============================================================================

## ---------------------------------------------------------------------------
## CANONICAL QbD SPECIFICATION
##
## This object is the single source of truth for every expert-selected number
## in the workflow. It is consumed by:
##
##     siku01_helpers_and_tests_v04.R   (this file: rule functions below)
##            v
##     S14a_QbD_Ranking_v06_SIKU01.R    (production pipeline; CLI defaults)
##            v
##     test_implementation_boundaries_*.R  (boundary tests)
##            v
##     run_design_space_sensitivity_*.R    (sweep nominals)
##
## The dependency runs one way only. S14a consumes these values; it must never
## define them independently, and this file must never read them back from
## S14a. Anything that needs a canonical number takes it from here.
##
## Values must agree with Table 2 of the manuscript. Where the two ever
## disagree, this object is the specification and Table 2 is the description
## of it that needs correcting.
##
## v03 change log
##   M1_PROTEIN_THRESHOLD  6L -> 3L    matched to the pipeline
##   M1_PDNA_THRESHOLD     4L -> 3L    matched to the pipeline
##   route-specific weights added: the protein route scores MW and GRAVY at +1,
##     the pDNA route scores host CAI at +1/-1, and neither had a callable
##     function, so both were computed inline in S14a and untested
##   M2_ADD_THRESHOLD renamed M2_THRESHOLD
## ---------------------------------------------------------------------------

QBD <- list(

  ## --- THE TOP BANNER: scoring weights, tunable ----------------------------
  ## Every scored criterion is worth POS_WEIGHT when satisfied. A criterion
  ## carrying a penalty condition is worth NEG_WEIGHT when that condition is
  ## met, and 0 in between. A criterion with no penalty condition is worth 0
  ## when unsatisfied.
  ##
  ## The penalty floor is -1 and NEG_WEIGHT_FLOOR asserts it for a reference
  ## run. The deposited -2 and -3 penalties are not reinstated: a single unmet
  ## manufacturability convention should not outweigh a satisfied one, and the
  ## deposited weights were author-selected with no calibration behind them.
  ##
  ## A sweep may move both, and further than a reference run may: SWEEP_WEIGHT
  ## is the declared perturbation range and reaches +-3, which is the widest
  ## weighting the deposited scheme ever used.
  POS_WEIGHT           =  1L,
  NEG_WEIGHT           = -1L,
  NEG_WEIGHT_FLOOR     = -1L,               # a reference run may not go below
  SWEEP_WEIGHT         = c(-3, -2, -1, 0, 1, 2, 3),

  ## Which scored criteria carry a penalty condition. These are the three
  ## properties the deposited scheme penalised; every other criterion is
  ## satisfied or simply unmet.
  PENALTY_CRITERIA     = c("M2_CAI", "M2_INSTABILITY", "M2_GC3"),

  ## --- M0, the reference gene model ----------------------------------------
  ## FULL_LENGTH_MIN is a ratio: the reference annotated length over the panel
  ## majority annotated length. The bound is >= rather than == because the
  ## criterion exists to exclude a TRUNCATED reference call, and an annotation
  ## longer than the majority is not truncated.
  FULL_LENGTH_MIN      = 1.00,

  ## --- Pre-M1 --------------------------------------------------------------
  ## carriage is a PROPORTION on 0-1 despite the _n suffix it carries in the
  ## descriptor tables. On 90 genomes 0.99 is 89.1, so the operative rule is
  ## 90 of 90.
  CARRIAGE_MIN         = 0.99,

  ## --- M1 mandatory gates ---------------------------------------------------
  ## The two anchor-integrity gates are ordered BEFORE the conservation gate:
  ## they decide whether its median is taken over columns every member carries.
  PROTEIN_FORM_REQUIRED = "single",          # one annotated protein form panel-wide
  SPAN_OCCUPANCY_MIN    = 1.00,              # every member occupies every anchor column
  HNORM_THRESHOLD      = 0.98,               # strict `>`
  LEN_MIN              = 100,                # aa, inclusive
  LEN_MAX              = 700,                # aa, EXCLUSIVE -> 100-699
  TMH_MAX              = 2L,                 # independent SignalP-reconciled

  ## --- M1 general evidence count -------------------------------------------
  ## Three criteria, +1 each, retained at N of 3. N = 1 because the three fire
  ## at very different rates: at N = 2 the count becomes a near-conjunction and
  ## discards 96.9% of the set reaching it on two evidence layers the framework
  ## itself calls supportive-only.
  MW_SCORE             = c(20000, 60000),    # Da, inclusive both ends
  M1_GENERAL_N         = 1L,
  M1_GENERAL_M         = 3L,

  ## --- M1 protein route -----------------------------------------------------
  ## Molecular weight is counted ONCE, at M1 general. The deposited scheme
  ## scored the same band again here, so one property earned two points.
  M1_PROTEIN_N         = 2L,
  M1_PROTEIN_M         = 3L,
  GRAVY_SCORE          = c(-0.5, 0.5),
  INSTABILITY_MAX      = 40,                 # Guruprasad 1990

  ## --- M1 pDNA routes -------------------------------------------------------
  ## Host codon adaptation was the route's only scored criterion once the
  ## uniform rule applied, so it is a mandatory GATE rather than a
  ## one-criterion score. A one-criterion score with a threshold of one is a
  ## gate wearing a score's clothes.
  M1_PDNA_IS_GATE      = TRUE,

  ## --- empirical quantiles, all derived from Pre-M1 -------------------------
  CAI_HI_Q             = 0.75,
  CAI_LO_Q             = 0.25,
  GC3_HI_Q             = 0.75,
  GC3_LO_Q             = 0.25,
  LEN_Q                = 0.50,

  ## --- M2, all routes -------------------------------------------------------
  ## FILTER_MODE stays additive: a failed gate determines eligibility for the
  ## route without removing the candidate from the dataset, so every rule is
  ## evaluated for every candidate and the audit is complete rather than
  ## truncated at the first failure.
  FILTER_MODE          = "additive",
  BASE_MW              = c(20000, 100000),
  BASE_GRAVY           = c(-1.5, 1.5),
  BASE_PI              = c(2, 12),

  ## --- M2 pDNA --------------------------------------------------------------
  ## Host codon adaptation is NOT among these three. It is the M1 pDNA gate, so
  ## every candidate reaching M2 on a pDNA route already satisfies it; scored
  ## again it fired for every candidate on the route and discriminated nothing.
  M2_PDNA_N            = 2L,
  M2_PDNA_M            = 3L,

  ## --- M2 protein routes ----------------------------------------------------
  ## Silica is a pure gate. The deposited charge tiers, the previous z > -15 implementation is superseded. The current M2.6 criterion retains strongly negative cargo with z <= -15 at pH 7.0.
  ## Silica capture is tag-mediated (Si-tag, SB7, Car9, R5, (RH)4), so the
  ## antigen's own isoelectric point does not determine binding: a His6-tagged
  ## protein at pI 6.2 and net charge -6.5 binds bare silica while its untagged
  ## counterpart of the same mass and pI does not. The window is therefore kept
  ## full-range and inert rather than removed, so passes_silica and its tests are
  ## unchanged; the only antigen-level criterion is the strongly-negative cargo threshold.
  SILICA_PI_PREF = c(0, 14),
  SILICA_Z_MAX   = -15,
  AEX_PI_MAX = 6.0, AEX_Z_MAX = 0,
  CEX_PI_MIN = 8.0, CEX_Z_MIN = 0,
  CELL_LEN_MAX   = 400,                      # aa, EXCLUSIVE

  ## --- operating ranges -----------------------------------------------------
  ## The charge columns computed on the panel. pH 7.0 is the screening
  ## reference; the other two are the operating-condition projection.
  CHARGE_PH      = c(6.8, 7.0, 7.4),
  CHARGE_PH_REF  = 7.0
)

## The reference run may not carry a penalty below the declared floor. A sweep
## may, which is why this asserts QBD and not the run values.
stopifnot(QBD$NEG_WEIGHT >= QBD$NEG_WEIGHT_FLOOR,
          QBD$POS_WEIGHT == 1L,
          QBD$M1_GENERAL_N <= QBD$M1_GENERAL_M,
          QBD$M1_PROTEIN_N <= QBD$M1_PROTEIN_M,
          QBD$M2_PDNA_N    <= QBD$M2_PDNA_M)

## ---------------------------------------------------------------------------
## Scoring under the uniform rule.
##
## score_criterion() is the only place a weight is applied. Every scored
## criterion goes through it, so a weight cannot drift between one criterion
## and another, and a sweep changes one argument rather than nine expressions.
## ---------------------------------------------------------------------------
score_criterion <- function(satisfied, penalised = NULL,
                            pos = QBD$POS_WEIGHT, neg = QBD$NEG_WEIGHT) {
  s <- !is.na(satisfied) & satisfied
  out <- ifelse(s, pos, 0L)
  if (!is.null(penalised)) {
    p <- !is.na(penalised) & penalised & !s
    out <- ifelse(p, neg, out)
  }
  as.integer(out)
}

## "at least N of M criteria met" on a signed sum. Named this way in the
## manuscript too: calling a count of satisfied criteria a score invites the
## reader to think the components were weighted by importance, and they were not.
retained_at_n <- function(score, n) !is.na(score) & score >= n

## --- mandatory gates --------------------------------------------------------
## The gate sheet's canonical name is passes_conservation(). The _gate suffix
## form is the historical name S14a and the integration test call, so both
## resolve to one predicate rather than to two that can drift apart.
passes_conservation <- function(median_hnorm, threshold = QBD$HNORM_THRESHOLD)
  !is.na(median_hnorm) & median_hnorm > threshold

passes_conservation_gate <- passes_conservation

passes_length_gate <- function(len_aa, lo = QBD$LEN_MIN, hi = QBD$LEN_MAX)
  !is.na(len_aa) & len_aa >= lo & len_aa < hi

passes_base_phys <- function(mw, gravy, pI, mw_r = QBD$BASE_MW,
                             gravy_r = QBD$BASE_GRAVY, pi_r = QBD$BASE_PI)
  !is.na(mw) & mw >= mw_r[1] & mw <= mw_r[2] &
  !is.na(gravy) & gravy >= gravy_r[1] & gravy <= gravy_r[2] &
  !is.na(pI) & pI >= pi_r[1] & pI <= pi_r[2]

## --- RETIRED scoring functions ----------------------------------------------
## The deposited per-criterion weight functions are retired, not rewritten.
## Every scored criterion now goes through score_criterion() in the top banner,
## so a weight cannot drift between one criterion and another. These stubs exist
## so a stale caller fails loudly instead of silently reading a NULL weight out
## of QBD and scoring every candidate 0. v03 holds the originals for provenance.
.retired <- function(what, instead)
  function(...) stop(what, " is retired in v04; use ", instead, call. = FALSE)

score_mw            <- .retired("score_mw()",            "score_criterion(in_range(mw, QBD$MW_SCORE))")
score_epitope       <- .retired("score_epitope()",       "score_criterion(epitope_positive)")
score_pubmed        <- .retired("score_pubmed()",        "score_criterion(pmid_count >= 1)")
m1_general_score    <- .retired("m1_general_score()",    "sum of score_criterion() over the three general criteria")
score_mw_protein    <- .retired("score_mw_protein()",    "nothing: molecular weight is counted once, at M1 general")
score_gravy_protein <- .retired("score_gravy_protein()", "score_criterion(in_range(gravy, QBD$GRAVY_SCORE))")
score_instability   <- .retired("score_instability()",   "score_criterion(ii <= QBD$INSTABILITY_MAX, ii > QBD$INSTABILITY_MAX)")
score_cai_protein   <- .retired("score_cai_protein()",   "score_criterion(cai >= hi, cai <= lo)")
score_cai_pdna      <- .retired("score_cai_pdna()",      "passes_host_cai(): the pDNA route gates, it does not score")
score_gc3           <- .retired("score_gc3()",           "score_criterion(gc3 >= hi, gc3 <= lo)")
score_cai_m2_pdna   <- .retired("score_cai_m2_pdna()",   "nothing: host codon adaptation is the M1 pDNA gate")
score_silica_z      <- .retired("score_silica_z()",      "passes_silica(): silica is a pure gate")
score_cai           <- score_cai_protein
score_gravy         <- score_gravy_protein

## --- the gate predicates the pangenome_id spine adds ------------------------
## in_range() is the one numeric-window predicate. It exists so a window is
## written once and the MASTER numeric-range gate and the pipeline cannot
## disagree about whether a bound is inclusive.
in_range <- function(x, r, hi_exclusive = FALSE)
  !is.na(x) & x >= r[1] & (if (hi_exclusive) x < r[2] else x <= r[2])

## M0. CDS and protein pair coherence. Lifted VERBATIM from the TST_gene_model unit test,
## which defined it locally: two definitions of one rule is exactly the drift
## Part B exists to prevent, and the TST_gene_model robustness test refuses to run until the
## rule lives here. Genetic code 11; alternative initiation codons come from
## Biostrings rather than from a hand-written list.
.orf_pair_scalar <- function(nt, aa) {

  # Scalar pair only.
  if (length(nt) != 1L || length(aa) != 1L ||
      is.na(nt) || is.na(aa)) {
    return(FALSE)
  }

  # Harmless normalization only: case + surrounding whitespace.
  # Internal whitespace is intentionally NOT removed.
  nt <- toupper(trimws(nt))
  aa <- toupper(trimws(aa))

  if (nt == "" || aa == "") {
    return(FALSE)
  }

  # CDS must consist of complete codons.
  if (nchar(nt) %% 3L != 0L) {
    return(FALSE)
  }

  genetic_code <- Biostrings::getGeneticCode("11")

  valid_starts <- unique(c(
    "ATG",
    attr(genetic_code, "alt_init_codons")
  ))

  valid_stops <- names(genetic_code)[genetic_code == "*"]

  start_codon <- substr(nt, 1L, 3L)
  stop_codon  <- substr(nt, nchar(nt) - 2L, nchar(nt))

  if (!(start_codon %in% valid_starts)) {
    return(FALSE)
  }

  if (!(stop_codon %in% valid_stops)) {
    return(FALSE)
  }

  # Protein FASTA may retain or omit the terminal stop symbol.
  aa_no_stop <- sub("\\*$", "", aa)

  if (aa_no_stop == "" || substr(aa_no_stop, 1L, 1L) != "M") {
    return(FALSE)
  }

  # Parse + translate with Biostrings. Malformed DNA or a fuzzy codon whose
  # translation is genuinely ambiguous must fail the gate rather than crash it.
  translated <- tryCatch(
    {
      dna <- Biostrings::DNAString(nt)

      as.character(
        Biostrings::translate(
          dna,
          genetic.code = genetic_code,
          no.init.codon = FALSE,
          if.fuzzy.codon = "error.if.X"
        )
      )
    },
    error = function(e) NA_character_
  )

  if (is.na(translated)) {
    return(FALSE)
  }

  # We explicitly require the translated CDS itself to terminate with a stop.
  if (!endsWith(translated, "*")) {
    return(FALSE)
  }

  translated_no_stop <- sub("\\*$", "", translated)

  # Any remaining '*' is an internal in-frame stop.
  if (grepl("*", translated_no_stop, fixed = TRUE)) {
    return(FALSE)
  }

  # Final biological assertion for TST_gene_model: nucleotide and protein agree.
  identical(translated_no_stop, aa_no_stop)
}


## The decision above is per pair and scalar, exactly as deposited. The gate the
## pipeline and the robustness contract call is vectorised over it: zero-length
## in gives zero-length out, the result is the same length as the input, and a
## missing value gives FALSE rather than NA. An NA inside dplyr::filter() drops
## the row silently, so a gate that propagates NA removes candidates without
## leaving a trace. No per-pair decision changed.
## `aa` defaults to absent so the gate is callable with one argument, which is
## the shape the generic robustness contract tests every gate in. A coding
## sequence with no translation cannot satisfy pair coherence, so an absent
## translation is FALSE rather than an error.
passes_orf_pair <- function(nt, aa) {
  if (missing(aa)) aa <- rep(NA_character_, length(nt))
  n <- max(length(nt), length(aa))
  if (length(nt) == 0L || length(aa) == 0L) return(logical(0))
  nt <- rep_len(nt, n); aa <- rep_len(aa, n)
  vapply(seq_len(n), function(i) isTRUE(.orf_pair_scalar(nt[[i]], aa[[i]])), logical(1))
}

## M0. The reference annotated length over the panel majority annotated length.
## Not against the anchor: the anchor is selected as the longest member and is
## the reference isolate in most families, so an anchor denominator would make
## every ratio 1.00 by construction.
passes_full_length <- function(ratio, min_ratio = QBD$FULL_LENGTH_MIN)
  !is.na(ratio) & ratio >= min_ratio

## Pre-M1. carriage is a proportion on 0-1 despite its _n suffix.
passes_core_genome <- function(carriage, min_carriage = QBD$CARRIAGE_MIN)
  !is.na(carriage) & carriage >= min_carriage

## M1. Its own gate: an expression and solubility criterion, not an
## immunological one, and applied to the recombinant-protein routes only because
## multiple helices are not exclusionary for a plasmid DNA route.
passes_tmh <- function(tmh_count, max_tmh = QBD$TMH_MAX)
  !is.na(tmh_count) & tmh_count <= max_tmh

## M1 pDNA. A gate, not a score.
passes_host_cai <- function(cai, hi) !is.na(cai) & cai >= hi

## M2 silica. One gate replacing four deposited terms.
passes_silica <- function(pI, z, pi_r = QBD$SILICA_PI_PREF, z_max = QBD$SILICA_Z_MAX)
  in_range(pI, pi_r) & !is.na(z) & z <= z_max

## --- pDNA: the four mandatory gates ----------------------------------------
pdna_gates <- function(cai, gc3, len_nt, iis, cai_hi, gc3_hi, len_max) list(
  pass_cai  = !is.na(cai)    & cai    >= cai_hi,
  pass_gc3  = !is.na(gc3)    & gc3    >= gc3_hi,
  pass_len  = !is.na(len_nt) & len_nt <= len_max,
  pass_iis0 = !is.na(iis)    & iis    == 0L)
pdna_final_pass <- function(g) g$pass_cai & g$pass_gc3 & g$pass_len & g$pass_iis0

## --- M2 protein routes ------------------------------------------------------
score_silica_z <- function(z, excl = QBD$SILICA_Z_EXCL, lo = QBD$SILICA_Z_LO, hi = QBD$SILICA_Z_HI)
  ifelse(is.na(z), NA_integer_, ifelse(z <= excl, -999L, ifelse(z <= lo, -1L, ifelse(z <= hi, 2L, 3L))))
passes_cellulose <- function(len_aa, cap = QBD$CELL_LEN_MAX) !is.na(len_aa) & len_aa < cap
passes_aex <- function(pI, z, pi_max = QBD$AEX_PI_MAX, z_max = QBD$AEX_Z_MAX)
  !is.na(pI) & pI <= pi_max & !is.na(z) & z <= z_max
passes_cex <- function(pI, z, pi_min = QBD$CEX_PI_MIN, z_min = QBD$CEX_Z_MIN)
  !is.na(pI) & pI >= pi_min & !is.na(z) & z >= z_min

## ============================================================================
## PART C — test framework
## ============================================================================
.TEST_MODE <- Sys.getenv("SIKU01_TEST_MODE", "warn")   # stop | warn | off
.TESTS <- new.env(parent = emptyenv())
.TESTS$rows <- list(); .TESTS$current <- NA_character_
.TESTS$class <- "UNIT"; .TESTS$dir <- "."; .TESTS$stem <- "unit_tests"

.record <- function(assertion, ok, detail) {
  .TESTS$rows[[length(.TESTS$rows) + 1L]] <- data.frame(
    step = .TESTS$current, class = .TESTS$class, assertion = assertion,
    result = if (ok) "PASS" else "FAIL", detail = detail, stringsAsFactors = FALSE)
  if (!ok) {
    msg <- sprintf("[%s / %s] %s -- %s", .TESTS$current, .TESTS$class, assertion, detail)
    if (identical(.TEST_MODE, "stop")) {
      ## flush the partial report BEFORE stopping, so a failed run still leaves
      ## a readable trace on disk rather than nothing
      try(test_report(.TESTS$dir, paste0(.TESTS$stem, "_PARTIAL"), note = "aborted"), silent = TRUE)
      stop(msg, call. = FALSE)
    }
    if (identical(.TEST_MODE, "warn")) warning(msg, call. = FALSE)
  }
  invisible(ok)
}

## class: UNIT       logic that must always hold, regardless of the data
##        DATA_QC    a property this SIKU01 dataset should have
##        REGRESSION a frozen count; may legitimately change after a re-run
##        SENSITIVITY a design-space sweep, reported not asserted
test_step <- function(name, expr, class = "UNIT") {
  if (identical(.TEST_MODE, "off")) return(invisible(NULL))
  pn <- .TESTS$current; pc <- .TESTS$class
  .TESTS$current <- name; .TESTS$class <- class
  on.exit({ .TESTS$current <- pn; .TESTS$class <- pc }, add = TRUE)
  message("  [", class, "] ", name)
  force(expr); invisible(NULL)
}

test_init <- function(dir, stem) { .TESTS$dir <- dir; .TESTS$stem <- stem }

expect_true <- function(cond, what) {
  ok <- length(cond) > 0 && !any(is.na(cond)) && all(cond)
  .record(what, ok, if (ok) "" else paste0("false or NA on ", sum(!cond | is.na(cond)), " element(s)"))
}
expect_false <- function(cond, what) expect_true(!cond, what)
expect_equal <- function(a, b, what, tol = 1e-8) {
  ok <- length(a) == length(b) && isTRUE(all(abs(as.numeric(a) - as.numeric(b)) <= tol))
  .record(what, ok, if (ok) "" else paste0("got ", paste(a, collapse = ","),
                                           " expected ", paste(b, collapse = ",")))
}
expect_identical <- function(a, b, what) .record(what, identical(a, b),
  if (identical(a, b)) "" else "objects differ")
expect_gt <- function(a, b, what) .record(what, isTRUE(all(a > b)),
  if (isTRUE(all(a > b))) "" else paste0(a, " !> ", b))
expect_rows <- function(df, min_n, what) { n <- nrow(df)
  .record(what, !is.null(n) && n >= min_n, paste0("n=", n)) }
expect_cols <- function(df, cols, what) { miss <- setdiff(cols, names(df))
  .record(what, !length(miss), if (!length(miss)) "" else paste0("missing: ", paste(miss, collapse = ", "))) }
expect_range <- function(x, lo, hi, what, allow_na = TRUE) {
  v <- if (allow_na) x[!is.na(x)] else x
  ok <- length(v) > 0 && all(v >= lo & v <= hi)
  .record(what, ok, if (ok) sprintf("[%.4g, %.4g]", min(v), max(v))
          else sprintf("outside [%g, %g]: min=%.4g max=%.4g", lo, hi, min(v), max(v)))
}
## join integrity ------------------------------------------------------------
expect_unique <- function(x, what) {
  dup <- unique(x[duplicated(x) & !is.na(x)]); ok <- !length(dup)
  .record(what, ok, if (ok) paste0(length(x), " unique records")
          else paste0(length(dup), " duplicated, e.g. ", paste(utils::head(dup, 5), collapse = ", ")))
}
expect_no_na <- function(x, what) { n <- sum(is.na(x))
  .record(what, n == 0, if (n == 0) "" else paste0(n, " NA values")) }
expect_same_rows <- function(n_before, after, what) {
  n <- if (is.numeric(n_before)) n_before else nrow(n_before)
  .record(what, nrow(after) == n, paste0(n, " -> ", nrow(after)))
}
expect_subset <- function(child, parent, what) {
  extra <- setdiff(child, parent); ok <- !length(extra)
  .record(what, ok, if (ok) paste0(length(child), " of ", length(parent))
          else paste0(length(extra), " ids not in parent, e.g. ", paste(utils::head(extra, 3), collapse = ", ")))
}
expect_intersection <- function(final, components, what) {
  expected <- Reduce(`&`, components); ok <- identical(as.logical(final), as.logical(expected))
  .record(what, ok, if (ok) paste0(sum(expected), " pass")
          else paste0("mismatch on ", sum(as.logical(final) != expected), " rows"))
}
## score arithmetic: the reported total must equal the sum of its parts -------
expect_score_arithmetic <- function(total, components, what) {
  expected <- Reduce(`+`, components)
  bad <- which(as.numeric(total) != as.numeric(expected))
  .record(what, !length(bad), if (!length(bad)) paste0(length(total), " rows reconcile")
          else paste0(length(bad), " rows disagree, first at index ", bad[1]))
}
expect_funnel <- function(counts, what) {
  ok <- all(diff(as.numeric(counts)) <= 0)
  .record(what, ok, paste0(paste(counts, collapse = " -> "), if (ok) "" else "  NOT non-increasing"))
}

## ============================================================================
## PART D — bio3d semantics, deterministic
## ============================================================================
.AA20 <- c("A","R","N","D","C","Q","E","G","H","I","L","K","M","F","P","S","T","W","Y","V")

## build a deterministic alignment: n rows, len columns, the first
## round(frac*len) columns cycle through distinct residues, the rest invariant
.det_aln <- function(frac_variable, n = 90, len = 200) {
  m <- matrix("A", nrow = n, ncol = len)
  nvar <- round(frac_variable * len)
  if (nvar > 0) for (j in seq_len(nvar)) m[, j] <- rep_len(.AA20, n)
  m
}

## FIRST: does bio3d normalise by a FIXED constant (log2(22)) or by the maximum
## entropy observed WITHIN each alignment? The answer decides whether H.norm is
## comparable across alignments at all, and it has never been checked here.
expect_hnorm_normalization_constant <- function() {
  if (!.io_have("bio3d")) return(.record("bio3d installed", FALSE, "package missing"))
  n <- 90
  ## same probe column (half A, half C) embedded in two very different contexts
  probe <- c(rep("A", n / 2), rep("C", n / 2))
  quiet <- cbind(matrix("A", n, 50), probe)                 # otherwise invariant
  noisy <- cbind(matrix(rep_len(.AA20, n * 50), n, 50), probe)  # otherwise diverse
  hq <- bio3d::entropy(quiet)$H.norm[51]
  hn <- bio3d::entropy(noisy)$H.norm[51]
  fixed <- abs(hq - hn) < 1e-8
  .record("H.norm normalisation is context-independent (fixed denominator)", fixed,
          sprintf("same column scores %.6f in a quiet alignment and %.6f in a noisy one%s",
                  hq, hn, if (fixed) "" else
                  " -- normalisation is ALIGNMENT-RELATIVE; H.norm is NOT comparable across orthogroups"))
  invisible(fixed)
}

## A. fully invariant
## B. realistic sparse variation, which must still PASS -- this is the point
## C. an artificial majority-variable stress case, named so it is never
##    mistaken for a model of S. iniae evolution
## D. the exact gate boundary
expect_conservation_orientation <- function() {
  if (!.io_have("bio3d")) return(.record("bio3d installed", FALSE, "package missing"))
  ei <- bio3d::entropy(.det_aln(0))
  expect_range(ei$H.norm, 0.999, 1, "A: invariant alignment scores H.norm = 1")
  expect_range(ei$H, 0, 1e-8,       "A: invariant alignment scores raw H = 0")

  for (f in c(0.01, 0.025, 0.05, 0.075)) {
    m <- median(bio3d::entropy(.det_aln(f))$H.norm)
    .record(sprintf("B: %.1f%% variable columns still passes the gate", f * 100),
            passes_conservation_gate(m), sprintf("median H.norm = %.4f", m))
  }
  mstress <- median(bio3d::entropy(.det_aln(0.90))$H.norm)
  .record("C: artificial_majority_variable_stress_test is rejected",
          !passes_conservation_gate(mstress),
          sprintf("median H.norm = %.4f (artificial; not a model of S. iniae)", mstress))

  e_all <- vapply(c(0, 0.25, 0.60, 1), function(f) mean(bio3d::entropy(.det_aln(f))$H), numeric(1))
  expect_true(all(diff(e_all) > 0), "raw H increases monotonically with diversity")
}

expect_gate_boundary <- function(thr = QBD$HNORM_THRESHOLD) {
  expect_identical(passes_conservation_gate(0.981, thr), TRUE,  "D: H.norm 0.981 passes")
  expect_identical(passes_conservation_gate(0.980, thr), FALSE, "D: H.norm 0.980 fails a strict > gate")
  expect_identical(passes_conservation_gate(0.979, thr), FALSE, "D: H.norm 0.979 fails")
  expect_identical(passes_conservation_gate(NA_real_, thr), FALSE, "D: NA fails")
}

## boundary tests for the other expert-selected gates
expect_length_boundary <- function() {
  expect_identical(passes_length_gate(99),  FALSE, "length 99 aa fails")
  expect_identical(passes_length_gate(100), TRUE,  "length 100 aa passes")
  expect_identical(passes_length_gate(699), TRUE,  "length 699 aa passes")
  expect_identical(passes_length_gate(700), FALSE, "length 700 aa fails (exclusive max)")
}
expect_cellulose_boundary <- function() {
  expect_identical(passes_cellulose(399), TRUE,  "cellulose 399 aa passes")
  expect_identical(passes_cellulose(400), FALSE, "cellulose 400 aa fails (exclusive cap)")
}
expect_score_component_boundaries <- function() {
  expect_equal(score_mw(19999), 0, "MW 19,999 Da scores 0"); expect_equal(score_mw(20000), 2, "MW 20 kDa scores +2")
  expect_equal(score_mw(60000), 2, "MW 60 kDa scores +2");   expect_equal(score_mw(60001), 0, "MW 60,001 Da scores 0")
  expect_equal(score_gravy(-0.5), 2, "GRAVY -0.5 scores +2"); expect_equal(score_gravy(0.51), 0, "GRAVY 0.51 scores 0")
  expect_equal(score_instability(40), 1, "instability 40 scores +1")
  expect_equal(score_instability(41), -2, "instability 41 scores -2")
  expect_equal(score_epitope(TRUE), 3, "IEDB evidence scores +3")
  expect_equal(score_pubmed(NA), 0, "absent PubMed scores 0")
  ## the combinations the >=2 general threshold implies
  expect_true(m1_general_score(NA, TRUE, NA) >= QBD$M1_GENERAL_THRESHOLD, "IEDB alone (+3) passes M1-general")
  expect_true(m1_general_score(30000, FALSE, NA) >= QBD$M1_GENERAL_THRESHOLD, "MW alone (+2) passes M1-general")
  expect_false(m1_general_score(NA, FALSE, "123") >= QBD$M1_GENERAL_THRESHOLD, "PubMed alone (+1) does not pass")
  expect_false(m1_general_score(NA, FALSE, NA) >= QBD$M1_GENERAL_THRESHOLD, "no evidence does not pass")
}

## ============================================================================
## PART E — design-space sensitivity
##
## A boundary test confirms the implementation. A sweep asks the question
## Reviewer 2 is actually asking: if this expert-selected value moves within a
## reasonable neighbourhood, does the shortlist change materially?
##
## select_fn(params) must return a character vector of retained ids.
## ============================================================================
jaccard <- function(a, b) { u <- length(union(a, b)); if (!u) return(NA_real_); length(intersect(a, b)) / u }

sweep_param <- function(param, values, select_fn, canonical_value,
                        parent_n = NA_integer_, label = NULL, stage = NA_character_) {
  can_ids <- select_fn(canonical_value)
  rows <- lapply(seq_along(values), function(i) {
    v <- values[[i]]
    ids <- select_fn(v)
    data.frame(parameter = param, stage = stage,
               value = if (length(v) > 1) paste(v, collapse = "-") else as.character(v),
               is_canonical = identical(v, canonical_value),
               n_retained = length(ids),
               pct_of_parent = if (is.na(parent_n)) NA_real_ else round(100 * length(ids) / parent_n, 2),
               pct_of_canonical = round(100 * length(ids) / max(1L, length(can_ids)), 1),
               jaccard_vs_canonical = round(jaccard(ids, can_ids), 4),
               n_added = length(setdiff(ids, can_ids)),
               n_lost  = length(setdiff(can_ids, ids)),
               stringsAsFactors = FALSE)
  })
  out <- do.call(rbind, rows)
  if (!is.null(label)) out$note <- label
  out
}

## compact verdict for the manuscript: how much does the shortlist move?
sweep_verdict <- function(sw, stable_jaccard = 0.80) {
  j <- sw$jaccard_vs_canonical[!sw$is_canonical]
  data.frame(parameter = sw$parameter[1], stage = sw$stage[1],
             n_settings = nrow(sw),
             n_canonical = sw$n_retained[sw$is_canonical][1],
             n_min = min(sw$n_retained), n_max = max(sw$n_retained),
             min_jaccard = round(min(j, na.rm = TRUE), 4),
             verdict = if (min(j, na.rm = TRUE) >= stable_jaccard) "stable" else "threshold-sensitive",
             stringsAsFactors = FALSE)
}

## ============================================================================
## report
## ============================================================================
test_report <- function(dir = ".", stem = "unit_tests", note = "") {
  if (identical(.TEST_MODE, "off") || !length(.TESTS$rows)) return(invisible(NULL))
  df <- do.call(rbind, .TESTS$rows)
  fails <- df[df$result == "FAIL", , drop = FALSE]
  message(sprintf("\n  %d assertions, %d steps, %d failed", nrow(df),
                  length(unique(df$step)), nrow(fails)))
  print(table(df$class, df$result))
  if (nrow(fails)) { message("\n  failures:"); for (i in seq_len(nrow(fails)))
    message(sprintf("   %-8s %-34s %s", fails$class[i], fails$step[i], fails$assertion[i])) }
  vwrite(df, stem, "tsv", dir, note = paste(note, "mode=", .TEST_MODE))
  unit_fail <- sum(df$result == "FAIL" & df$class == "UNIT")
  if (unit_fail && identical(.TEST_MODE, "stop"))
    stop(unit_fail, " UNIT test(s) failed; outputs are not trustworthy")
  invisible(df)
}

test_reset <- function() { .TESTS$rows <- list(); .TESTS$current <- NA_character_ }
