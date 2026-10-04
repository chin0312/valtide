`%||%` <- function(x, y) if (is.null(x)) y else x

okx_query_string <- function(params) {
  if (!length(params)) return("")
  keep <- !vapply(params, function(x) is.null(x) || !length(x) || !nzchar(as.character(x)), logical(1))
  params <- params[keep]
  if (!length(params)) return("")
  parts <- vapply(names(params), function(k) paste0(utils::URLencode(k, reserved = TRUE), "=", utils::URLencode(as.character(params[[k]]), reserved = TRUE)), character(1))
  paste0("?", paste(parts, collapse = "&"))
}

okx_timestamp <- function() format(Sys.time(), tz = "UTC", format = "%Y-%m-%dT%H:%M:%OS3Z")

okx_sign <- function(message, secret) {
  raw_sig <- digest::hmac(key = secret, object = message, algo = "sha256", serialize = FALSE, raw = TRUE)
  openssl::base64_encode(raw_sig)
}

# Local-only raw HTTP capture. The exact response BODY bytes are written before
# parsing. Authentication headers / API keys / signatures / passphrases are never
# written to disk. The companion metadata file contains only safe request fields.
.okx_capture_state <- new.env(parent = emptyenv())
.okx_capture_state$seq <- 0L

okx_capture_response <- function(raw_body, path, params, status, request_timestamp, capture_dir, capture_label = NULL) {
  if (is.null(capture_dir) || !nzchar(capture_dir)) return(invisible(NULL))
  dir.create(capture_dir, recursive = TRUE, showWarnings = FALSE)

  .okx_capture_state$seq <- .okx_capture_state$seq + 1L
  seq_id <- .okx_capture_state$seq
  stamp <- gsub("[^0-9A-Za-z]+", "", request_timestamp)
  label <- capture_label %||% basename(path)
  label <- gsub("[^A-Za-z0-9._-]+", "-", label)
  request_hash <- substr(
    digest::digest(
      paste(request_timestamp, path, okx_query_string(params), seq_id, sep = "|"),
      algo = "sha256",
      serialize = FALSE
    ),
    1,
    12
  )
  stem <- sprintf("%s_%04d_%s_%s", stamp, seq_id, label, request_hash)
  body_path <- file.path(capture_dir, paste0(stem, ".json"))
  meta_path <- file.path(capture_dir, paste0(stem, ".meta.json"))

  con <- file(body_path, open = "wb")
  on.exit(close(con), add = TRUE)
  writeBin(raw_body, con)
  close(con)
  on.exit(NULL, add = FALSE)

  metadata <- list(
    captured_at_utc = okx_timestamp(),
    request_timestamp_utc = request_timestamp,
    method = "GET",
    host = "https://web3.okx.com",
    path = path,
    params = params,
    http_status = as.integer(status),
    response_body_file = basename(body_path),
    response_body_sha256 = digest::digest(raw_body, algo = "sha256", serialize = FALSE),
    authentication_material_saved = FALSE
  )
  jsonlite::write_json(metadata, meta_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  message("Saved LOCAL raw OKX response: ", body_path)
  invisible(body_path)
}

okx_get <- function(path, params = list(), capture_dir = NULL, capture_label = NULL) {
  api_key <- require_env("OKX_API_KEY")
  secret <- require_env("OKX_SECRET_KEY")
  passphrase <- require_env("OKX_PASSPHRASE")
  query <- okx_query_string(params)
  path_with_query <- paste0(path, query)
  timestamp <- okx_timestamp()
  signature <- okx_sign(paste0(timestamp, "GET", path_with_query), secret)
  req <- httr2::request(paste0("https://web3.okx.com", path_with_query)) |>
    httr2::req_headers(`OK-ACCESS-KEY` = api_key, `OK-ACCESS-SIGN` = signature, `OK-ACCESS-TIMESTAMP` = timestamp, `OK-ACCESS-PASSPHRASE` = passphrase) |>
    httr2::req_retry(max_tries = 5) |>
    httr2::req_error(is_error = function(resp) FALSE)
  resp <- httr2::req_perform(req)
  status <- httr2::resp_status(resp)

  # Save exactly the response body bytes that are subsequently parsed. This is
  # deliberately done before API-code/status validation so error responses can
  # also be audited locally.
  raw_body <- httr2::resp_body_raw(resp)
  okx_capture_response(raw_body, path, params, status, timestamp, capture_dir, capture_label)

  if (status == 402) stop("OKX Market API quota/payment is required.", call. = FALSE)
  if (status >= 400) stop(sprintf("OKX HTTP request failed with status %d.", status), call. = FALSE)
  if (!length(raw_body)) stop("OKX returned an empty response body.", call. = FALSE)

  body <- jsonlite::fromJSON(rawToChar(raw_body), simplifyVector = FALSE)
  if (is.null(body$code) || body$code != "0") stop(sprintf("OKX API error. code=%s msg=%s", body$code %||% "NULL", body$msg %||% ""), call. = FALSE)
  body$data
}

okx_rwa_tokens <- function(issuer = "36", category = "47", limit = 100L) {
  path <- "/api/v6/dex/market/rwa/tokens"
  cursor <- NULL; out <- list(); page <- 1L
  repeat {
    data <- okx_get(path, list(issuer = issuer, category = category, limit = as.character(limit), cursor = cursor))
    rows <- data$list
    if (!is.null(rows) && length(rows)) {
      page_dt <- data.table::rbindlist(rows, fill = TRUE); page_dt[, page := page]
      out[[length(out) + 1L]] <- page_dt
    }
    cursor <- data$cursor
    if (is.null(cursor) || !nzchar(cursor)) break
    page <- page + 1L
  }
  if (!length(out)) return(data.table::data.table())
  data.table::rbindlist(out, fill = TRUE)
}

discover_xstock <- function(xstock_symbol, underlying_symbol = sub("x$", "", xstock_symbol, ignore.case = TRUE)) {
  dt <- okx_rwa_tokens()
  if (!nrow(dt)) stop("OKX RWA list returned no xStocks.", call. = FALSE)
  token_col <- if ("tokenSymbol" %in% names(dt)) as.character(dt$tokenSymbol) else rep("", nrow(dt))
  stock_col <- if ("stockCode" %in% names(dt)) as.character(dt$stockCode) else rep("", nrow(dt))
  keep <- toupper(token_col) == toupper(xstock_symbol) | toupper(stock_col) %in% toupper(c(underlying_symbol, xstock_symbol))
  matches <- dt[which(keep)]
  if (!nrow(matches)) stop(sprintf("%s / %s was not found in the OKX RWA token list.", xstock_symbol, underlying_symbol), call. = FALSE)
  if ("volume24h" %in% names(matches)) {
    matches[, volume24h_num := safe_numeric(volume24h)]
    data.table::setorder(matches, -volume24h_num)
  }
  matches
}

okx_historical_candles <- function(chain_index, token_address, start_utc, end_utc, bar = "5m", limit = 299L, capture_dir = NULL) {
  path <- "/api/v6/dex/market/historical-candles"
  start_ts <- parse_utc(start_utc); end_ts <- parse_utc(end_utc)
  start_ms <- as.numeric(start_ts) * 1000; end_ms <- as.numeric(end_ts) * 1000
  after <- format(end_ms + 1, scientific = FALSE, trim = TRUE)
  chunks <- list(); seen_oldest <- Inf; request_n <- 0L
  repeat {
    request_n <- request_n + 1L
    data <- okx_get(
      path,
      list(chainIndex = as.character(chain_index), tokenContractAddress = token_address, after = after, bar = bar, limit = as.character(limit)),
      capture_dir = capture_dir,
      capture_label = sprintf("historical-candles-page-%04d", request_n)
    )
    if (is.null(data) || !length(data)) break
    rows <- data.table::rbindlist(lapply(data, function(x) data.table::as.data.table(as.list(stats::setNames(unlist(x, use.names = FALSE), c("ts", "open", "high", "low", "close", "volume", "volume_usd", "confirm"))))), fill = TRUE)
    rows[, ts_ms := safe_numeric(ts)]; rows <- rows[!is.na(ts_ms)]
    if (!nrow(rows)) break
    chunks[[length(chunks) + 1L]] <- rows
    oldest <- min(rows$ts_ms, na.rm = TRUE)
    message(sprintf("OKX page %d: oldest=%s", request_n, format(as.POSIXct(oldest / 1000, origin = "1970-01-01", tz = "UTC"), tz = "UTC")))
    if (oldest <= start_ms) break
    if (!is.finite(oldest) || oldest >= seen_oldest) { warning("OKX pagination stopped because the oldest timestamp did not move backward."); break }
    seen_oldest <- oldest; after <- format(oldest, scientific = FALSE, trim = TRUE); Sys.sleep(0.08)
  }
  if (!length(chunks)) return(data.table::data.table())
  dt <- data.table::rbindlist(chunks, fill = TRUE); dt <- unique(dt, by = "ts_ms"); dt <- dt[ts_ms >= start_ms & ts_ms <= end_ms]
  for (col in intersect(c("open", "high", "low", "close", "volume", "volume_usd"), names(dt))) dt[, (col) := safe_numeric(get(col))]
  dt[, timestamp_utc := as.POSIXct(ts_ms / 1000, origin = "1970-01-01", tz = "UTC")]
  if ("confirm" %in% names(dt)) dt[, confirm := as.integer(confirm)]
  data.table::setorder(dt, timestamp_utc); dt[]
}
