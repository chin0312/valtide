suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
})

source("config/model_config.R")
source("config/p1a_calibration_config.R")
source("R/utils.R")
source("R/load_cached_data.R")
source("R/model_spec.R")
source("R/state_space_models.R")
source("R/evaluation.R")
source("R/p1a_calibration.R")

config <- VALTIDE_CONFIG
cc <- P1A_C_CONFIG
out_dir <- Sys.getenv("VALTIDE_OUTPUT_DIR", unset = "outputs/p1a_c")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
asset_id <- Sys.getenv("VALTIDE_ASSET_ID", unset = "unknown")
cache_dir <- Sys.getenv("VALTIDE_CACHE_DIR", unset = "data/cache")
metadata_path <- file.path(cache_dir, "asset_metadata.json")
asset_metadata <- if (file.exists(metadata_path)) jsonlite::read_json(metadata_path, simplifyVector = TRUE) else list()
dataset_sha <- if (!is.null(asset_metadata$dataset_sha256)) as.character(asset_metadata$dataset_sha256) else "unknown"

if (!is.null(asset_metadata$asset_id) && nzchar(asset_id) && asset_id != "unknown" &&
    !identical(toupper(as.character(asset_metadata$asset_id)), toupper(asset_id))) {
  stop("VALTIDE_ASSET_ID does not match asset_metadata.json.", call. = FALSE)
}

message("P1a-C vs Raw-xStock-C asset: ", asset_id, " | dataset SHA256: ", dataset_sha)
message("Loading cached data only; no market-data APIs will be called.")

panel <- add_derived_features(load_cached_panel(cache_dir))
split <- split_cached_panel(panel, config)
train <- split$train
test <- split$test
full_spec <- make_model_spec(train, character(), character())

message(sprintf("Original split: %s", split$description))
message(sprintf("Train rows=%d | untouched test rows=%d", nrow(train), nrow(test)))
message("Sessions: ", paste(full_spec$sessions, collapse = ", "))

# =============================================================================
# Raw-xStock-C helpers
# =============================================================================
# Raw-xStock-C deliberately leaves the center estimate equal to the token price.
# Only the uncertainty interval is learned from historical token-vs-underlying
# residuals. This provides a strong baseline against P1a-C.

make_raw_replay <- function(dt) {
  out <- data.table::data.table(
    timestamp_utc = dt$timestamp_utc,
    session_state = as.character(dt$session_state),
    nvda_log_price = dt$nvda_log_price,
    nvdax_log_price = dt$nvdax_log_price,
    reference_hidden_mean = dt$nvdax_log_price,
    # These are placeholders for schema compatibility with interval_metrics().
    # Raw-C bounds are direct empirical log-error offsets, not q * model sigma.
    reference_hidden_P = NA_real_,
    reference_predictive_sd = NA_real_
  )
  out[, signed_score := nvda_log_price - nvdax_log_price]
  out[, abs_score := abs(signed_score)]
  out
}

fit_raw_calibrator <- function(scores, type, level, min_session_scores = 200L) {
  scores <- scores[is.finite(signed_score) & is.finite(abs_score)]
  if (!nrow(scores)) stop("No finite Raw-xStock calibration residuals.")

  raw_gaussian_halfwidth <- function(z, level) {
    z <- as.numeric(z[is.finite(z)])
    if (!length(z)) return(NA_real_)
    # The interval is constrained to be centered on the raw token price.
    # Under zero-mean Gaussian errors, the MLE scale around that fixed center
    # is RMS(error), not sd(error - mean(error)).
    sigma0 <- sqrt(mean(z^2))
    stats::qnorm((1 + level) / 2) * sigma0
  }

  global_asym <- empirical_tail_quantiles(scores$signed_score, level)
  global_sym <- finite_conformal_quantile(scores$abs_score, level)

  cal <- list(
    type = type,
    level = level,
    n = nrow(scores),
    global = list(
      sym = global_sym,
      lo = global_asym[["lo"]],
      hi = global_asym[["hi"]]
    ),
    sessions = list(),
    min_session_scores = min_session_scores,
    center = "raw_xstock_log_price",
    scale = "direct_log_error_offset"
  )

  if (type == "gaussian") {
    h <- raw_gaussian_halfwidth(scores$signed_score, level)
    cal$global$sym <- h
    cal$global$lo <- -h
    cal$global$hi <- h
  }

  if (startsWith(type, "session_")) {
    for (ss in unique(as.character(scores$session_state))) {
      x <- scores[session_state == ss]
      if (nrow(x) < min_session_scores) next
      asym <- empirical_tail_quantiles(x$signed_score, level)
      cal$sessions[[ss]] <- list(
        n = nrow(x),
        sym = finite_conformal_quantile(x$abs_score, level),
        lo = asym[["lo"]],
        hi = asym[["hi"]]
      )
    }
  }
  cal
}

