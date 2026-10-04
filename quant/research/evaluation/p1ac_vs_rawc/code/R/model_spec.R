make_model_spec <- function(train, factor_cols, quality_cols) {
  sessions <- ordered_sessions(train$session_state)
  if (length(sessions) == 0) sessions <- "all"

  center_scale <- function(cols) {
    if (length(cols) == 0) return(list(cols = character(), center = numeric(), scale = numeric()))
    center <- vapply(cols, function(nm) mean(train[[nm]], na.rm = TRUE), numeric(1))
    scale <- vapply(cols, function(nm) safe_sd(train[[nm]]), numeric(1))
    keep <- is.finite(center) & is.finite(scale) & scale > 1e-12
    list(cols = cols[keep], center = center[keep], scale = scale[keep])
  }

  list(
    sessions = sessions,
    factors = center_scale(factor_cols),
    quality = center_scale(quality_cols)
  )
}

standardize_cols <- function(dt, obj) {
  if (length(obj$cols) == 0) return(matrix(numeric(), nrow = nrow(dt), ncol = 0))
  z <- sapply(seq_along(obj$cols), function(i) {
    x <- as.numeric(dt[[obj$cols[i]]])
    x <- (x - obj$center[i]) / obj$scale[i]
    x[!is.finite(x)] <- 0
    x
  })
  if (is.null(dim(z))) z <- matrix(z, ncol = 1)
  colnames(z) <- obj$cols
  z
}

prepare_model_data <- function(dt, spec, hide_nvda = FALSE) {
  sess <- match(dt$session_state, spec$sessions)
  sess[is.na(sess)] <- match("closed", spec$sessions)
  sess[is.na(sess)] <- 1L

  list(
    timestamp = dt$timestamp_utc,
    y_nvda = if (hide_nvda) rep(NA_real_, nrow(dt)) else as.numeric(dt$nvda_log_price),
    y_nvdax = as.numeric(dt$nvdax_log_price),
    session = as.integer(sess),
    X = standardize_cols(dt, spec$factors),
    Zq = standardize_cols(dt, spec$quality)
  )
}

initial_m <- function(data) {
  for (i in seq_along(data$y_nvda)) {
    obs <- c(data$y_nvda[i], data$y_nvdax[i])
    obs <- obs[is.finite(obs)]
    if (length(obs)) return(mean(obs))
  }
  stop("No finite price observations.")
}
