suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
})

source("config/model_config.R")
source("config/p1a_calibration_config.R")
source("R/utils.R")
source("R/load_cached_data.R")
source("R/model_spec.R")
source("R/p1a_calibration.R")
source("R/momentum_state_model.R")

config <- VALTIDE_CONFIG
cc <- P1A_C_CONFIG

asset_id <- Sys.getenv("VALTIDE_ASSET_ID", unset = "unknown")
cache_dir <- Sys.getenv("VALTIDE_CACHE_DIR", unset = "data/cache")
out_dir <- Sys.getenv("VALTIDE_OUTPUT_DIR", unset = "outputs/p1m_momentum")
p1a_dir <- Sys.getenv("VALTIDE_P1A_DIR", unset = "")
challenger_report_path <- Sys.getenv("VALTIDE_CHALLENGER_REPORT", unset = "")
gate_scored_path <- Sys.getenv("VALTIDE_GATE_SCORED", unset = "")

dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

metadata_path <- file.path(cache_dir, "asset_metadata.json")
metadata <- if (file.exists(metadata_path)) {
  jsonlite::read_json(metadata_path, simplifyVector = TRUE)
} else list()

if (!is.null(metadata$asset_id) &&
    nzchar(asset_id) &&
    asset_id != "unknown" &&
    toupper(as.character(metadata$asset_id)) != toupper(asset_id)) {
  stop("VALTIDE_ASSET_ID does not match asset_metadata.json.", call. = FALSE)
}

dataset_sha <- as.character(metadata$dataset_sha256 %||% "unknown")
message("P1m asset: ", asset_id, " | dataset SHA256: ", dataset_sha)
message("P1m: local cache only; no market-data APIs will be called.")

panel <- add_derived_features(load_cached_panel(cache_dir))
panel <- add_causal_xstock_momentum(panel, alpha = 0.35)
split <- split_cached_panel(panel, config)
train <- split$train
test <- split$test

full_spec <- make_model_spec(train, character(), character())

message(sprintf("Split: %s", split$description))
message(sprintf("Train rows=%d | development test rows=%d", nrow(train), nrow(test)))
message("Sessions: ", paste(full_spec$sessions, collapse = ", "))

load_p1a_fit <- function(path) {
  if (!nzchar(path) || !file.exists(path)) return(NULL)
  x <- try(readRDS(path), silent = TRUE)
  if (inherits(x, "try-error")) return(NULL)
  if (!identical(x$model_id, "P1a")) return(NULL)
  x
}

# -----------------------------------------------------------------------------
# 1) Expanding-window cross-fit P1m training and OOS replay.
# -----------------------------------------------------------------------------
folds <- make_expanding_crossfit_folds(
  train,
  initial_fraction = cc$crossfit_initial_fraction,
  n_folds = cc$crossfit_folds
)

crossfit_scores <- list()
fold_summary <- list()

for (f in folds) {
  fit_dt <- train[f$fit_idx]
  score_dt <- train[f$score_idx]
  fold_spec <- make_model_spec(fit_dt, character(), character())
  fit_data <- prepare_p1m_data(fit_dt, fold_spec, hide_nvda = FALSE)

  p1a_fold <- load_p1a_fit(
    if (nzchar(p1a_dir)) file.path(
      p1a_dir, sprintf("crossfit_fold_%02d_fit.rds", f$fold)
    ) else ""
  )

  message("\n========================================")
  message(sprintf("P1m cross-fit fold %d/%d", f$fold, length(folds)))
  message(sprintf("Fit rows %d -> %d | score rows %d -> %d",
                  min(f$fit_idx), max(f$fit_idx),
                  min(f$score_idx), max(f$score_idx)))
  message("========================================")

  fold_fit <- fit_p1m(
    fit_data, fold_spec, config,
    p1a_fit = p1a_fold
  )
  fold_fit$asset_id <- asset_id
  fold_fit$dataset_sha256 <- dataset_sha
  saveRDS(fold_fit, file.path(out_dir, sprintf("crossfit_fold_%02d_fit.rds", f$fold)))

  replay <- p1m_one_step_reference_replay(
    fold_fit, score_dt, fold_spec,
    init_state = fold_fit$train_filter$final_state,
    init_P = fold_fit$train_filter$final_P
  )

  replay[, `:=`(
    fold = f$fold,
    score_eligible = is.finite(nvda_log_price) &
      is.finite(nvdax_log_price) &
      is.finite(signed_score),
    raw_error_bps = 10000 * abs(nvdax_log_price - nvda_log_price),
    p1m_error_bps = 10000 * abs(reference_hidden_mean - nvda_log_price),
    disagreement_bps = 10000 * abs(nvdax_log_price - reference_hidden_mean)
  )]

  crossfit_scores[[length(crossfit_scores) + 1L]] <- replay[score_eligible == TRUE]

  fold_summary[[length(fold_summary) + 1L]] <- data.table(
    fold = f$fold,
    fit_start = min(fit_dt$timestamp_utc),
    fit_end = max(fit_dt$timestamp_utc),
    score_start = min(score_dt$timestamp_utc),
    score_end = max(score_dt$timestamp_utc),
    fit_rows = nrow(fit_dt),
    score_rows = nrow(score_dt),
    eligible_scores = sum(replay$score_eligible),
    logLik = fold_fit$loglik,
    AIC = fold_fit$AIC,
    BIC = fold_fit$BIC,
    elapsed_sec = fold_fit$elapsed_sec,
    convergence = fold_fit$optimizer$convergence,
    rho = fold_fit$decoded$rho,
    beta_momentum = fold_fit$decoded$beta_momentum,
    q_velocity = fold_fit$decoded$q_velocity
  )
}