raw_calibrator_bounds <- function(cal, session) {
  use <- cal$global
  source <- "global"

  if (startsWith(cal$type, "session_") && !is.null(cal$sessions[[session]])) {
    use <- cal$sessions[[session]]
    source <- paste0("session:", session)
  } else if (startsWith(cal$type, "session_")) {
    source <- "global_fallback"
  }

  if (cal$type %in% c("gaussian", "global_sym", "session_sym")) {
    c(lo = -use$sym, hi = use$sym, source = source)
  } else {
    c(lo = use$lo, hi = use$hi, source = source)
  }
}

apply_raw_calibrator <- function(replay, cal) {
  out <- data.table::copy(replay)
  lo_off <- hi_off <- rep(NA_real_, nrow(out))
  source <- rep(NA_character_, nrow(out))

  for (i in seq_len(nrow(out))) {
    b <- raw_calibrator_bounds(cal, as.character(out$session_state[[i]]))
    lo_off[[i]] <- as.numeric(b[["lo"]])
    hi_off[[i]] <- as.numeric(b[["hi"]])
    source[[i]] <- as.character(b[["source"]])
  }

  out[, `:=`(
    calibration_type = cal$type,
    calibration_level = cal$level,
    calibration_source = source,
    q_lower = lo_off,
    q_upper = hi_off,
    calibrated_log_lo = nvdax_log_price + lo_off,
    calibrated_log_hi = nvdax_log_price + hi_off,
    calibrated_price_mid = exp(nvdax_log_price),
    calibrated_price_lo = exp(nvdax_log_price + lo_off),
    calibrated_price_hi = exp(nvdax_log_price + hi_off)
  )]
  out
}

evaluate_raw_calibrator <- function(replay, cal, label = NULL) {
  scored <- apply_raw_calibrator(replay, cal)
  overall <- interval_metrics(scored, cal$level)
  overall[, `:=`(
    candidate = label %||% cal$type,
    level = cal$level,
    session_state = "ALL"
  )]

  by_session <- scored[, interval_metrics(.SD, cal$level), by = session_state]
  by_session[, `:=`(
    candidate = label %||% cal$type,
    level = cal$level
  )]

  list(scored = scored, metrics = data.table::rbindlist(list(overall, by_session), fill = TRUE))
}

raw_calibrator_to_jsonable <- function(cal) {
  list(
    type = cal$type,
    level = cal$level,
    n = cal$n,
    center = cal$center,
    scale = cal$scale,
    global = cal$global,
    sessions = cal$sessions,
    min_session_scores = cal$min_session_scores
  )
}

raw_pseudo_closure_stress <- function(test_dt, cal, durations_min = c(30L, 60L, 120L, 240L)) {
  rows <- list()
  n <- nrow(test_dt)

  for (dur in durations_min) {
    L <- as.integer(dur / 5L)
    if (L < 1L) next
    i <- 2L
    block_id <- 0L

    while (i + L - 1L <= n) {
      idx <- i:(i + L - 1L)
      ts <- test_dt$timestamp_utc[idx]
      contiguous <- all(diff(as.numeric(ts)) == 300)
      labels <- is.finite(test_dt$nvda_log_price[idx]) & is.finite(test_dt$nvdax_log_price[idx])

      if (contiguous && all(labels)) {
        block_id <- block_id + 1L
        replay <- make_raw_replay(test_dt[idx])
        scored <- apply_raw_calibrator(replay, cal)
        scored[, `:=`(
          duration_min = dur,
          block_id = block_id,
          step_in_block = seq_len(.N)
        )]
        rows[[length(rows) + 1L]] <- scored
        i <- i + L
      } else {
        i <- i + 1L
      }
    }
  }

  if (!length(rows)) {
    return(list(detail = data.table::data.table(), metrics = data.table::data.table()))
  }

  detail <- data.table::rbindlist(rows, fill = TRUE)
  metrics <- detail[, interval_metrics(.SD, cal$level), by = duration_min]
  list(detail = detail, metrics = metrics)
}

