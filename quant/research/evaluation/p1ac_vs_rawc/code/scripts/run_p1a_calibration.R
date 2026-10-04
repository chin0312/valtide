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
if (!is.null(asset_metadata$asset_id) && nzchar(asset_id) && asset_id != "unknown" && !identical(toupper(as.character(asset_metadata$asset_id)), toupper(asset_id))) {
  stop("VALTIDE_ASSET_ID does not match asset_metadata.json.", call. = FALSE)
}
message("P1a-C asset: ", asset_id, " | dataset SHA256: ", dataset_sha)
message("P1a-C: loading cached data only; no market-data APIs will be called.")
panel <- add_derived_features(load_cached_panel(cache_dir))
split <- split_cached_panel(panel, config)
train <- split$train
test <- split$test

# P1a does not use external factors or quality covariates. Keep the specification
# intentionally narrow so calibration is an improvement to P1a, not a hidden new model.
full_spec <- make_model_spec(train, character(), character())

message(sprintf("Original split: %s", split$description))
message(sprintf("Train rows=%d | untouched test rows=%d", nrow(train), nrow(test)))
message("Sessions: ", paste(full_spec$sessions, collapse = ", "))

# -----------------------------------------------------------------------------
# 1) Expanding-window cross-fit scores inside the ORIGINAL TRAIN SAMPLE.
# -----------------------------------------------------------------------------
folds <- make_expanding_crossfit_folds(
  train,
  initial_fraction = cc$crossfit_initial_fraction,
  n_folds = cc$crossfit_folds
)

crossfit_scores <- list()
fold_summary <- list()
previous_fit <- NULL

for (f in folds) {
  fit_dt <- train[f$fit_idx]
  score_dt <- train[f$score_idx]
  fold_spec <- make_model_spec(fit_dt, character(), character())
  fit_data <- prepare_model_data(fit_dt, fold_spec, hide_nvda = FALSE)

  message("\n========================================")
  message(sprintf("Cross-fit fold %d/%d", f$fold, length(folds)))
  message(sprintf("Fit rows %d -> %d | score rows %d -> %d",
                  min(f$fit_idx), max(f$fit_idx), min(f$score_idx), max(f$score_idx)))
  message("========================================")

  # Each score fold must be genuinely out-of-sample relative to its own model.
  # A previous fold may warm-start optimization because it contains only earlier data.
  fold_fit <- fit_state_model("P1a", fit_data, fold_spec, config, previous_fit = previous_fit)
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
  crossfit_scores[[length(crossfit_scores) + 1L]] <- eligible

  fold_summary[[length(fold_summary) + 1L]] <- data.table(
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

scores <- rbindlist(crossfit_scores, fill = TRUE)
fold_summary_dt <- rbindlist(fold_summary, fill = TRUE)
fwrite(scores, file.path(out_dir, "crossfit_scores.csv"))
fwrite(fold_summary_dt, file.path(out_dir, "crossfit_fold_summary.csv"))

if (nrow(scores) < 500L) stop("Too few cross-fit calibration scores.")
message(sprintf("Collected %d out-of-sample calibration scores.", nrow(scores)))

# -----------------------------------------------------------------------------
# 2) Select calibration family WITHOUT touching the original test sample.
#    Folds 1..K-1 fit candidate calibrators; fold K is calibration validation.
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
message("Selected calibration family from cross-fit validation: ", selected_type)

# Refit the selected calibration family on ALL cross-fit scores, separately for
# every reporting level. The original held-out test has still not been touched.
final_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_calibrator(
    scores,
    type = selected_type,
    level = level,
    min_session_scores = cc$min_session_scores
  )
})
names(final_calibrators) <- sprintf("%.2f", cc$interval_levels)

# Also retain Gaussian baseline calibrators for direct comparison.
gaussian_calibrators <- lapply(cc$interval_levels, function(level) {
  fit_calibrator(scores, type = "gaussian", level = level, min_session_scores = cc$min_session_scores)
})
names(gaussian_calibrators) <- names(final_calibrators)

# -----------------------------------------------------------------------------
# 3) Full P1a fit for the final untouched test replay.
# -----------------------------------------------------------------------------
full_fit_path <- file.path(out_dir, "P1a_full_fit.rds")
reuse_ok <- FALSE
if (cc$reuse_full_p1a_fit && file.exists(full_fit_path)) {
  candidate_fit <- readRDS(full_fit_path)
  reuse_ok <- identical(candidate_fit$model_id, "P1a") &&
    identical(toupper(as.character(candidate_fit$asset_id %||% "")), toupper(asset_id)) &&
    identical(as.character(candidate_fit$dataset_sha256 %||% ""), dataset_sha)
  if (reuse_ok) {
    full_fit <- candidate_fit
    message("Reusing same-asset, same-dataset full P1a fit: ", full_fit_path)
  } else {
    message("Saved P1a fit exists but asset/dataset fingerprint differs; refitting from scratch.")
  }
}
if (!reuse_ok) {
  message("Fitting P1a on the complete original training sample.")
  train_data <- prepare_model_data(train, full_spec, hide_nvda = FALSE)
  full_fit <- fit_state_model("P1a", train_data, full_spec, config, previous_fit = NULL)
  full_fit$asset_id <- asset_id
  full_fit$dataset_sha256 <- dataset_sha
  saveRDS(full_fit, full_fit_path)
}

# Use the specification embedded in the saved fit where available so session
# ordering exactly matches the model that produced its raw parameter vector.
if (!is.null(full_fit$spec)) full_spec <- full_fit$spec

test_replay <- p1a_one_step_reference_replay(
  full_fit, test, full_spec,
  init_state = full_fit$train_filter$final_state,
  init_P = full_fit$train_filter$final_P
)

