source("R/utils.R")

required_packages <- c("data.table", "httr2", "jsonlite", "lubridate", "digest", "openssl")
missing <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", "), ". Run Rscript 00_install_packages.R first.", call. = FALSE)

settings <- asset_settings()
start <- parse_utc(settings$start_utc); end <- parse_utc(settings$end_utc)
if (is.na(start) || is.na(end) || start >= end) stop("Invalid DATA_START_UTC / DATA_END_UTC.", call. = FALSE)

# Verify secrets exist without printing their values.
for (name in c("OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE", "ALPACA_API_KEY", "ALPACA_SECRET_KEY")) require_env(name)

chain <- optional_env("OKX_CHAIN_INDEX")
address <- optional_env("OKX_TOKEN_ADDRESS")
if (xor(nzchar(chain), nzchar(address))) stop("Set both OKX_CHAIN_INDEX and OKX_TOKEN_ADDRESS, or leave both blank.", call. = FALSE)

message("Preflight passed for ", settings$xstock, " / ", settings$underlying)
message("Window: ", settings$start_utc, " -> ", settings$end_utc)
message("Network: ", settings$network, " (OKX chainIndex=", network_chain_index(settings$network), "); Alpaca feed: ", settings$alpaca_feed)
message("Credentials were detected locally; their values were not printed.")