point_estimate_comparison <- function(p1a_replay, raw_replay) {
  x <- data.table::data.table(
    timestamp_utc = p1a_replay$timestamp_utc,
    session_state = as.character(p1a_replay$session_state),
    y = p1a_replay$nvda_log_price,
    p1a = p1a_replay$reference_hidden_mean,
    raw = raw_replay$nvdax_log_price
  )
  x <- x[is.finite(y) & is.finite(p1a) & is.finite(raw)]

  calc <- function(z) {
    ep <- z$p1a - z$y
    er <- z$raw - z$y
    ap <- abs(ep)
    ar <- abs(er)
    data.table::data.table(
      n = nrow(z),
      P1a_MAE_bps = 10000 * mean(ap),
      Raw_xStock_MAE_bps = 10000 * mean(ar),
      P1a_RMSE_bps = 10000 * sqrt(mean(ep^2)),
      Raw_xStock_RMSE_bps = 10000 * sqrt(mean(er^2)),
      P1a_bias_bps = 10000 * mean(ep),
      Raw_xStock_bias_bps = 10000 * mean(er),
      P1a_minus_Raw_MAE_bps = 10000 * (mean(ap) - mean(ar)),
      P1a_MAE_ratio_to_Raw = mean(ap) / mean(ar),
      P1a_win_rate_vs_Raw = mean(ap < ar),
      Raw_win_rate_vs_P1a = mean(ar < ap),
      tie_rate = mean(ap == ar)
    )
  }

  overall <- calc(x)
  overall[, session_state := "ALL"]
  by_session <- x[, calc(.SD), by = session_state]
  data.table::rbindlist(list(overall, by_session), fill = TRUE)
}

# =============================================================================
# 1) Expanding-window folds shared by both models.
# =============================================================================
folds <- make_expanding_crossfit_folds(
  train,
  initial_fraction = cc$crossfit_initial_fraction,
  n_folds = cc$crossfit_folds
)

candidate_types <- c(
  "gaussian",
  "global_sym",
  "global_asym",
  "session_sym",
  "session_asym"
)

# =============================================================================
# 2) P1a-C cross-fit scores.
#    Safe reuse is allowed only when an existing calibrator manifest matches the
#    current asset + exact dataset SHA. This makes NVDAx re-testing much faster.
# =============================================================================
reuse_prior <- tolower(Sys.getenv("VALTIDE_REUSE_VALID_PRIOR", unset = "true")) == "true"
p1a_manifest_path <- file.path(out_dir, "p1a_c_calibrator.json")
p1a_scores_path <- file.path(out_dir, "crossfit_scores.csv")
p1a_fold_summary_path <- file.path(out_dir, "crossfit_fold_summary.csv")
can_reuse_scores <- FALSE

if (reuse_prior && file.exists(p1a_manifest_path) && file.exists(p1a_scores_path)) {
  old_manifest <- tryCatch(jsonlite::read_json(p1a_manifest_path, simplifyVector = TRUE), error = function(e) NULL)
  can_reuse_scores <- !is.null(old_manifest) &&
    identical(toupper(as.character(old_manifest$asset_id %||% "")), toupper(asset_id)) &&
    identical(as.character(old_manifest$dataset_sha256 %||% ""), dataset_sha)
}

