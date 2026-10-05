#!/usr/bin/env Rscript

# Freeze deterministic step-by-step output from James's original P1a reference
# replay for comparison with the Python runtime. Inputs are synthetic fixtures,
# not market observations or research evidence.

args <- commandArgs(trailingOnly = TRUE)
arg <- function(name) {
  at <- match(name, args)
  if (is.na(at) || at == length(args)) stop("missing argument: ", name)
  args[[at + 1L]]
}
if (!requireNamespace("jsonlite", quietly = TRUE) ||
    !requireNamespace("data.table", quietly = TRUE)) {
  stop("jsonlite and data.table are required to run the source R parity helper")
}

handoff <- normalizePath(arg("--handoff-root"), mustWork = TRUE)
repo <- normalizePath(arg("--repo-root"), mustWork = TRUE)
output <- arg("--output")
source(file.path(handoff, "provenance/R/model_spec.R"), local = TRUE)
source(file.path(handoff, "provenance/R/p1a_calibration.R"), local = TRUE)

iso_to_posix <- function(value) as.POSIXct(value, format = "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
sha256_file <- function(path) {
  line <- system2("sha256sum", shQuote(path), stdout = TRUE)
  strsplit(trimws(line[[1L]]), "[[:space:]]+")[[1L]][[1L]]
}
assets <- list(
  SPYx = list(
    bundle = "spyx",
    prices = c(660.0, 661.3, 662.1, 661.7, NA_real_, 660.9),
    underlying = c(659.8, 661.1, 662.0, NA_real_, 661.4, 660.8)
  ),
  QQQx = list(
    bundle = "qqqx",
    prices = c(590.0, 591.2, 592.4, 591.8, NA_real_, 590.7),
    underlying = c(589.7, 591.0, 592.2, NA_real_, 591.2, 590.6)
  ),
  AAPLx = list(
    bundle = "aaplx",
    prices = c(260.0, 260.8, 261.1, 260.3, NA_real_, 259.9),
    underlying = c(259.8, 260.7, 261.0, NA_real_, 260.2, 259.8)
  )
)
sessions <- c("regular", "regular", "premarket", "afterhours", "overnight", "closed")
timestamps <- seq(iso_to_posix("2026-10-02T13:30:00Z"), by = "5 min", length.out = length(sessions))
results <- list()

for (asset in names(assets)) {
  spec <- assets[[asset]]
  fit_path <- file.path(handoff, spec$bundle, "full_fit.rds")
  calibration_path <- file.path(handoff, spec$bundle, "calibration/p1a_c_calibrator.json")
  fit <- readRDS(fit_path)
  calibrator_doc <- jsonlite::fromJSON(calibration_path, simplifyVector = FALSE)
  if (!identical(fit$asset_id, asset) || !identical(fit$model_id, "P1a")) {
    stop("parity fixture fit identity mismatch for ", asset)
  }
  cal <- calibrator_doc$calibrators[[sprintf("%.2f", calibrator_doc$primary_level)]]
  state_m <- as.numeric(fit$train_filter$final_state[[1L]])
  state_P <- as.numeric(as.matrix(fit$train_filter$final_P)[1L, 1L])
  steps <- vector("list", length(sessions))

  for (i in seq_along(sessions)) {
    token <- spec$prices[[i]]
    underlying <- spec$underlying[[i]]
    row <- data.frame(
      timestamp_utc = timestamps[[i]],
      session_state = sessions[[i]],
      nvda_log_price = if (is.finite(underlying)) log(underlying) else NA_real_,
      nvdax_log_price = if (is.finite(token)) log(token) else NA_real_
    )
    replay <- p1a_one_step_reference_replay(
      fit, row, fit$spec,
      init_state = state_m,
      init_P = matrix(state_P, nrow = 1L, ncol = 1L)
    )
    bounds <- calibrator_bounds(cal, sessions[[i]])
    mean_log <- as.numeric(replay$reference_hidden_mean[[1L]])
    variance_log <- as.numeric(replay$reference_hidden_P[[1L]])
    predictive_sd <- as.numeric(replay$reference_predictive_sd[[1L]])
    lo_z <- as.numeric(bounds[["lo"]])
    hi_z <- as.numeric(bounds[["hi"]])
    next_state <- attr(replay, "final_state")
    next_P <- attr(replay, "final_P")
    steps[[i]] <- list(
      timestamp = format(timestamps[[i]], "%Y-%m-%dT%H:%M:%SZ", tz = "UTC"),
      session = sessions[[i]],
      token_price = if (is.finite(token)) token else NULL,
      current_underlying_price = if (is.finite(underlying)) underlying else NULL,
      challenger_m_log = mean_log,
      challenger_P_log = variance_log,
      reference_predictive_sd_log = predictive_sd,
      fair_value = exp(mean_log),
      lower_bound = exp(mean_log + lo_z * predictive_sd),
      upper_bound = exp(mean_log + hi_z * predictive_sd),
      state_m_after_observation = as.numeric(next_state[[1L]]),
      state_P_after_observation = as.numeric(as.matrix(next_P)[1L, 1L]),
      calibration_type = cal$type,
      calibration_source = as.character(bounds[["source"]])
    )
    state_m <- as.numeric(next_state[[1L]])
    state_P <- as.numeric(as.matrix(next_P)[1L, 1L])
  }
  results[[asset]] <- list(
    source = "James p1a_one_step_reference_replay; deterministic synthetic input",
    source_fit_sha256 = tolower(sha256_file(fit_path)),
    dataset_sha256 = fit$dataset_sha256,
    model_version = "0.3.0",
    initial_state_m = as.numeric(fit$train_filter$final_state[[1L]]),
    initial_state_P = as.numeric(as.matrix(fit$train_filter$final_P)[1L, 1L]),
    steps = steps
  )
}

dir.create(dirname(output), recursive = TRUE, showWarnings = FALSE)
jsonlite::write_json(
  list(schema_version = 1L, assets = results), output,
  auto_unbox = TRUE, pretty = TRUE, digits = 17, null = "null", na = "null"
)
cat("wrote deterministic source-R parity fixture\n")
