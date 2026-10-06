#!/usr/bin/env Rscript

# Export a James-handoff P1a full fit into Valtide's immutable Python runtime
# artifact shape. This does not refit or recalibrate the model.

args <- commandArgs(trailingOnly = TRUE)
`%||%` <- function(x, y) if (is.null(x) || length(x) == 0L) y else x
arg_value <- function(name, required = TRUE) {
  at <- match(name, args)
  if (is.na(at) || at == length(args)) {
    if (required) stop("missing required argument: ", name)
    return(NULL)
  }
  args[[at + 1L]]
}

handoff_root <- normalizePath(arg_value("--handoff-root"), mustWork = TRUE)
repo_root <- normalizePath(arg_value("--repo-root"), mustWork = TRUE)
asset_input <- tolower(arg_value("--asset"))
asset <- c(spyx = "SPYx", qqqx = "QQQx", aaplx = "AAPLx")[[asset_input]]
if (is.null(asset)) stop("asset must be one of SPYx, QQQx, or AAPLx")
output_dir <- arg_value("--output-dir")
deployment_version <- arg_value("--deployment-version", required = FALSE) %||% "0.3.0"

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("R package jsonlite is required for deterministic JSON export")
}

sha256_file <- function(path) {
  output <- suppressWarnings(system2("sha256sum", shQuote(path), stdout = TRUE, stderr = TRUE))
  status <- attr(output, "status")
  if (!length(output) || (!is.null(status) && status %in% c(126L, 127L))) {
    stop("sha256sum could not verify an input artifact")
  }
  hash <- strsplit(trimws(output[[1L]]), "[[:space:]]+")[[1L]][[1L]]
  if (!grepl("^[[:xdigit:]]{64}$", hash)) stop("invalid SHA-256 output")
  tolower(hash)
}
read_json <- function(path) jsonlite::fromJSON(path, simplifyVector = FALSE)
write_json <- function(value, path) {
  jsonlite::write_json(
    value, path, auto_unbox = TRUE, pretty = TRUE, digits = 17,
    null = "null", na = "null"
  )
}

asset_key <- tolower(asset)
asset_root <- file.path(handoff_root, asset_key)
binding_path <- file.path(asset_root, "model_binding.json")
fit_path <- file.path(asset_root, "full_fit.rds")
calibrator_path <- file.path(asset_root, "calibration", "p1a_c_calibrator.json")
binding <- read_json(binding_path)
datasets <- read_json(file.path(repo_root, "quant/data_manifest/datasets_manifest.json"))
dataset <- Filter(function(x) identical(x$asset_id, asset), datasets)
if (length(dataset) != 1L) stop("asset does not have exactly one committed dataset identity")
dataset <- dataset[[1L]]

if (!identical(binding$asset_id, asset) || !identical(dataset$asset_id, asset)) {
  stop("handoff fit, binding, and committed dataset assets must match")
}
if (!identical(binding$dataset_sha256, dataset$dataset_sha256)) {
  stop("handoff dataset SHA-256 does not match the committed asset manifest")
}
fit_sha <- sha256_file(fit_path)
calibrator_sha <- sha256_file(calibrator_path)
if (!identical(fit_sha, tolower(binding$model_sha256))) {
  stop("frozen fit SHA-256 does not match its handoff binding")
}
if (!identical(calibrator_sha, tolower(binding$calibration_sha256))) {
  stop("calibrator SHA-256 does not match its handoff binding")
}

fit <- readRDS(fit_path)
calibrator <- read_json(calibrator_path)
if (!identical(fit$status, "OK") || !identical(fit$model_id, "P1a")) {
  stop("only a converged, frozen P1a handoff fit can be exported")
}
if (!identical(fit$asset_id, asset) || !identical(fit$dataset_sha256, dataset$dataset_sha256)) {
  stop("RDS embedded asset/dataset identity does not match the handoff")
}
if (!identical(calibrator$asset_id, asset) ||
    !identical(calibrator$dataset_sha256, dataset$dataset_sha256)) {
  stop("calibrator asset/dataset identity does not match the handoff")
}
level <- as.numeric(binding$calibration_primary_level)
if (!isTRUE(all.equal(as.numeric(calibrator$primary_level), level, tolerance = 1e-12))) {
  stop("calibrator primary level does not match the handoff binding")
}
cal_key <- sprintf("%.2f", level)
if (is.null(calibrator$calibrators[[cal_key]]) ||
    !identical(calibrator$calibrators[[cal_key]]$type, binding$calibration_method)) {
  stop("selected calibration family does not match the handoff binding")
}