if (can_reuse_scores) {
  message("Reusing existing same-asset, same-dataset P1a cross-fit scores.")
  scores <- data.table::fread(p1a_scores_path)
  scores[, timestamp_utc := as_utc(timestamp_utc)]
  fold_summary_dt <- if (file.exists(p1a_fold_summary_path)) data.table::fread(p1a_fold_summary_path) else data.table::data.table()
} else {
  p1a_crossfit_scores <- list()
  fold_summary <- list()
  previous_fit <- NULL

  for (f in folds) {
    fit_dt <- train[f$fit_idx]
    score_dt <- train[f$score_idx]
    fold_spec <- make_model_spec(fit_dt, character(), character())
    fit_data <- prepare_model_data(fit_dt, fold_spec, hide_nvda = FALSE)

    message("\n========================================")
    message(sprintf("P1a cross-fit fold %d/%d", f$fold, length(folds)))
    message(sprintf("Fit rows %d -> %d | score rows %d -> %d",
                    min(f$fit_idx), max(f$fit_idx), min(f$score_idx), max(f$score_idx)))
    message("========================================")

    fold_fit <- fit_state_model("P1a", fit_data, fold_spec, config, previous_fit = previous_fit)
    fold_fit$asset_id <- asset_id
    fold_fit$dataset_sha256 <- dataset_sha
    saveRDS(fold_fit, file.path(out_dir, sprintf("crossfit_fold_%02d_fit.rds", f$fold)))

    replay <- p1a_one_step_reference_replay(
      fold_fit, score_dt, fold_spec,
      init_state = fold_fit$train_filter$final_state,
      init_P = fold_fit$train_filter$final_P
    )
    replay[, `:=`(
      fold = f$fold,
      score_eligible = is.finite(nvda_log_price) & is.finite(nvdax_log_price) & is.finite(signed_score)
    )]
    eligible <- replay[score_eligible == TRUE]
    p1a_crossfit_scores[[length(p1a_crossfit_scores) + 1L]] <- eligible

    fold_summary[[length(fold_summary) + 1L]] <- data.table::data.table(
      fold = f$fold,
      fit_start = min(fit_dt$timestamp_utc),
      fit_end = max(fit_dt$timestamp_utc),
      score_start = min(score_dt$timestamp_utc),
      score_end = max(score_dt$timestamp_utc),
      fit_rows = nrow(fit_dt),
      score_rows = nrow(score_dt),
      eligible_scores = nrow(eligible),
      logLik = fold_fit$loglik,
      elapsed_sec = fold_fit$elapsed_sec,
      convergence = fold_fit$optimizer$convergence
    )
    previous_fit <- fold_fit
  }

  scores <- data.table::rbindlist(p1a_crossfit_scores, fill = TRUE)
  fold_summary_dt <- data.table::rbindlist(fold_summary, fill = TRUE)
  data.table::fwrite(scores, p1a_scores_path)
  data.table::fwrite(fold_summary_dt, p1a_fold_summary_path)
}

if (nrow(scores) < 500L) stop("Too few P1a cross-fit calibration scores.")
message(sprintf("P1a-C: %d out-of-sample calibration scores.", nrow(scores)))

# =============================================================================
# 3) Raw-xStock-C cross-fit residuals on the SAME chronological score folds.
#    No model fitting is needed: the raw xStock itself is the center estimate.
# =============================================================================
raw_score_list <- list()
for (f in folds) {
  score_dt <- train[f$score_idx]
  r <- make_raw_replay(score_dt)
  r[, `:=`(
    fold = f$fold,
    score_eligible = is.finite(nvda_log_price) & is.finite(nvdax_log_price) & is.finite(signed_score)
  )]
  raw_score_list[[length(raw_score_list) + 1L]] <- r[score_eligible == TRUE]
}
raw_scores <- data.table::rbindlist(raw_score_list, fill = TRUE)
data.table::fwrite(raw_scores, file.path(out_dir, "raw_crossfit_scores.csv"))
if (nrow(raw_scores) < 500L) stop("Too few Raw-xStock calibration residuals.")
message(sprintf("Raw-xStock-C: %d out-of-sample calibration residuals.", nrow(raw_scores)))

# =============================================================================
# 4) Select calibration family separately for P1a-C and Raw-xStock-C.
#    Folds 1..K-1 fit candidate calibrators; fold K validates selection.
# =============================================================================
p1a_selector_train <- scores[fold < max(fold)]
p1a_selector_valid <- scores[fold == max(fold)]
p1a_validation_metrics <- list()

