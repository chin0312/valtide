require_env <- function(name) {
  value <- trimws(Sys.getenv(name, unset = ""))
  if (!nzchar(value)) stop(sprintf("Environment variable %s is missing. Put it in your LOCAL .Renviron.", name), call. = FALSE)
  value
}

optional_env <- function(name, default = "") trimws(Sys.getenv(name, unset = default))

parse_utc <- function(x) {
  if (inherits(x, "POSIXt")) return(as.POSIXct(x, tz = "UTC"))
  out <- as.POSIXct(as.character(x), format = "%Y-%m-%dT%H:%M:%OSZ", tz = "UTC")
  miss <- is.na(out) & !is.na(x)
  if (any(miss)) out[miss] <- as.POSIXct(as.character(x)[miss], format = "%Y-%m-%d %H:%M:%OS", tz = "UTC")
  out
}

parse_timestamp_utc <- parse_utc

safe_numeric <- function(x) suppressWarnings(as.numeric(x))

floor_5m <- function(x) as.POSIXct(floor(as.numeric(x) / 300) * 300, origin = "1970-01-01", tz = "UTC")
ceil_5m <- function(x) as.POSIXct(ceiling(as.numeric(x) / 300) * 300, origin = "1970-01-01", tz = "UTC")

has_intraday_bar_cadence <- function(x, expected_seconds = 300) {
  timestamps <- sort(unique(parse_timestamp_utc(x)))
  timestamps <- timestamps[!is.na(timestamps)]
  if (length(timestamps) < 2) return(FALSE)
  gaps <- as.numeric(diff(timestamps), units = "secs")
  any(gaps > 0 & gaps <= expected_seconds * 1.5)
}

slugify <- function(x) {
  s <- tolower(gsub("[^A-Za-z0-9._-]+", "-", trimws(x)))
  s <- gsub("(^-+|-+$)", "", s)
  if (!nzchar(s)) stop("Could not create an asset slug.", call. = FALSE)
  s
}

asset_settings <- function() {
  xstock <- require_env("XSTOCK_SYMBOL")
  underlying <- require_env("UNDERLYING_SYMBOL")
  list(
    xstock = xstock,
    underlying = underlying,
    network = optional_env("XSTOCK_NETWORK", "Solana"),
    asset_id = xstock,
    slug = slugify(xstock),
    start_utc = optional_env("DATA_START_UTC", "2025-07-01T00:00:00Z"),
    end_utc = optional_env("DATA_END_UTC", "2026-09-20T23:59:59Z"),
    alpaca_feed = tolower(optional_env("ALPACA_FEED", "sip"))
  )
}

format_utc <- function(x) format(as.POSIXct(x, tz = "UTC"), tz = "UTC", format = "%Y-%m-%dT%H:%M:%SZ")

network_chain_index <- function(network) {
  key <- tolower(trimws(network))
  switch(
    key,
    "solana" = "501",
    "ethereum" = "1",
    stop(sprintf("Unsupported XSTOCK_NETWORK '%s'. This package currently pins Solana (501) or Ethereum (1).", network), call. = FALSE)
  )
}

sha256_file <- function(path) unname(digest::digest(file = path, algo = "sha256"))

flag_env <- function(name, default = FALSE) {
  v <- tolower(optional_env(name, if (default) "true" else "false"))
  v %in% c("1", "true", "yes", "on")
}
