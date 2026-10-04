source("R/utils.R")
source("R/cache.R")
source("R/api_okx.R")
source("R/api_alpaca.R")
source("R/api_xstocks.R")

settings <- asset_settings()
raw_dir <- file.path("data/raw", settings$slug)
dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
start_time <- parse_utc(settings$start_utc); end_time <- parse_utc(settings$end_utc)
force <- flag_env("FORCE_REFRESH_DATA")
capture_okx_raw <- flag_env("OKX_CAPTURE_RAW_RESPONSES")
requery_okx_window <- flag_env("OKX_REQUERY_REQUESTED_WINDOW")
okx_capture_dir <- if (capture_okx_raw) file.path(raw_dir, "okx_http_raw") else NULL
if (capture_okx_raw) {
  dir.create(okx_capture_dir, recursive = TRUE, showWarnings = FALSE)
  message("LOCAL raw OKX response capture is ON: ", okx_capture_dir)
  message("Authentication headers, API keys, signatures and passphrases are NOT written to capture files.")
}
manifest <- if (force) list(version = 1L) else read_manifest(raw_dir)

# ----- Deployment selection -----
# The multi-asset experiment is network-pinned. By default XSTOCK_NETWORK=Solana,
# which maps to OKX chainIndex 501. We first filter to the requested network and
# only then select the highest-volume deployment on that network. The chosen
# chain/address is persisted in selected_deployment.csv and reused on later runs.
target_chain <- network_chain_index(settings$network)
chain_override <- optional_env("OKX_CHAIN_INDEX")
address_override <- optional_env("OKX_TOKEN_ADDRESS")
if (xor(nzchar(chain_override), nzchar(address_override))) stop("Set both OKX deployment overrides or neither.", call. = FALSE)
if (nzchar(chain_override) && chain_override != target_chain) {
  stop(sprintf("OKX_CHAIN_INDEX=%s conflicts with XSTOCK_NETWORK=%s (expected chainIndex=%s).", chain_override, settings$network, target_chain), call. = FALSE)
}

deployment_path <- file.path(raw_dir, "selected_deployment.csv")
deployment <- NULL

if (nzchar(chain_override)) {
  deployment <- data.table::data.table(
    chainIndex = chain_override,
    tokenContractAddress = address_override,
    tokenSymbol = settings$xstock,
    stockCode = settings$underlying,
    selectedNetwork = settings$network,
    selectedBy = "explicit_override"
  )
} else if (!force && file.exists(deployment_path)) {
  cached_deployment <- data.table::fread(deployment_path)
  cached_ok <- nrow(cached_deployment) && all(c("chainIndex", "tokenContractAddress") %in% names(cached_deployment))
  if (cached_ok && as.character(cached_deployment$chainIndex[[1]]) == target_chain) {
    deployment <- cached_deployment
    message("Reusing pinned ", settings$network, " deployment from ", deployment_path)
  } else if (cached_ok) {
    message("Ignoring previously pinned chainIndex=", cached_deployment$chainIndex[[1]],
            " because this run requires ", settings$network, " chainIndex=", target_chain, ".")
  }
}

if (is.null(deployment)) {
  matches <- discover_xstock(settings$xstock, settings$underlying)
  network_matches <- matches[as.character(chainIndex) == target_chain]
  if (!nrow(network_matches)) {
    stop(sprintf("No %s deployment (chainIndex=%s) found for %s / %s.", settings$network, target_chain, settings$xstock, settings$underlying), call. = FALSE)
  }
  # discover_xstock() sorts by volume24h descending when the field is present.
  deployment <- data.table::copy(network_matches[1])
  deployment[, `:=`(selectedNetwork = settings$network, selectedBy = "highest_volume_on_target_network")]
}

chain_index <- as.character(deployment$chainIndex[[1]])
token_address <- as.character(deployment$tokenContractAddress[[1]])
if (chain_index != target_chain) stop("Internal deployment-selection error: selected chain does not match requested network.", call. = FALSE)
data.table::fwrite(deployment, deployment_path)
message("Using pinned ", settings$network, " deployment for ", settings$xstock,
        ": chainIndex=", chain_index, " address=", token_address)