for (type in candidate_types) {
  cal <- fit_calibrator(
    p1a_selector_train,
    type = type,
    level = cc$primary_level,
    min_session_scores = cc$min_session_scores
  )
  ev <- evaluate_calibrator(p1a_selector_valid, cal, label = type)
  p1a_validation_metrics[[length(p1a_validation_metrics) + 1L]] <- ev$metrics
}
p1a_validation_dt <- data.table::rbindlist(p1a_validation_metrics, fill = TRUE)
data.table::fwrite(p1a_validation_dt, file.path(out_dir, "candidate_validation_metrics.csv"))
p1a_selected_type <- select_calibrator_type(
  p1a_validation_dt,
  level = cc$primary_level,
  coverage_tolerance = cc$coverage_tolerance
)
message("Selected P1a-C calibration family: ", p1a_selected_type)

raw_selector_train <- raw_scores[fold < max(fold)]
raw_selector_valid <- raw_scores[fold == max(fold)]
raw_validation_metrics <- list()

for (type in candidate_types) {
  cal <- fit_raw_calibrator(
    raw_selector_train,
    type = type,
    level = cc$primary_level,
    min_session_scores = cc$min_session_scores
  )
  ev <- evaluate_raw_calibrator(raw_selector_valid, cal, label = type)
  raw_validation_metrics[[length(raw_validation_metrics) + 1L]] <- ev$metrics
}
raw_validation_dt <- data.table::rbindlist(raw_validation_metrics, fill = TRUE)
data.table::fwrite(raw_validation_dt, file.path(out_dir, "raw_candidate_validation_metrics.csv"))
raw_selected_type <- select_calibrator_type(
  raw_validation_dt,
  level = cc$primary_level,
  coverage_tolerance = cc$coverage_tolerance
)
message("Selected Raw-xStock-C calibration family: ", raw_selected_type)

# Refit both selected calibration families on all cross-fit residuals for each level.
p1a_final_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_calibrator(scores, p1a_selected_type, level, cc$min_session_scores)
})
names(p1a_final_calibrators) <- sprintf("%.2f", cc$interval_levels)

p1a_gaussian_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_calibrator(scores, "gaussian", level, cc$min_session_scores)
})
names(p1a_gaussian_calibrators) <- names(p1a_final_calibrators)

raw_final_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_raw_calibrator(raw_scores, raw_selected_type, level, cc$min_session_scores)
})
names(raw_final_calibrators) <- sprintf("%.2f", cc$interval_levels)

raw_gaussian_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_raw_calibrator(raw_scores, "gaussian", level, cc$min_session_scores)
})
names(raw_gaussian_calibrators) <- names(raw_final_calibrators)

# =============================================================================
# 5) Full P1a fit for the untouched test replay.
#    Automatically reuse only an exact same-asset/same-dataset fit.
# =============================================================================
full_fit_path <- file.path(out_dir, "P1a_full_fit.rds")
reuse_full_fit <- FALSE
if (reuse_prior && file.exists(full_fit_path)) {
  candidate_fit <- tryCatch(readRDS(full_fit_path), error = function(e) NULL)
  reuse_full_fit <- !is.null(candidate_fit) &&
    identical(candidate_fit$model_id, "P1a") &&
    identical(toupper(as.character(candidate_fit$asset_id %||% "")), toupper(asset_id)) &&
    identical(as.character(candidate_fit$dataset_sha256 %||% ""), dataset_sha)
  if (reuse_full_fit) {
    full_fit <- candidate_fit
    message("Reusing same-asset, same-dataset full P1a fit: ", full_fit_path)
  }
}

if (!reuse_full_fit) {
  message("Fitting P1a on the complete original training sample.")
  train_data <- prepare_model_data(train, full_spec, hide_nvda = FALSE)
  full_fit <- fit_state_model("P1a", train_data, full_spec, config, previous_fit = NULL)
  full_fit$asset_id <- asset_id
  full_fit$dataset_sha256 <- dataset_sha
  saveRDS(full_fit, full_fit_path)
}
if (!is.null(full_fit$spec)) full_spec <- full_fit$spec

p1a_test_replay <- p1a_one_step_reference_replay(
  full_fit, test, full_spec,
  init_state = full_fit$train_filter$final_state,
  init_P = full_fit$train_filter$final_P
)
raw_test_replay <- make_raw_replay(test)