sessions <- c("regular", "premarket", "afterhours", "overnight", "closed")
decoded <- fit$decoded
q <- decoded$q_by_session[sessions]
theta <- decoded$theta_by_session[sessions]
r_token <- decoded$r_nvdax_by_session[sessions]
if (any(!is.finite(q)) || any(q <= 0) || any(!is.finite(theta)) ||
    any(abs(theta - 1) > 1e-12) || any(!is.finite(r_token)) || any(r_token <= 0)) {
  stop("frozen fit is not compatible with the current scalar P1a runtime")
}
if (max(r_token) - min(r_token) > 1e-12) {
  stop("P1a token measurement variance must be session-invariant for this runtime")
}
r_underlying <- as.numeric(decoded$r_nvda)
if (length(r_underlying) != 1L || !is.finite(r_underlying) || r_underlying <= 0) {
  stop("frozen fit has invalid underlying measurement variance")
}

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
runtime <- list(
  model_family = "P1a",
  deployment_model_id = "P1a-C",
  model_version = deployment_version,
  asset = asset,
  interval_level = level,
  q_by_session = as.list(setNames(as.numeric(q), sessions)),
  # Historical names retained by the frozen Python runtime: r_nvda is the
  # corresponding underlying variance and r_nvdax is this asset's token variance.
  r_nvda = r_underlying,
  r_nvdax = as.numeric(r_token[[1L]]),
  trained_through_utc = gsub("Z$", "+00:00", binding$training_cutoff_utc),
  source_model_version = binding$model_version,
  source_fit_sha256 = fit_sha,
  source_dataset_sha256 = dataset$dataset_sha256
)
provenance <- list(
  asset_id = asset,
  deployment_model_id = "P1a-C",
  deployment_model_version = deployment_version,
  source_model_family = "P1a",
  source_model_version = binding$model_version,
  source_model_version_status = "UNAVAILABLE_IN_HANDOFF",
  source_fit_sha256 = fit_sha,
  source_dataset_sha256 = dataset$dataset_sha256,
  source_dataset_sha256_independently_recomputed = FALSE,
  source_panel_bytes_in_handoff = FALSE,
  source_code_commit = binding$code_commit,
  source_code_commit_status = binding$code_commit_status,
  source_training_cutoff_utc = binding$training_cutoff_utc,
  calibration_cutoff_utc = binding$calibration_cutoff_utc,
  evaluation_test_start_utc = binding$evaluation_test_start_utc,
  calibration_family = binding$calibration_method,
  calibration_primary_level = level,
  calibration_score_count = as.integer(calibrator$calibrators[[cal_key]]$n),
  calibration_sha256 = calibrator_sha,
  calibration_generated_at_utc = binding$calibration_generated_at_utc,
  frozen_fit_status = fit$status,
  optimizer_convergence = as.integer(fit$optimizer$convergence),
  optimizer_message = fit$optimizer$message,
  source_r_environment_status = binding$environment_version_status,
  notes = "Parameter export only; no refit, recalibration, or dataset-byte verification was performed."
)

runtime_path <- file.path(output_dir, "p1a_runtime.json")
calibration_output <- file.path(output_dir, "p1a_c_calibrator.json")
provenance_path <- file.path(output_dir, "provenance.json")
write_json(runtime, runtime_path)
if (!file.copy(calibrator_path, calibration_output, overwrite = TRUE)) {
  stop("could not copy the bound calibration artifact byte-for-byte")
}
provenance$runtime_artifact_sha256 <- sha256_file(runtime_path)
write_json(provenance, provenance_path)
cat(sprintf("exported verified %s P1a-C artifact bundle (%s)\n", asset, deployment_version))
