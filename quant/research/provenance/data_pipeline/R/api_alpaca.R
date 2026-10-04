alpaca_stock_bars <- function(
  symbol = "NVDA",
  start_utc,
  end_utc,
  timeframe = "5Min",
  feed = Sys.getenv("ALPACA_FEED", unset = "sip"),
  adjustment = "raw"
) {
  key <- require_env("ALPACA_API_KEY")
  secret <- require_env("ALPACA_SECRET_KEY")

  base_url <- sprintf("https://data.alpaca.markets/v2/stocks/%s/bars", symbol)
  page_token <- NULL
  out <- list()
  page <- 1L

  repeat {
    req <- httr2::request(base_url) |>
      httr2::req_headers(
        `APCA-API-KEY-ID` = key,
        `APCA-API-SECRET-KEY` = secret
      ) |>
      httr2::req_url_query(
        timeframe = timeframe,
        start = start_utc,
        end = end_utc,
        limit = 10000,
        adjustment = adjustment,
        feed = feed,
        sort = "asc",
        page_token = page_token
      ) |>
      httr2::req_retry(max_tries = 5)

    resp <- tryCatch(
      httr2::req_perform(req),
      error = function(e) {
        stop(
          paste0(
            "Alpaca request failed. If you used feed='sip', make sure the requested ",
            "end time is outside the latest restricted window for your plan. Original error: ",
            conditionMessage(e)
          ),
          call. = FALSE
        )
      }
    )

    body <- httr2::resp_body_json(resp, simplifyVector = TRUE)

    if (!is.null(body$bars) && length(body$bars) > 0) {
      bars <- data.table::as.data.table(body$bars)
      out[[length(out) + 1L]] <- bars
      message(sprintf("Alpaca page %d: %d bars", page, nrow(bars)))
    }

    page_token <- body$next_page_token
    if (is.null(page_token) || !nzchar(page_token)) break

    page <- page + 1L
    Sys.sleep(0.05)
  }

  if (length(out) == 0) return(data.table::data.table())

  dt <- data.table::rbindlist(out, fill = TRUE)

  # Alpaca bar field names are typically:
  # t timestamp, o/h/l/c OHLC, v volume, n trade count, vw VWAP.
  rename_map <- c(
    t = "timestamp_utc",
    o = "open",
    h = "high",
    l = "low",
    c = "close",
    v = "volume",
    n = "trade_count",
    vw = "vwap"
  )

  for (old in names(rename_map)) {
    if (old %in% names(dt)) {
      data.table::setnames(dt, old, rename_map[[old]])
    }
  }

  raw_timestamps <- dt$timestamp_utc
  dt[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]
  if (any(is.na(dt$timestamp_utc) & !is.na(raw_timestamps))) {
    stop("Alpaca returned a timestamp that could not be parsed as UTC.", call. = FALSE)
  }

  if (identical(tolower(timeframe), "5min") &&
      nrow(dt) > 1 &&
      !has_intraday_bar_cadence(dt$timestamp_utc, expected_seconds = 300)) {
    stop(
      "Alpaca's 5-minute response has no intraday 5-minute cadence; refusing to cache it.",
      call. = FALSE
    )
  }

  numeric_cols <- intersect(
    c("open", "high", "low", "close", "volume", "trade_count", "vwap"),
    names(dt)
  )
  for (col in numeric_cols) dt[, (col) := safe_numeric(get(col))]

  dt[, symbol := symbol]
  dt[, feed := feed]
  data.table::setorder(dt, timestamp_utc)
  unique(dt, by = "timestamp_utc")
}