# =============================================================================
# 6) Untouched test evaluation at all reporting levels.
# =============================================================================
combined_test_metrics <- list()
p1a_primary <- p1a_gaussian_primary <- raw_primary <- raw_gaussian_primary <- NULL

for (level in cc$interval_levels) {
  key <- sprintf("%.2f", level)

  p1a_ev <- evaluate_calibrator(
    p1a_test_replay,
    p1a_final_calibrators[[key]],
    label = paste0("P1a-C:", p1a_selected_type)
  )
  p1a_g_ev <- evaluate_calibrator(
    p1a_test_replay,
    p1a_gaussian_calibrators[[key]],
    label = "P1a-Gaussian"
  )
  raw_ev <- evaluate_raw_calibrator(
    raw_test_replay,
    raw_final_calibrators[[key]],
    label = paste0("Raw-xStock-C:", raw_selected_type)
  )
  raw_g_ev <- evaluate_raw_calibrator(
    raw_test_replay,
    raw_gaussian_calibrators[[key]],
    label = "Raw-xStock-Gaussian"
  )

  combined_test_metrics[[length(combined_test_metrics) + 1L]] <- p1a_ev$metrics
  combined_test_metrics[[length(combined_test_metrics) + 1L]] <- p1a_g_ev$metrics
  combined_test_metrics[[length(combined_test_metrics) + 1L]] <- raw_ev$metrics
  combined_test_metrics[[length(combined_test_metrics) + 1L]] <- raw_g_ev$metrics

  if (abs(level - cc$primary_level) < 1e-12) {
    p1a_primary <- p1a_ev$scored
    p1a_gaussian_primary <- p1a_g_ev$scored
    raw_primary <- raw_ev$scored
    raw_gaussian_primary <- raw_g_ev$scored
  }
}

combined_test_metrics_dt <- data.table::rbindlist(combined_test_metrics, fill = TRUE)
data.table::fwrite(combined_test_metrics_dt, file.path(out_dir, "test_interval_metrics_comparison.csv"))

# Preserve the legacy P1a-only file shape for compatibility with existing tooling.
p1a_only_metrics <- combined_test_metrics_dt[grepl("^P1a", candidate)]
data.table::fwrite(p1a_only_metrics, file.path(out_dir, "test_interval_metrics.csv"))

# Direct center-estimate comparison on an identical test sample.
point_metrics <- point_estimate_comparison(p1a_test_replay, raw_test_replay)
data.table::fwrite(point_metrics, file.path(out_dir, "test_point_estimate_comparison.csv"))

# Primary interval replays.
p1a_primary[, coverage_eval_available := is.finite(nvda_log_price)]
p1a_primary[, interval_target := "contemporaneous_reference_equivalent"]
data.table::fwrite(p1a_primary, file.path(out_dir, "test_primary_intervals.csv"))

raw_primary[, coverage_eval_available := is.finite(nvda_log_price)]
raw_primary[, interval_target := "contemporaneous_reference_equivalent"]
data.table::fwrite(raw_primary, file.path(out_dir, "raw_test_primary_intervals.csv"))

# Actual closed/overnight inference rows. No contemporaneous underlying label is
# available there, so these are replay outputs, not empirical coverage claims.
p1a_closed_replay <- p1a_primary[
  !is.finite(nvda_log_price) & is.finite(nvdax_log_price),
  .(
    timestamp_utc, session_state, nvdax_log_price,
    minutes_since_last_nvda,
    calibrated_price_mid, calibrated_price_lo, calibrated_price_hi,
    calibrated_log_lo, calibrated_log_hi,
    reference_hidden_P, reference_predictive_sd,
    calibration_source, interval_target, coverage_eval_available
  )
]
data.table::fwrite(p1a_closed_replay, file.path(out_dir, "closed_market_replay.csv"))

raw_closed_replay <- raw_primary[
  !is.finite(nvda_log_price) & is.finite(nvdax_log_price),
  .(
    timestamp_utc, session_state, nvdax_log_price,
    calibrated_price_mid, calibrated_price_lo, calibrated_price_hi,
    calibrated_log_lo, calibrated_log_hi,
    calibration_source, interval_target, coverage_eval_available
  )
]
data.table::fwrite(raw_closed_replay, file.path(out_dir, "raw_closed_market_replay.csv"))

