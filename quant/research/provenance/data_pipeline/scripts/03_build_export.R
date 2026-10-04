source("R/utils.R")
source("R/build_panel.R")

settings <- asset_settings()
raw_dir <- file.path("data/raw", settings$slug)
processed_dir <- file.path("data/processed", settings$slug)
export_dir <- file.path("exports", settings$slug)
dir.create(processed_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(export_dir, recursive = TRUE, showWarnings = FALSE)

underlying_path <- file.path(raw_dir, "underlying_alpaca_5m.csv")
token_path <- file.path(raw_dir, "token_okx_5m.csv")
if (!file.exists(underlying_path) || !file.exists(token_path)) stop("Raw data are missing. Run scripts/02_download_data.R first.", call. = FALSE)
underlying <- data.table::fread(underlying_path); token <- data.table::fread(token_path)
underlying[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]; token[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]
panel <- build_canonical_panel(underlying, token, settings)
audit <- audit_panel(panel)

if (!nrow(panel[underlying_available & token_available])) stop("No overlapping underlying/token observations. P1a-C cannot be identified.", call. = FALSE)
overlap <- panel[underlying_available & token_available]
overlap[, price_ratio := token_close / underlying_close]
scale <- overlap[, .(n = .N, median_ratio = median(price_ratio, na.rm = TRUE), mean_ratio = mean(price_ratio, na.rm = TRUE), p01 = quantile(price_ratio, 0.01, na.rm = TRUE), p99 = quantile(price_ratio, 0.99, na.rm = TRUE))]
tolerance <- suppressWarnings(as.numeric(optional_env("SCALE_RATIO_TOLERANCE", "0.02")))
if (!is.finite(tolerance) || tolerance <= 0) stop("SCALE_RATIO_TOLERANCE must be positive.", call. = FALSE)

processed_path <- file.path(processed_dir, "canonical_panel_5m.csv")
export_path <- file.path(export_dir, "canonical_panel_5m.csv")
data.table::fwrite(panel, processed_path); data.table::fwrite(panel, export_path)
data.table::fwrite(audit, file.path(export_dir, "data_audit.csv"))
data.table::fwrite(scale, file.path(export_dir, "scale_check.csv"))

if (!is.finite(scale$median_ratio) || abs(scale$median_ratio - 1) > tolerance) {
  stop(sprintf("Token/underlying median raw price ratio %.6f differs from 1 by more than %.2f%%. Export was written for inspection, but do NOT upload/run P1a-C until multiplier/corporate-action normalization is resolved.", scale$median_ratio, 100 * tolerance), call. = FALSE)
}

deployment_path <- file.path(raw_dir, "selected_deployment.csv")
deployment <- if (file.exists(deployment_path)) data.table::fread(deployment_path) else data.table::data.table()
metadata <- list(
  asset_id = settings$asset_id,
  xstock_symbol = settings$xstock,
  underlying_symbol = settings$underlying,
  xstock_network = settings$network,
  data_start_utc = format_utc(min(panel$timestamp_utc)),
  data_end_utc = format_utc(max(panel$timestamp_utc)),
  rows = nrow(panel),
  overlap_rows = nrow(overlap),
  dataset_file = "canonical_panel_5m.csv",
  dataset_sha256 = sha256_file(export_path),
  compatibility_note = "Columns named nvda_* and nvdax_* are legacy P1a interface aliases for the selected underlying and xStock; they do not imply the asset is NVDA.",
  source = list(token = "OKX OnchainOS historical 5m candles", underlying = "Alpaca 5m stock bars", multiplier_metadata = "xStocks public multiplier history"),
  okx_deployment = if (nrow(deployment)) as.list(deployment[1]) else NULL,
  generated_at_utc = format_utc(Sys.time())
)
jsonlite::write_json(metadata, file.path(export_dir, "asset_metadata.json"), auto_unbox = TRUE, pretty = TRUE, null = "null", na = "null")
writeLines(metadata$dataset_sha256, file.path(export_dir, "dataset.sha256"))

print(audit); print(scale)
message("Sanitized GCP export ready: ", export_dir)
message("Only upload files from this export directory. It contains no API keys or .Renviron.")
