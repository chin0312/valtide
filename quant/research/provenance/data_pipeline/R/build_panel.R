classify_us_session <- function(timestamp_utc) {
  et <- lubridate::with_tz(timestamp_utc, "America/New_York")
  dow <- lubridate::wday(et, week_start = 1)
  mins <- lubridate::hour(et) * 60 + lubridate::minute(et)
  out <- rep("closed", length(et))
  overnight <- (dow %in% 1:5 & mins < 240) | (dow %in% 1:4 & mins >= 1200) | (dow == 7 & mins >= 1200)
  premarket <- dow %in% 1:5 & mins >= 240 & mins < 570
  regular <- dow %in% 1:5 & mins >= 570 & mins < 960
  afterhours <- dow %in% 1:5 & mins >= 960 & mins < 1200
  out[overnight] <- "overnight"; out[premarket] <- "premarket"; out[regular] <- "regular"; out[afterhours] <- "afterhours"
  out
}

observation_age_minutes <- function(timestamp, observed) {
  age <- rep(NA_real_, length(timestamp)); last_seen <- as.POSIXct(NA, tz = "UTC")
  for (i in seq_along(timestamp)) {
    if (isTRUE(observed[i])) { last_seen <- timestamp[i]; age[i] <- 0 }
    else if (!is.na(last_seen)) age[i] <- as.numeric(difftime(timestamp[i], last_seen, units = "mins"))
  }
  age
}

build_canonical_panel <- function(underlying, token, settings) {
  stopifnot(data.table::is.data.table(underlying), data.table::is.data.table(token))
  underlying <- data.table::copy(underlying); token <- data.table::copy(token)
  underlying[, timestamp_utc := floor_5m(parse_timestamp_utc(timestamp_utc))]
  token[, timestamp_utc := floor_5m(parse_timestamp_utc(timestamp_utc))]
  if ("confirm" %in% names(token)) token <- token[confirm == 1L]
  underlying <- underlying[!is.na(close) & close > 0]; token <- token[!is.na(close) & close > 0]
  underlying <- underlying[order(timestamp_utc), .SD[.N], by = timestamp_utc]
  token <- token[order(timestamp_utc), .SD[.N], by = timestamp_utc]
  data.table::setnames(underlying, intersect(c("close", "volume", "vwap"), names(underlying)), paste0("underlying_", intersect(c("close", "volume", "vwap"), names(underlying))))
  data.table::setnames(token, intersect(c("close", "volume", "volume_usd"), names(token)), paste0("token_", intersect(c("close", "volume", "volume_usd"), names(token))))
  start <- min(c(underlying$timestamp_utc, token$timestamp_utc), na.rm = TRUE); end <- max(c(underlying$timestamp_utc, token$timestamp_utc), na.rm = TRUE)
  grid <- data.table::data.table(timestamp_utc = seq(floor_5m(start), ceil_5m(end), by = "5 min"))
  keep_u <- intersect(c("timestamp_utc", "underlying_close", "underlying_volume", "underlying_vwap"), names(underlying))
  keep_t <- intersect(c("timestamp_utc", "token_close", "token_volume", "token_volume_usd"), names(token))
  panel <- merge(grid, underlying[, ..keep_u], by = "timestamp_utc", all.x = TRUE)
  panel <- merge(panel, token[, ..keep_t], by = "timestamp_utc", all.x = TRUE)
  panel[, underlying_available := !is.na(underlying_close)]
  panel[, token_available := !is.na(token_close)]
  panel[, underlying_log_price := data.table::fifelse(underlying_available, log(underlying_close), NA_real_)]
  panel[, token_log_price := data.table::fifelse(token_available, log(token_close), NA_real_)]
  panel[, session_state := classify_us_session(timestamp_utc)]
  panel[, token_observation_age_min := observation_age_minutes(timestamp_utc, token_available)]
  panel[, time_since_underlying_min := observation_age_minutes(timestamp_utc, underlying_available)]
  panel[, `:=`(asset_id = settings$asset_id, xstock_symbol = settings$xstock, underlying_symbol = settings$underlying)]

  # Compatibility aliases expected by the existing P1a/P1a-C model suite.
  # These names are an interface convention only; for TSLAx, nvda_close contains TSLA, etc.
  panel[, `:=`(
    nvda_close = underlying_close,
    nvdax_close = token_close,
    nvda_available = underlying_available,
    nvdax_available = token_available,
    nvda_log_price = underlying_log_price,
    nvdax_log_price = token_log_price,
    nvdax_observation_age_min = token_observation_age_min,
    time_since_nvda_min = time_since_underlying_min
  )]
  if ("underlying_volume" %in% names(panel)) panel[, nvda_volume := underlying_volume]
  if ("underlying_vwap" %in% names(panel)) panel[, nvda_vwap := underlying_vwap]
  if ("token_volume" %in% names(panel)) panel[, nvdax_volume := token_volume]
  if ("token_volume_usd" %in% names(panel)) panel[, nvdax_volume_usd := token_volume_usd]
  data.table::setorder(panel, timestamp_utc); panel[]
}

audit_panel <- function(panel) data.table::data.table(
  metric = c("rows_5m", "underlying_observations", "token_observations", "overlap_observations", "token_only_observations", "no_observation_rows", "weekend_token_observations"),
  value = c(nrow(panel), sum(panel$underlying_available), sum(panel$token_available), panel[underlying_available & token_available, .N], panel[!underlying_available & token_available, .N], panel[!underlying_available & !token_available, .N], panel[session_state == "closed", sum(token_available)])
)