# =============================================================================
# 7) Block-bootstrap interval comparisons.
# =============================================================================
boot_p1a_vs_gaussian <- block_bootstrap_difference(
  p1a_primary,
  p1a_gaussian_primary,
  level = cc$primary_level,
  reps = cc$bootstrap_reps,
  seed = cc$random_seed
)
if (nrow(boot_p1a_vs_gaussian)) {
  boot_p1a_vs_gaussian[, `:=`(
    model_a = paste0("P1a-C:", p1a_selected_type),
    model_b = "P1a-Gaussian",
    level = cc$primary_level
  )]
}
data.table::fwrite(boot_p1a_vs_gaussian, file.path(out_dir, "test_block_bootstrap_vs_gaussian.csv"))

boot_raw_vs_p1a <- block_bootstrap_difference(
  raw_primary,
  p1a_primary,
  level = cc$primary_level,
  reps = cc$bootstrap_reps,
  seed = cc$random_seed + 1L
)
if (nrow(boot_raw_vs_p1a)) {
  boot_raw_vs_p1a[, `:=`(
    model_a = paste0("Raw-xStock-C:", raw_selected_type),
    model_b = paste0("P1a-C:", p1a_selected_type),
    level = cc$primary_level,
    interpretation = "negative score_diff_bps favors Raw-xStock-C"
  )]
}
data.table::fwrite(boot_raw_vs_p1a, file.path(out_dir, "test_block_bootstrap_rawc_vs_p1ac.csv"))

# =============================================================================
# 8) Pseudo-closure stress tests using the SAME duration design.
# =============================================================================
p1a_primary_cal <- p1a_final_calibrators[[sprintf("%.2f", cc$primary_level)]]
raw_primary_cal <- raw_final_calibrators[[sprintf("%.2f", cc$primary_level)]]

p1a_stress <- pseudo_closure_stress(
  full_fit, test, full_spec, p1a_primary_cal,
  durations_min = cc$pseudo_closure_minutes
)
if (nrow(p1a_stress$detail)) data.table::fwrite(p1a_stress$detail, file.path(out_dir, "pseudo_closure_detail.csv"))
if (nrow(p1a_stress$metrics)) data.table::fwrite(p1a_stress$metrics, file.path(out_dir, "pseudo_closure_metrics.csv"))

raw_stress <- raw_pseudo_closure_stress(
  test, raw_primary_cal,
  durations_min = cc$pseudo_closure_minutes
)
if (nrow(raw_stress$detail)) data.table::fwrite(raw_stress$detail, file.path(out_dir, "raw_pseudo_closure_detail.csv"))
if (nrow(raw_stress$metrics)) data.table::fwrite(raw_stress$metrics, file.path(out_dir, "raw_pseudo_closure_metrics.csv"))

if (nrow(p1a_stress$metrics) && nrow(raw_stress$metrics)) {
  p <- data.table::copy(p1a_stress$metrics)
  r <- data.table::copy(raw_stress$metrics)
  data.table::setnames(p, setdiff(names(p), "duration_min"), paste0("P1aC_", setdiff(names(p), "duration_min")))
  data.table::setnames(r, setdiff(names(r), "duration_min"), paste0("RawC_", setdiff(names(r), "duration_min")))
  stress_compare <- merge(p, r, by = "duration_min", all = TRUE, sort = TRUE)
  stress_compare[, `:=`(
    RawC_minus_P1aC_MAE_bps = RawC_MAE_bps - P1aC_MAE_bps,
    RawC_minus_P1aC_interval_score_bps = RawC_mean_interval_score_bps - P1aC_mean_interval_score_bps
  )]
  data.table::fwrite(stress_compare, file.path(out_dir, "pseudo_closure_comparison.csv"))
} else {
  stress_compare <- data.table::data.table()
}