# -----------------------------------------------------------------------------
# 4) Untouched test evaluation: calibration + sharpness at multiple levels.
# -----------------------------------------------------------------------------
test_metrics <- list()
primary_selected <- primary_gaussian <- NULL

for (level in cc$interval_levels) {
  key <- sprintf("%.2f", level)
  cal_sel <- final_calibrators[[key]]
  cal_g <- gaussian_calibrators[[key]]

  ev_sel <- evaluate_calibrator(test_replay, cal_sel, label = paste0("P1a-C:", selected_type))
  ev_g <- evaluate_calibrator(test_replay, cal_g, label = "P1a-Gaussian")

  test_metrics[[length(test_metrics) + 1L]] <- ev_sel$metrics
  test_metrics[[length(test_metrics) + 1L]] <- ev_g$metrics

  if (abs(level - cc$primary_level) < 1e-12) {
    primary_selected <- ev_sel$scored
    primary_gaussian <- ev_g$scored
  }
}

test_metrics_dt <- rbindlist(test_metrics, fill = TRUE)
fwrite(test_metrics_dt, file.path(out_dir, "test_interval_metrics.csv"))

# Primary interval replay: includes actual closed/overnight rows even though no
# contemporaneous NVDA label exists there. coverage_eval_available makes this explicit.
primary_output <- copy(primary_selected)
primary_output[, coverage_eval_available := is.finite(nvda_log_price)]
primary_output[, interval_target := "contemporaneous_reference_equivalent"]
primary_output[, latent_gaussian_lo := reference_hidden_mean - stats::qnorm((1 + cc$primary_level)/2) * sqrt(reference_hidden_P)]
primary_output[, latent_gaussian_hi := reference_hidden_mean + stats::qnorm((1 + cc$primary_level)/2) * sqrt(reference_hidden_P)]
primary_output[, `:=`(
  latent_gaussian_price_lo = exp(latent_gaussian_lo),
  latent_gaussian_price_hi = exp(latent_gaussian_hi)
)]
fwrite(primary_output, file.path(out_dir, "test_primary_intervals.csv"))

closed_replay <- primary_output[
  !is.finite(nvda_log_price) & is.finite(nvdax_log_price),
  .(
    timestamp_utc, session_state, nvdax_log_price,
    minutes_since_last_nvda,
    calibrated_price_mid, calibrated_price_lo, calibrated_price_hi,
    calibrated_log_lo, calibrated_log_hi,
    reference_hidden_P, reference_predictive_sd,
    calibration_source,
    interval_target,
    coverage_eval_available
  )
]
fwrite(closed_replay, file.path(out_dir, "closed_market_replay.csv"))

# -----------------------------------------------------------------------------
# 5) Block-bootstrap comparison vs the original Gaussian 90% interval.
# -----------------------------------------------------------------------------
boot <- block_bootstrap_difference(
  primary_selected,
  primary_gaussian,
  level = cc$primary_level,
  reps = cc$bootstrap_reps,
  seed = cc$random_seed
)
if (nrow(boot)) {
  boot[, `:=`(
    model_a = paste0("P1a-C:", selected_type),
    model_b = "P1a-Gaussian",
    level = cc$primary_level
  )]
}
fwrite(boot, file.path(out_dir, "test_block_bootstrap_vs_gaussian.csv"))

# -----------------------------------------------------------------------------
# 6) Pseudo-closure stress test: contiguous periods with actual NVDA deliberately
#    hidden. This probes how calibration behaves as time-since-reference grows.
# -----------------------------------------------------------------------------
primary_cal <- final_calibrators[[sprintf("%.2f", cc$primary_level)]]
stress <- pseudo_closure_stress(
  full_fit, test, full_spec, primary_cal,
  durations_min = cc$pseudo_closure_minutes
)
if (nrow(stress$detail)) fwrite(stress$detail, file.path(out_dir, "pseudo_closure_detail.csv"))
if (nrow(stress$metrics)) fwrite(stress$metrics, file.path(out_dir, "pseudo_closure_metrics.csv"))

# -----------------------------------------------------------------------------
# 7) Persist production calibration parameters and a compact report.
# -----------------------------------------------------------------------------
cal_json <- list(
  generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  base_model = "P1a",
  selected_calibration_type = selected_type,
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
  calibrators = lapply(final_calibrators, calibrator_to_jsonable)
)
jsonlite::write_json(cal_json, file.path(out_dir, "p1a_c_calibrator.json"), auto_unbox = TRUE, pretty = TRUE)

report <- list(
  asset_id = asset_id,
  dataset_sha256 = dataset_sha,
  selected_type = selected_type,
  validation = validation_dt[session_state == "ALL" & abs(level - cc$primary_level) < 1e-12],
  test = test_metrics_dt[session_state == "ALL" & abs(level - cc$primary_level) < 1e-12],
  bootstrap = boot,
  pseudo_closure = stress$metrics
)
jsonlite::write_json(report, file.path(out_dir, "p1a_c_report.json"), auto_unbox = TRUE, pretty = TRUE, na = "null")

message("\n========================================")
message("P1a-C COMPLETE")
message("Selected calibration family: ", selected_type)
message("Primary outputs:")
message("  ", file.path(out_dir, "candidate_validation_metrics.csv"))
message("  ", file.path(out_dir, "test_interval_metrics.csv"))
message("  ", file.path(out_dir, "test_block_bootstrap_vs_gaussian.csv"))
message("  ", file.path(out_dir, "pseudo_closure_metrics.csv"))
message("  ", file.path(out_dir, "closed_market_replay.csv"))
message("  ", file.path(out_dir, "p1a_c_calibrator.json"))
message("========================================\n")
print(test_metrics_dt[session_state == "ALL" & abs(level - cc$primary_level) < 1e-12])