scores <- rbindlist(crossfit_scores, fill = TRUE)
fold_summary_dt <- rbindlist(fold_summary, fill = TRUE)
fwrite(scores, file.path(out_dir, "crossfit_scores.csv"))
fwrite(fold_summary_dt, file.path(out_dir, "crossfit_fold_summary.csv"))

if (nrow(scores) < 500L) stop("Too few P1m cross-fit scores.")
message(sprintf("Collected %d P1m OOS calibration scores.", nrow(scores)))

# -----------------------------------------------------------------------------
# 2) Select P1m-C interval calibration without touching the development test.
# -----------------------------------------------------------------------------
selector_train <- scores[fold < max(fold)]
selector_valid <- scores[fold == max(fold)]

candidate_types <- c(
  "gaussian",
  "global_sym",
  "global_asym",
  "session_sym",
  "session_asym"
)

validation_metrics <- list()
for (type in candidate_types) {
  cal <- fit_calibrator(
    selector_train,
    type = type,
    level = cc$primary_level,
    min_session_scores = cc$min_session_scores
  )
  ev <- evaluate_calibrator(selector_valid, cal, label = type)
  validation_metrics[[length(validation_metrics) + 1L]] <- ev$metrics
}

validation_dt <- rbindlist(validation_metrics, fill = TRUE)
fwrite(validation_dt, file.path(out_dir, "candidate_validation_metrics.csv"))

selected_type <- select_calibrator_type(
  validation_dt,
  level = cc$primary_level,
  coverage_tolerance = cc$coverage_tolerance
)
message("Selected P1m calibration family: ", selected_type)

final_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_calibrator(
    scores,
    type = selected_type,
    level = level,
    min_session_scores = cc$min_session_scores
  )
})
names(final_calibrators) <- sprintf("%.2f", cc$interval_levels)

# -----------------------------------------------------------------------------
# 3) Full P1m fit on original training sample.
# -----------------------------------------------------------------------------
p1a_full <- load_p1a_fit(
  if (nzchar(p1a_dir)) file.path(p1a_dir, "P1a_full_fit.rds") else ""
)

full_fit <- fit_p1m(
  prepare_p1m_data(train, full_spec, hide_nvda = FALSE),
  full_spec,
  config,
  p1a_fit = p1a_full
)
full_fit$asset_id <- asset_id
full_fit$dataset_sha256 <- dataset_sha
saveRDS(full_fit, file.path(out_dir, "P1m_full_fit.rds"))

decoded_dt <- data.table(
  asset_id = asset_id,
  rho = full_fit$decoded$rho,
  beta_momentum = full_fit$decoded$beta_momentum,
  q_velocity = full_fit$decoded$q_velocity,
  r_underlying = full_fit$decoded$r_underlying,
  r_xstock = full_fit$decoded$r_xstock,
  logLik = full_fit$loglik,
  AIC = full_fit$AIC,
  BIC = full_fit$BIC,
  convergence = full_fit$optimizer$convergence
)
fwrite(decoded_dt, file.path(out_dir, "P1m_parameters.csv"))

