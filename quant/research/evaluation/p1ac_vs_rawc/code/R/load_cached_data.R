load_optional_table <- function(path) {
  if (!file.exists(path)) return(NULL)
  x <- data.table::fread(path)
  if (!"timestamp_utc" %in% names(x)) stop(path, " must contain timestamp_utc")
  x[, timestamp_utc := as_utc(timestamp_utc)]
  x
}

strip_legacy_filter_cols <- function(dt) {
  drop <- intersect(c("m_pred", "P_pred", "m_filt", "P_filt", "loglik_t", "observations_used", "fair_value", "state_sd_log", "fair_value_lo90", "fair_value_hi90"), names(dt))
  if (length(drop)) dt[, (drop) := NULL]
  dt
}

map_generic_to_p1a_aliases <- function(dt) {
  aliases <- c(
    underlying_close = "nvda_close",
    token_close = "nvdax_close",
    underlying_available = "nvda_available",
    token_available = "nvdax_available",
    underlying_log_price = "nvda_log_price",
    token_log_price = "nvdax_log_price",
    underlying_volume = "nvda_volume",
    underlying_vwap = "nvda_vwap",
    token_volume = "nvdax_volume",
    token_volume_usd = "nvdax_volume_usd",
    token_observation_age_min = "nvdax_observation_age_min",
    time_since_underlying_min = "time_since_nvda_min"
  )
  for (src in names(aliases)) {
    dst <- aliases[[src]]
    if (!dst %in% names(dt) && src %in% names(dt)) dt[, (dst) := get(src)]
  }
  dt
}

load_cached_panel <- function(cache_dir = Sys.getenv("VALTIDE_CACHE_DIR", unset = "data/cache")) {
  generic <- file.path(cache_dir, "canonical_panel_5m.csv")
  canonical <- file.path(cache_dir, "p0_panel_5m.csv")
  legacy_train <- file.path(cache_dir, "p0_train_filtered.csv")
  legacy_test <- file.path(cache_dir, "p0_test_filtered.csv")

  if (file.exists(generic)) {
    dt <- data.table::fread(generic); dt[, legacy_split := NA_character_]
  } else if (file.exists(canonical)) {
    dt <- data.table::fread(canonical); dt[, legacy_split := NA_character_]
  } else if (file.exists(legacy_train) && file.exists(legacy_test)) {
    tr <- strip_legacy_filter_cols(data.table::fread(legacy_train)); te <- strip_legacy_filter_cols(data.table::fread(legacy_test))
    tr[, legacy_split := "train"]; te[, legacy_split := "test"]
    dt <- data.table::rbindlist(list(tr, te), fill = TRUE)
  } else stop("No cached panel found in ", cache_dir, call. = FALSE)

  dt <- map_generic_to_p1a_aliases(dt)
  required_price <- c("timestamp_utc", "nvda_close", "nvdax_close")
  missing <- setdiff(required_price, names(dt))
  if (length(missing)) stop("Dataset is missing P1a-required fields: ", paste(missing, collapse = ", "), call. = FALSE)

  dt[, timestamp_utc := as_utc(timestamp_utc)]
  data.table::setorder(dt, timestamp_utc); dt <- unique(dt, by = "timestamp_utc")
  if (!"nvda_available" %in% names(dt)) dt[, nvda_available := is.finite(nvda_close)]
  if (!"nvdax_available" %in% names(dt)) dt[, nvdax_available := is.finite(nvdax_close)]
  dt[, nvda_available := as_bool(nvda_available)]; dt[, nvdax_available := as_bool(nvdax_available)]
  if (!"nvda_log_price" %in% names(dt)) dt[, nvda_log_price := ifelse(nvda_available & nvda_close > 0, log(nvda_close), NA_real_)]
  if (!"nvdax_log_price" %in% names(dt)) dt[, nvdax_log_price := ifelse(nvdax_available & nvdax_close > 0, log(nvdax_close), NA_real_)]
  if (!"session_state" %in% names(dt)) dt[, session_state := classify_us_session(timestamp_utc)]
  dt[, session_state := as.character(session_state)]

  factors <- load_optional_table(file.path(cache_dir, "factors_5m.csv"))
  if (!is.null(factors)) {
    other <- setdiff(names(factors), "timestamp_utc")
    for (nm in other) if (is.numeric(factors[[nm]]) && !startsWith(nm, "factor_")) data.table::setnames(factors, nm, paste0("factor_", nm))
    dt <- merge(dt, factors, by = "timestamp_utc", all.x = TRUE, sort = FALSE)
  }
  quality <- load_optional_table(file.path(cache_dir, "market_quality_5m.csv"))
  if (!is.null(quality)) dt <- merge(dt, quality, by = "timestamp_utc", all.x = TRUE, sort = FALSE)
  data.table::setorder(dt, timestamp_utc); dt
}

