parse_utc <- function(x) {
  if (inherits(x, "POSIXct")) return(as.POSIXct(x, tz = "UTC"))
  x <- as.character(x)
  out <- as.POSIXct(x, format = "%Y-%m-%dT%H:%M:%OSZ", tz = "UTC")
  miss <- is.na(out)
  if (any(miss)) out[miss] <- as.POSIXct(x[miss], format = "%Y-%m-%d %H:%M:%OS", tz = "UTC")
  out
}

as_utc <- function(x) parse_utc(x)

as_bool <- function(x) {
  if (is.logical(x)) return(x)
  if (is.numeric(x)) return(x != 0)
  tolower(as.character(x)) %in% c("true", "t", "1", "yes", "y")
}

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x

comma_list <- function(x) {
  if (!nzchar(x)) return(character())
  trimws(strsplit(x, ",", fixed = TRUE)[[1]])
}

safe_sd <- function(x) {
  s <- stats::sd(x, na.rm = TRUE)
  if (!is.finite(s) || s < 1e-12) 1 else s
}

bps <- function(log_error) 10000 * log_error

canonical_sessions <- c("regular", "premarket", "afterhours", "overnight", "closed")

ordered_sessions <- function(x) {
  x <- unique(as.character(x[!is.na(x)]))
  c(intersect(canonical_sessions, x), sort(setdiff(x, canonical_sessions)))
}

classify_us_session <- function(timestamp_utc) {
  et <- as.POSIXlt(timestamp_utc, tz = "America/New_York")
  # POSIXlt wday: Sunday=0 ... Saturday=6
  wday <- et$wday
  mins <- et$hour * 60 + et$min
  out <- rep("closed", length(timestamp_utc))

  weekday <- wday %in% 1:5
  out[weekday & mins >= 240 & mins < 570] <- "premarket"
  out[weekday & mins >= 570 & mins < 960] <- "regular"
  out[weekday & mins >= 960 & mins < 1200] <- "afterhours"

  # Generic overnight label for observations outside pre/regular/post where a
  # provider may still have an overnight print. True no-observation rows remain closed.
  out[weekday & mins < 240] <- "overnight"
  out[weekday & mins >= 1200] <- "overnight"
  out[wday == 0 & mins >= 1200] <- "overnight"
  out
}

locf_vec <- function(x) {
  out <- x
  last <- NA_real_
  for (i in seq_along(out)) {
    if (is.finite(out[i])) last <- out[i] else out[i] <- last
  }
  out
}