# -----------------------------------------------------------------------------
# 4) Development-test one-step replay and calibrated intervals.
# -----------------------------------------------------------------------------
test_replay <- p1m_one_step_reference_replay(
  full_fit, test, full_spec,
  init_state = full_fit$train_filter$final_state,
  init_P = full_fit$train_filter$final_P
)
test_replay[, `:=`(
  raw_error_bps = 10000 * abs(nvdax_log_price - nvda_log_price),
  p1m_error_bps = 10000 * abs(reference_hidden_mean - nvda_log_price),
  disagreement_bps = 10000 * abs(nvdax_log_price - reference_hidden_mean)
)]

test_interval_metrics <- list()
primary_scored <- NULL

for (level in cc$interval_levels) {
  key <- sprintf("%.2f", level)
  ev <- evaluate_calibrator(
    test_replay,
    final_calibrators[[key]],
    label = paste0("P1m-C:", selected_type)
  )
  test_interval_metrics[[length(test_interval_metrics) + 1L]] <- ev$metrics

  if (abs(level - cc$primary_level) < 1e-12) {
    primary_scored <- ev$scored
  }
}

test_interval_metrics_dt <- rbindlist(test_interval_metrics, fill = TRUE)
fwrite(test_interval_metrics_dt, file.path(out_dir, "test_interval_metrics.csv"))
fwrite(primary_scored, file.path(out_dir, "test_primary_intervals.csv"))

# -----------------------------------------------------------------------------
# 5) Point-estimate comparison: raw xStock vs existing P1a vs P1m.
# -----------------------------------------------------------------------------
p1a_test_path <- if (nzchar(p1a_dir)) file.path(p1a_dir, "test_primary_intervals.csv") else ""
p1a_test <- if (file.exists(p1a_test_path)) fread(p1a_test_path) else data.table()

cmp <- copy(test_replay)
if (nrow(p1a_test)) {
  keep <- p1a_test[, .(
    timestamp_utc,
    p1a_mean = reference_hidden_mean,
    p1a_lo = calibrated_log_lo,
    p1a_hi = calibrated_log_hi
  )]
  cmp <- merge(cmp, keep, by = "timestamp_utc", all.x = TRUE, sort = FALSE)
} else {
  cmp[, `:=`(p1a_mean = NA_real_, p1a_lo = NA_real_, p1a_hi = NA_real_)]
}

cmp[, `:=`(
  p1a_error_bps = 10000 * abs(p1a_mean - nvda_log_price),
  p1m_minus_raw_improvement_bps = raw_error_bps - p1m_error_bps,
  p1m_minus_p1a_improvement_bps = p1a_error_bps - p1m_error_bps
)]

metric_row <- function(x, label) {
  x <- x[is.finite(nvda_log_price) & is.finite(nvdax_log_price)]
  data.table(
    subset = label,
    n = nrow(x),
    raw_mae_bps = mean(x$raw_error_bps, na.rm = TRUE),
    raw_rmse_bps = sqrt(mean(x$raw_error_bps^2, na.rm = TRUE)),
    p1a_mae_bps = mean(x$p1a_error_bps, na.rm = TRUE),
    p1a_rmse_bps = sqrt(mean(x$p1a_error_bps^2, na.rm = TRUE)),
    p1m_mae_bps = mean(x$p1m_error_bps, na.rm = TRUE),
    p1m_rmse_bps = sqrt(mean(x$p1m_error_bps^2, na.rm = TRUE)),
    p1m_beats_raw_rate = mean(x$p1m_error_bps < x$raw_error_bps, na.rm = TRUE),
    p1m_beats_p1a_rate = mean(x$p1m_error_bps < x$p1a_error_bps, na.rm = TRUE)
  )
}

point_rows <- list(metric_row(cmp, "ALL"))
for (ss in unique(cmp$session_state)) {
  point_rows[[length(point_rows) + 1L]] <- metric_row(
    cmp[session_state == ss],
    paste0("SESSION:", ss)
  )
}
point_dt <- rbindlist(point_rows, fill = TRUE)
fwrite(point_dt, file.path(out_dir, "test_point_estimate_comparison.csv"))