add_derived_features <- function(dt) {
  dt <- data.table::copy(dt); n <- nrow(dt)
  if (n < 2) return(dt)
  prev_ok <- c(FALSE, dt$nvdax_available[-n]); exact_5m <- c(FALSE, diff(as.numeric(dt$timestamp_utc)) == 300)
  r <- c(NA_real_, diff(dt$nvdax_log_price)); r[!(dt$nvdax_available & prev_ok & exact_5m)] <- NA_real_
  dt[, nvdax_return_5m := r]; dt[, nvdax_abs_return_lag1 := data.table::shift(abs(nvdax_return_5m), 1L)]
  sq <- r^2; dt[, nvdax_rv_30m_lag1 := sqrt(data.table::frollsum(data.table::shift(sq, 1L), n = 6L, align = "right", na.rm = TRUE))]
  if ("nvdax_volume" %in% names(dt)) dt[, nvdax_log_volume_lag1 := data.table::shift(log1p(pmax(nvdax_volume, 0)), 1L)]
  if ("nvdax_volume_usd" %in% names(dt)) dt[, nvdax_log_usd_volume_lag1 := data.table::shift(log1p(pmax(nvdax_volume_usd, 0)), 1L)]
  dt
}

split_cached_panel <- function(dt, config) {
  legacy <- !all(is.na(dt$legacy_split)) && any(dt$legacy_split == "train") && any(dt$legacy_split == "test")
  if (legacy) {
    train <- dt[legacy_split == "train"]; test <- dt[legacy_split == "test"]; split_desc <- "legacy cached split"
  } else if (nzchar(config$train_end_utc)) {
    cutoff <- parse_utc(config$train_end_utc); train <- dt[timestamp_utc <= cutoff]; test <- dt[timestamp_utc > cutoff]; split_desc <- paste("TRAIN_END_UTC", config$train_end_utc)
  } else {
    idx <- max(100L, floor(0.80 * nrow(dt))); cutoff <- dt$timestamp_utc[idx]
    train <- dt[timestamp_utc <= cutoff]; test <- dt[timestamp_utc > cutoff]; split_desc <- "80/20 chronological split"
  }
  if (nrow(train) < 100 || nrow(test) < 20) stop("Train/test split is too small.")
  list(train = train, test = test, description = split_desc)
}

detect_feature_cols <- function(train, config) {
  env_factors <- comma_list(Sys.getenv("VALTIDE_FACTOR_COLS", unset = "")); factor_cols <- if (length(env_factors)) env_factors else config$factor_cols
  if (is.null(factor_cols)) factor_cols <- grep("^factor_", names(train), value = TRUE)
  factor_cols <- factor_cols[factor_cols %in% names(train)]; factor_cols <- factor_cols[vapply(train[, ..factor_cols], is.numeric, logical(1))]
  if (length(factor_cols) > config$max_factors) factor_cols <- factor_cols[seq_len(config$max_factors)]
  env_quality <- comma_list(Sys.getenv("VALTIDE_QUALITY_COLS", unset = "")); quality_cols <- if (length(env_quality)) env_quality else config$quality_cols
  if (is.null(quality_cols)) quality_cols <- intersect(c("nvdax_log_volume_lag1", "nvdax_log_usd_volume_lag1", "nvdax_abs_return_lag1", "nvdax_rv_30m_lag1"), names(train))
  quality_cols <- quality_cols[quality_cols %in% names(train)]; quality_cols <- quality_cols[vapply(train[, ..quality_cols], is.numeric, logical(1))]
  if (length(quality_cols) > config$max_quality) quality_cols <- quality_cols[seq_len(config$max_quality)]
  list(factor_cols = factor_cols, quality_cols = quality_cols)
}
