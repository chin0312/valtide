next_observed_nvda <- function(dt) {
  n <- nrow(dt)
  next_log <- rep(NA_real_, n)
  next_time <- as.POSIXct(rep(NA_real_, n), origin = "1970-01-01", tz = "UTC")
  seen_log <- NA_real_
  seen_time <- as.POSIXct(NA, tz = "UTC")
  for (i in n:1) {
    next_log[i] <- seen_log
    next_time[i] <- seen_time
    if (is.finite(dt$nvda_log_price[i])) {
      seen_log <- dt$nvda_log_price[i]
      seen_time <- dt$timestamp_utc[i]
    }
  }
  list(log = next_log, time = next_time)
}

previous_observed_nvda <- function(dt) {
  locf_vec(dt$nvda_log_price)
}

error_metrics <- function(pred, truth) {
  ok <- is.finite(pred) & is.finite(truth)
  if (!any(ok)) return(c(n = 0, MAE_bps = NA, RMSE_bps = NA))
  e <- pred[ok] - truth[ok]
  c(n = sum(ok), MAE_bps = 10000 * mean(abs(e)), RMSE_bps = 10000 * sqrt(mean(e^2)))
}

evaluate_fitted_model <- function(fit, model_id, test_dt, spec, config) {
  normal_data <- prepare_model_data(test_dt, spec, hide_nvda = FALSE)
  normal <- run_state_filter(
    model_id, fit$par, normal_data, spec,
    init_state = fit$train_filter$final_state,
    init_P = fit$train_filter$final_P,
    return_states = TRUE, interval_level = config$interval_level
  )

  masked_data <- prepare_model_data(test_dt, spec, hide_nvda = TRUE)
  masked <- run_state_filter(
    model_id, fit$par, masked_data, spec,
    init_state = fit$train_filter$final_state,
    init_P = fit$train_filter$final_P,
    return_states = TRUE, interval_level = config$interval_level
  )

  overlap <- is.finite(test_dt$nvda_log_price) & is.finite(test_dt$nvdax_log_price)
  raw_masked <- error_metrics(test_dt$nvdax_log_price[overlap], test_dt$nvda_log_price[overlap])
  model_masked <- error_metrics(masked$states$m_filt[overlap], test_dt$nvda_log_price[overlap])

  nxt <- next_observed_nvda(test_dt)
  closed_rows <- !is.finite(test_dt$nvda_log_price) & is.finite(test_dt$nvdax_log_price) & is.finite(nxt$log)
  stale <- previous_observed_nvda(test_dt)
  raw_closed <- error_metrics(test_dt$nvdax_log_price[closed_rows], nxt$log[closed_rows])
  stale_closed <- error_metrics(stale[closed_rows], nxt$log[closed_rows])
  model_closed <- error_metrics(normal$states$m_filt[closed_rows], nxt$log[closed_rows])

  detail <- data.table::data.table(
    timestamp_utc = test_dt$timestamp_utc,
    session_state = test_dt$session_state,
    nvda_log_price = test_dt$nvda_log_price,
    nvdax_log_price = test_dt$nvdax_log_price,
    model_log_fair = normal$states$m_filt,
    model_fair_value = normal$states$fair_value,
    model_P = normal$states$P_filt,
    masked_log_fair = masked$states$m_filt,
    innov_z_nvda = normal$states$innov_z_nvda,
    innov_z_nvdax = normal$states$innov_z_nvdax,
    next_nvda_log = nxt$log,
    next_nvda_time = nxt$time
  )
  detail[, horizon_to_next_nvda_min := as.numeric(difftime(next_nvda_time, timestamp_utc, units = "mins"))]

  session_diag <- detail[, .(
    n_nvda_innov = sum(is.finite(innov_z_nvda)),
    mean_z_nvda = mean(innov_z_nvda, na.rm = TRUE),
    sd_z_nvda = stats::sd(innov_z_nvda, na.rm = TRUE),
    n_nvdax_innov = sum(is.finite(innov_z_nvdax)),
    mean_z_nvdax = mean(innov_z_nvdax, na.rm = TRUE),
    sd_z_nvdax = stats::sd(innov_z_nvdax, na.rm = TRUE)
  ), by = session_state]
  session_diag[, model := model_id]

  list(
    normal = normal,
    masked = masked,
    detail = detail,
    session_diag = session_diag,
    summary = data.table::data.table(
      model = model_id,
      test_logLik = normal$loglik,
      masked_n = model_masked[["n"]],
      masked_MAE_bps = model_masked[["MAE_bps"]],
      masked_RMSE_bps = model_masked[["RMSE_bps"]],
      raw_nvdax_masked_MAE_bps = raw_masked[["MAE_bps"]],
      raw_nvdax_masked_RMSE_bps = raw_masked[["RMSE_bps"]],
      closed_n = model_closed[["n"]],
      closed_MAE_bps = model_closed[["MAE_bps"]],
      closed_RMSE_bps = model_closed[["RMSE_bps"]],
      raw_nvdax_closed_MAE_bps = raw_closed[["MAE_bps"]],
      raw_nvdax_closed_RMSE_bps = raw_closed[["RMSE_bps"]],
      stale_nvda_closed_MAE_bps = stale_closed[["MAE_bps"]],
      stale_nvda_closed_RMSE_bps = stale_closed[["RMSE_bps"]]
    )
  )
}

parameter_table <- function(fit) {
  d <- fit$decoded
  rows <- list()
  for (nm in names(d$q_by_session)) rows[[length(rows)+1]] <- data.table::data.table(group="Q", name=nm, value=d$q_by_session[[nm]])
  rows[[length(rows)+1]] <- data.table::data.table(group="R_nvda", name="constant", value=d$r_nvda)
  for (nm in names(d$r_nvdax_by_session)) rows[[length(rows)+1]] <- data.table::data.table(group="R_nvdax", name=nm, value=d$r_nvdax_by_session[[nm]])
  for (nm in names(d$theta_by_session)) rows[[length(rows)+1]] <- data.table::data.table(group="theta", name=nm, value=d$theta_by_session[[nm]])
  if (length(d$beta)) for (nm in names(d$beta)) rows[[length(rows)+1]] <- data.table::data.table(group="beta", name=nm, value=d$beta[[nm]])
  if (length(d$gamma)) for (nm in names(d$gamma)) rows[[length(rows)+1]] <- data.table::data.table(group="gamma", name=nm, value=d$gamma[[nm]])
  if (is.finite(d$q_basis)) rows[[length(rows)+1]] <- data.table::data.table(group="basis", name="Q_basis", value=d$q_basis)
  if (is.finite(d$rho)) rows[[length(rows)+1]] <- data.table::data.table(group="basis", name="rho", value=d$rho)
  out <- data.table::rbindlist(rows, fill = TRUE)
  out[, model := fit$model_id]
  out[]
}