# ----- xStock / OKX -----
token_path <- file.path(raw_dir, "token_okx_5m.csv")
token_identity <- list(xstock_symbol = settings$xstock, chain_index = chain_index, token_address = token_address, bar = "5m")
token_valid <- !force && entry_identity_matches(manifest$token, token_identity) && entry_file_valid(manifest$token, raw_dir)
token <- if (token_valid) data.table::fread(token_path) else data.table::data.table()
if (nrow(token)) token[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]
token_windows <- if (requery_okx_window) {
  message("OKX requested-window requery is ON. Existing token cache will be preserved and refreshed for this window.")
  list(list(start = start_time, end = end_time))
} else if (token_valid) {
  missing_windows(manifest$token, start_time, end_time)
} else {
  list(list(start = start_time, end = end_time))
}
if (capture_okx_raw && !requery_okx_window && token_valid && !length(token_windows)) {
  warning("Raw OKX capture is enabled, but the requested window is already cached so no HTTP request will occur. Set OKX_REQUERY_REQUESTED_WINDOW=true to re-fetch this window without deleting the existing cache.")
}
old_qs <- if (token_valid) parse_utc(entry_value(manifest$token, "queried_start_utc")) else start_time
old_qe <- if (token_valid) parse_utc(entry_value(manifest$token, "queried_end_utc")) else end_time
for (w in token_windows) {
  message("Downloading ", settings$xstock, " from OKX: ", format_utc(w$start), " -> ", format_utc(w$end))
  d <- okx_historical_candles(
    chain_index, token_address, format_utc(w$start), format_utc(w$end),
    bar = "5m", capture_dir = okx_capture_dir
  )
  if (nrow(d)) {
    d[, `:=`(chain_index = chain_index, token_address = token_address)]
    token <- merge_rows(token, d)
  }
}
if (!nrow(token)) stop("OKX returned no token candles for the requested asset/window.", call. = FALSE)
write_csv_atomic(token, token_path)
queried_start <- min(c(start_time, old_qs), na.rm = TRUE); queried_end <- max(c(end_time, old_qe), na.rm = TRUE)
manifest$token <- make_entry(token_path, queried_start, queried_end, token_identity, token)
write_manifest(manifest, raw_dir)
message("Local token cache rows: ", nrow(token))

# ----- Underlying / Alpaca -----
underlying_path <- file.path(raw_dir, "underlying_alpaca_5m.csv")
underlying_identity <- list(symbol = settings$underlying, timeframe = "5Min", feed = settings$alpaca_feed, adjustment = "raw")
underlying_valid <- !force && entry_identity_matches(manifest$underlying, underlying_identity) && entry_file_valid(manifest$underlying, raw_dir)
underlying <- if (underlying_valid) data.table::fread(underlying_path) else data.table::data.table()
if (nrow(underlying)) underlying[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]
underlying_windows <- if (underlying_valid) missing_windows(manifest$underlying, start_time, end_time) else list(list(start = start_time, end = end_time))
old_qs_u <- if (underlying_valid) parse_utc(entry_value(manifest$underlying, "queried_start_utc")) else start_time
old_qe_u <- if (underlying_valid) parse_utc(entry_value(manifest$underlying, "queried_end_utc")) else end_time
for (w in underlying_windows) {
  message("Downloading ", settings$underlying, " from Alpaca: ", format_utc(w$start), " -> ", format_utc(w$end))
  d <- alpaca_stock_bars(settings$underlying, format_utc(w$start), format_utc(w$end), timeframe = "5Min", feed = settings$alpaca_feed, adjustment = "raw")
  if (nrow(d)) underlying <- merge_rows(underlying, d)
}
if (!nrow(underlying)) stop("Alpaca returned no underlying bars for the requested asset/window.", call. = FALSE)
write_csv_atomic(underlying, underlying_path)
queried_start_u <- min(c(start_time, old_qs_u), na.rm = TRUE); queried_end_u <- max(c(end_time, old_qe_u), na.rm = TRUE)
manifest$underlying <- make_entry(underlying_path, queried_start_u, queried_end_u, underlying_identity, underlying)
write_manifest(manifest, raw_dir)
message("Local underlying cache rows: ", nrow(underlying))

# ----- Public xStocks corporate-action/multiplier metadata -----
multiplier_path <- file.path(raw_dir, "multiplier_history.json")
if (force || !file.exists(multiplier_path)) {
  multiplier <- try(xstocks_multiplier_history(settings$xstock, settings$network), silent = TRUE)
  if (!inherits(multiplier, "try-error")) {
    jsonlite::write_json(multiplier, multiplier_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
    message("Saved xStocks multiplier history locally.")
  } else warning("Could not retrieve multiplier history. Do not ignore corporate-action normalization when interpreting the scale audit.")
} else message("Using cached multiplier history.")

message("Download complete. Raw data remain LOCAL under ", raw_dir)