# =============================================================================
# 9) Persist calibrators + compact comparison report.
# =============================================================================
p1a_cal_json <- list(
  generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  base_model = "P1a",
  selected_calibration_type = p1a_selected_type,
  primary_level = cc$primary_level,
  interval_target = "contemporaneous reference-equivalent predictive interval",
  note = paste(
    "Empirical calibration is validated only where the contemporaneous underlying reference is observable.",
    "Closed/overnight intervals use the selected global fallback unless a session calibration exists;",
    "their true latent-state coverage is not directly observable."
  ),
  crossfit = list(
    initial_fraction = cc$crossfit_initial_fraction,
    folds = cc$crossfit_folds,
    score_count = nrow(scores),
    selector_train_folds = paste(seq_len(cc$crossfit_folds - 1L), collapse = ","),
    selector_validation_fold = cc$crossfit_folds
  ),
  calibrators = lapply(p1a_final_calibrators, calibrator_to_jsonable)
)
jsonlite::write_json(p1a_cal_json, file.path(out_dir, "p1a_c_calibrator.json"), auto_unbox = TRUE, pretty = TRUE)

raw_cal_json <- list(
  generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  base_model = "raw_xstock",
  selected_calibration_type = raw_selected_type,
  primary_level = cc$primary_level,
  interval_target = "contemporaneous reference-equivalent predictive interval",
  center_definition = "raw tokenized-equity log price; calibration changes interval only",
  note = paste(
    "Raw-xStock-C does not alter the xStock point estimate.",
    "Empirical residual offsets are learned only from earlier observations with both xStock and underlying labels.",
    "Closed/overnight coverage is not directly observable and uses global fallback when no session-specific calibrator exists."
  ),
  crossfit = list(
    initial_fraction = cc$crossfit_initial_fraction,
    folds = cc$crossfit_folds,
    score_count = nrow(raw_scores),
    selector_train_folds = paste(seq_len(cc$crossfit_folds - 1L), collapse = ","),
    selector_validation_fold = cc$crossfit_folds
  ),
  calibrators = lapply(raw_final_calibrators, raw_calibrator_to_jsonable)
)
jsonlite::write_json(raw_cal_json, file.path(out_dir, "raw_xstock_c_calibrator.json"), auto_unbox = TRUE, pretty = TRUE)

comparison_report <- list(
  generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  p1a_c_selected_type = p1a_selected_type,
  raw_xstock_c_selected_type = raw_selected_type,
  primary_level = cc$primary_level,
  point_estimate_comparison = point_metrics[session_state == "ALL"],
  primary_interval_comparison = combined_test_metrics_dt[
    session_state == "ALL" & abs(level - cc$primary_level) < 1e-12 &
      candidate %in% c(paste0("P1a-C:", p1a_selected_type), paste0("Raw-xStock-C:", raw_selected_type))
  ],
  bootstrap_rawc_vs_p1ac = boot_raw_vs_p1a,
  pseudo_closure_comparison = stress_compare
)
jsonlite::write_json(
  comparison_report,
  file.path(out_dir, "p1ac_vs_rawc_report.json"),
  auto_unbox = TRUE,
  pretty = TRUE,
  na = "null"
)

message("\n========================================")
message("P1a-C vs Raw-xStock-C COMPLETE")
message("P1a-C calibration: ", p1a_selected_type)
message("Raw-xStock-C calibration: ", raw_selected_type)
message("Primary new outputs:")
message("  ", file.path(out_dir, "test_point_estimate_comparison.csv"))
message("  ", file.path(out_dir, "test_interval_metrics_comparison.csv"))
message("  ", file.path(out_dir, "raw_candidate_validation_metrics.csv"))
message("  ", file.path(out_dir, "test_block_bootstrap_rawc_vs_p1ac.csv"))
message("  ", file.path(out_dir, "pseudo_closure_comparison.csv"))
message("  ", file.path(out_dir, "raw_xstock_c_calibrator.json"))
message("  ", file.path(out_dir, "p1ac_vs_rawc_report.json"))
message("========================================\n")

cat("\n90% point-estimate comparison (same labeled test rows)\n")
print(point_metrics[session_state == "ALL"])

cat("\n90% interval comparison (same untouched test set)\n")
print(combined_test_metrics_dt[
  session_state == "ALL" & abs(level - cc$primary_level) < 1e-12,
  .(candidate, n, coverage, coverage_error, mean_width_bps, mean_interval_score_bps, MAE_bps, RMSE_bps)
])