# -----------------------------------------------------------------------------
# 6) Targeted test of the hypothesis discovered in the diagnostics.
#    Uses the OLD P1a challenger labels, so P1m is evaluated on the exact
#    historical situations where P1a previously failed.
# -----------------------------------------------------------------------------
targeted <- data.table()
if (nzchar(gate_scored_path) && file.exists(gate_scored_path)) {
  gate <- fread(gate_scored_path)
  gate_keep <- gate[, .(
    timestamp_utc,
    base_review = as.logical(base_review),
    gated_status,
    true_tail_event = as.logical(true_tail_event),
    xret_3_bps,
    xvol_6_bps
  )]

  z <- merge(cmp, gate_keep, by = "timestamp_utc", all = FALSE, sort = FALSE)
  review <- z[base_review == TRUE]

  mom_q75 <- if (nrow(review)) {
    as.numeric(stats::quantile(abs(review$xret_3_bps), 0.75, na.rm = TRUE))
  } else NA_real_

  vol_q75 <- if (nrow(review)) {
    as.numeric(stats::quantile(review$xvol_6_bps, 0.75, na.rm = TRUE))
  } else NA_real_

  subsets <- list(
    ALL = z,
    BASE_REVIEW = review,
    TRUE_TAIL = z[true_tail_event == TRUE],
    REVIEW_HIGH_MOMENTUM_Q4 = review[
      is.finite(xret_3_bps) & abs(xret_3_bps) >= mom_q75
    ],
    REVIEW_HIGH_VOL_Q4 = review[
      is.finite(xvol_6_bps) & xvol_6_bps >= vol_q75
    ],
    REVIEW_P1A_FALSE = review[
      is.finite(p1a_error_bps) & p1a_error_bps > raw_error_bps
    ]
  )

  targeted <- rbindlist(lapply(names(subsets), function(nm) {
    x <- subsets[[nm]]
    out <- metric_row(x, nm)
    out[, `:=`(
      momentum_q75_bps = mom_q75,
      volatility_q75_bps = vol_q75
    )]
    out
  }), fill = TRUE)
}
fwrite(targeted, file.path(out_dir, "targeted_momentum_diagnostics.csv"))

# -----------------------------------------------------------------------------
# 7) New P1m challenger score: can disagreement identify raw-xStock tails?
#    Thresholds come ONLY from P1m cross-fit history.
# -----------------------------------------------------------------------------
tail_threshold <- if (nzchar(challenger_report_path) && file.exists(challenger_report_path)) {
  cr <- jsonlite::read_json(challenger_report_path, simplifyVector = TRUE)
  as.numeric(cr$relative_tail_threshold_bps_from_crossfit)
} else {
  as.numeric(stats::quantile(scores$raw_error_bps, 0.95, na.rm = TRUE))
}

q80 <- as.numeric(stats::quantile(scores$disagreement_bps, 0.80, na.rm = TRUE))
q90 <- as.numeric(stats::quantile(scores$disagreement_bps, 0.90, na.rm = TRUE))

chall <- cmp[
  is.finite(raw_error_bps) &
  is.finite(p1m_error_bps) &
  is.finite(disagreement_bps)
]
chall[, `:=`(
  true_tail_event = raw_error_bps >= tail_threshold,
  p1m_status = fifelse(
    disagreement_bps >= q90, "REVIEW",
    fifelse(disagreement_bps >= q80, "WATCH", "SUPPORT")
  )
)]

status_metrics <- chall[, .(
  n = .N,
  raw_mae_bps = mean(raw_error_bps),
  p1a_mae_bps = mean(p1a_error_bps, na.rm = TRUE),
  p1m_mae_bps = mean(p1m_error_bps),
  tail_rate = mean(true_tail_event),
  p1m_beats_raw_rate = mean(p1m_error_bps < raw_error_bps),
  p1m_beats_p1a_rate = mean(p1m_error_bps < p1a_error_bps, na.rm = TRUE)
), by = p1m_status]

review_flag <- chall$p1m_status == "REVIEW"
truth <- chall$true_tail_event
tp <- sum(review_flag & truth)
fp <- sum(review_flag & !truth)
fn <- sum(!review_flag & truth)
tn <- sum(!review_flag & !truth)

challenger_metrics <- data.table(
  asset_id = asset_id,
  tail_threshold_bps = tail_threshold,
  disagreement_q80_bps = q80,
  disagreement_q90_bps = q90,
  review_precision = if ((tp + fp) > 0) tp / (tp + fp) else NA_real_,
  review_recall = if ((tp + fn) > 0) tp / (tp + fn) else NA_real_,
  review_false_positive_rate = if ((fp + tn) > 0) fp / (fp + tn) else NA_real_,
  review_n = sum(review_flag),
  true_tail_n = sum(truth)
)

