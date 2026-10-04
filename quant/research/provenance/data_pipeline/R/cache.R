manifest_path <- function(raw_dir) file.path(raw_dir, "cache_manifest.json")

read_manifest <- function(raw_dir) {
  path <- manifest_path(raw_dir)
  if (!file.exists(path)) return(list(version = 1L))
  tryCatch(jsonlite::read_json(path, simplifyVector = FALSE), error = function(e) stop("Cannot read cache manifest: ", conditionMessage(e), call. = FALSE))
}

write_manifest <- function(x, raw_dir) {
  dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)
  x$version <- 1L; x$updated_at_utc <- format_utc(Sys.time())
  jsonlite::write_json(x, manifest_path(raw_dir), auto_unbox = TRUE, pretty = TRUE, null = "null")
}

entry_value <- function(entry, name) {
  x <- entry[[name]]
  if (is.null(x) || !length(x)) return(NA_character_)
  as.character(x[[1]])
}

entry_identity_matches <- function(entry, identity) {
  if (is.null(entry)) return(FALSE)
  all(vapply(names(identity), function(nm) identical(entry_value(entry, nm), as.character(identity[[nm]])), logical(1)))
}

entry_file_valid <- function(entry, raw_dir) {
  if (is.null(entry)) return(FALSE)
  rel <- entry_value(entry, "path"); hash <- entry_value(entry, "sha256")
  if (is.na(rel) || is.na(hash)) return(FALSE)
  path <- file.path(raw_dir, rel)
  file.exists(path) && identical(sha256_file(path), hash)
}

missing_windows <- function(entry, start_time, end_time) {
  if (is.null(entry)) return(list(list(start = start_time, end = end_time)))
  cs <- parse_utc(entry_value(entry, "queried_start_utc")); ce <- parse_utc(entry_value(entry, "queried_end_utc"))
  if (is.na(cs) || is.na(ce)) return(list(list(start = start_time, end = end_time)))
  out <- list()
  if (start_time < cs) out[[length(out) + 1L]] <- list(start = start_time, end = min(end_time, cs - 1))
  if (end_time > ce) out[[length(out) + 1L]] <- list(start = max(start_time, ce + 1), end = end_time)
  Filter(function(w) w$start <= w$end, out)
}

merge_rows <- function(existing, downloaded) {
  dt <- data.table::rbindlist(list(existing, downloaded), fill = TRUE)
  if (!nrow(dt)) return(dt)
  dt[, timestamp_utc := parse_timestamp_utc(timestamp_utc)]
  dt <- dt[!is.na(timestamp_utc)]
  data.table::setorder(dt, timestamp_utc)
  unique(dt, by = "timestamp_utc", fromLast = TRUE)
}

write_csv_atomic <- function(dt, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  tmp <- tempfile("valtide-cache-", tmpdir = dirname(path), fileext = ".csv")
  on.exit(unlink(tmp), add = TRUE)
  data.table::fwrite(dt, tmp)
  if (!file.copy(tmp, path, overwrite = TRUE)) stop("Could not write cache file: ", path, call. = FALSE)
}

make_entry <- function(path, queried_start, queried_end, identity, dt) {
  ts <- if (nrow(dt)) parse_timestamp_utc(dt$timestamp_utc) else as.POSIXct(character(), tz = "UTC")
  c(identity, list(
    path = basename(path),
    sha256 = sha256_file(path),
    rows = nrow(dt),
    queried_start_utc = format_utc(queried_start),
    queried_end_utc = format_utc(queried_end),
    data_start_utc = if (length(ts) && any(!is.na(ts))) format_utc(min(ts, na.rm = TRUE)) else NULL,
    data_end_utc = if (length(ts) && any(!is.na(ts))) format_utc(max(ts, na.rm = TRUE)) else NULL
  ))
}