fwrite(status_metrics, file.path(out_dir, "p1m_challenger_status_profile.csv"))
fwrite(challenger_metrics, file.path(out_dir, "p1m_challenger_metrics.csv"))

# -----------------------------------------------------------------------------
# 8) Interval comparison with existing P1a-C on exact common rows.
# -----------------------------------------------------------------------------
interval_cmp <- data.table()
if (nrow(p1a_test)) {
  p1m90 <- primary_scored[, .(
    timestamp_utc,
    nvda_log_price,
    p1m_mid = reference_hidden_mean,
    p1m_lo = calibrated_log_lo,
    p1m_hi = calibrated_log_hi
  )]
  p1a90 <- p1a_test[, .(
    timestamp_utc,
    p1a_mid = reference_hidden_mean,
    p1a_lo = calibrated_log_lo,
    p1a_hi = calibrated_log_hi
  )]
  ic <- merge(p1m90, p1a90, by = "timestamp_utc", all = FALSE)
  ic <- ic[
    is.finite(nvda_log_price) &
    is.finite(p1m_lo) & is.finite(p1m_hi) &
    is.finite(p1a_lo) & is.finite(p1a_hi)
  ]

  interval_metric <- function(mid, lo, hi, label) {
    y <- ic$nvda_log_price
    alpha <- 1 - cc$primary_level
    score <- (hi - lo) +
      (2 / alpha) * (lo - y) * (y < lo) +
      (2 / alpha) * (y - hi) * (y > hi)
    data.table(
      model = label,
      n = length(y),
      coverage = mean(y >= lo & y <= hi),
      mean_width_bps = 10000 * mean(hi - lo),
      mean_interval_score_bps = 10000 * mean(score),
      MAE_bps = 10000 * mean(abs(mid - y)),
      RMSE_bps = 10000 * sqrt(mean((mid - y)^2))
    )
  }

  interval_cmp <- rbindlist(list(
    interval_metric(ic$p1a_mid, ic$p1a_lo, ic$p1a_hi, "P1a-C"),
    interval_metric(ic$p1m_mid, ic$p1m_lo, ic$p1m_hi, "P1m-C")
  ))
}
fwrite(interval_cmp, file.path(out_dir, "p1a_vs_p1m_interval_comparison.csv"))

# -----------------------------------------------------------------------------
# 9) Pseudo-closure stress.
# -----------------------------------------------------------------------------
primary_cal <- final_calibrators[[sprintf("%.2f", cc$primary_level)]]
stress <- p1m_pseudo_closure_stress(
  full_fit, test, full_spec, primary_cal,
  durations_min = cc$pseudo_closure_minutes
)
if (nrow(stress$detail)) {
  fwrite(stress$detail, file.path(out_dir, "pseudo_closure_detail.csv"))
}
if (nrow(stress$metrics)) {
  fwrite(stress$metrics, file.path(out_dir, "pseudo_closure_metrics.csv"))
}

# -----------------------------------------------------------------------------
# 10) Persist compact report.
# -----------------------------------------------------------------------------
cal_json <- list(
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  base_model = "P1m",
  state_equation = "m_t=m_{t-1}+v_{t-1}+beta*M_{t-1}+eta_m; v_t=rho*v_{t-1}+eta_v",
  momentum_feature = "causal EWMA of prior xStock 5-minute log returns; alpha=0.35",
  selected_calibration_type = selected_type,
  primary_level = cc$primary_level,
  calibrators = lapply(final_calibrators, calibrator_to_jsonable)
)
jsonlite::write_json(
  cal_json,
  file.path(out_dir, "p1m_c_calibrator.json"),
  auto_unbox = TRUE,
  pretty = TRUE
)

report <- list(
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  development_test_warning = paste(
    "The current test period has already been inspected during earlier Valtide development.",
    "Treat this experiment as development evidence; confirm any chosen model on a later untouched period."
  ),
  full_fit = as.list(decoded_dt[1]),
  selected_calibration_type = selected_type,
  point_comparison = point_dt,
  targeted_momentum_diagnostics = targeted,
  challenger_metrics = challenger_metrics,
  challenger_status_profile = status_metrics,
  interval_comparison = interval_cmp,
  pseudo_closure = stress$metrics
)
jsonlite::write_json(
  report,
  file.path(out_dir, "p1m_experiment_report.json"),
  auto_unbox = TRUE,
  pretty = TRUE,
  na = "null"
)

message("P1m experiment complete for ", asset_id)
