# Valtide P1m: momentum-augmented local-linear-trend challenger
#
# State:
#   m_t = m_{t-1} + v_{t-1} + beta_mom * M_{t-1} + eta_m,t
#   v_t = rho * v_{t-1} + eta_v,t
#
# Observations:
#   y_underlying,t = m_t + eps_u,t
#   y_xstock,t     = m_t + eps_x,t
#
# M_{t-1} is a causal EWMA of prior xStock 5-minute log returns.  It is
# computed before the current xStock observation is used, so there is no
# same-row look-ahead.  beta_mom is constrained to [0, 2].
#
# Relative to P1a, P1m adds only three global parameters:
#   q_velocity, rho, beta_momentum
#
# This is deliberately parsimonious so the experiment tests the momentum
# hypothesis rather than fitting a large asset-specific model.

p1m_rho_from_raw <- function(x) 0.999 * stats::plogis(x)
p1m_rho_to_raw <- function(rho) stats::qlogis(pmin(pmax(rho / 0.999, 1e-6), 1 - 1e-6))

p1m_beta_from_raw <- function(x) 2.0 * stats::plogis(x)
p1m_beta_to_raw <- function(beta) stats::qlogis(pmin(pmax(beta / 2.0, 1e-6), 1 - 1e-6))

p1m_rep_session <- function(x, sessions) stats::setNames(rep(as.numeric(x), length(sessions)), sessions)

add_causal_xstock_momentum <- function(dt, alpha = 0.35) {
  out <- data.table::copy(dt)
  n <- nrow(out)
  mom <- rep(NA_real_, n)
  ewma <- NA_real_

  if (n == 0L) {
    out[, nvdax_ewma_momentum_lag1 := mom]
    return(out)
  }

  for (i in seq_len(n)) {
    # Feature available before current observation i is assimilated.
    mom[[i]] <- ewma

    if (i == 1L) next

    exact_5m <- isTRUE(as.numeric(difftime(
      out$timestamp_utc[[i]], out$timestamp_utc[[i - 1L]], units = "secs"
    )) == 300)

    if (!exact_5m) {
      ewma <- NA_real_
      next
    }

    x_now <- out$nvdax_log_price[[i]]
    x_prev <- out$nvdax_log_price[[i - 1L]]

    if (is.finite(x_now) && is.finite(x_prev)) {
      r <- x_now - x_prev
      if (is.finite(ewma)) {
        ewma <- alpha * r + (1 - alpha) * ewma
      } else {
        ewma <- r
      }
    }
  }

  out[, nvdax_ewma_momentum_lag1 := mom]
  out
}

prepare_p1m_data <- function(dt, spec, hide_nvda = FALSE) {
  x <- prepare_model_data(dt, spec, hide_nvda = hide_nvda)
  m <- as.numeric(dt$nvdax_ewma_momentum_lag1)
  m[!is.finite(m)] <- 0
  x$momentum <- m
  x
}

make_p1m_parameterization <- function(spec, p1a_fit = NULL) {
  s <- spec$sessions

  if (!is.null(p1a_fit) && !is.null(p1a_fit$decoded)) {
    prev <- p1a_fit$decoded
    q0 <- prev$q_by_session
    if (length(q0) == 1L) q0 <- p1m_rep_session(q0, s) else q0 <- q0[s]
    fallback_q <- stats::median(prev$q_by_session, na.rm = TRUE)
    if (!is.finite(fallback_q)) fallback_q <- 1e-6
    q0[!is.finite(q0)] <- fallback_q

    ru0 <- prev$r_nvda
    if (!is.finite(ru0)) ru0 <- 1.5e-6

    rx0 <- prev$r_nvdax_by_session
    if (length(rx0) == 1L) rx0 <- p1m_rep_session(rx0, s) else rx0 <- rx0[s]
    fallback_rx <- stats::median(prev$r_nvdax_by_session, na.rm = TRUE)
    if (!is.finite(fallback_rx)) fallback_rx <- 2e-6
    rx0[!is.finite(rx0)] <- fallback_rx
    rx_scalar <- stats::median(rx0, na.rm = TRUE)
  } else {
    q0 <- p1m_rep_session(1e-6, s)
    ru0 <- 1.5e-6
    rx_scalar <- 2e-6
  }

  par <- lower <- upper <- numeric()
  add <- function(name, value, lo, hi) {
    par <<- c(par, stats::setNames(value, name))
    lower <<- c(lower, stats::setNames(lo, name))
    upper <<- c(upper, stats::setNames(hi, name))
  }

  for (ss in s) add(paste0("logQ_level__", ss), log(q0[[ss]]), -25, -1)
  add("logR_underlying", log(ru0), -25, -1)
  add("logR_xstock", log(rx_scalar), -25, -1)

  # Velocity innovations should generally be smaller than level innovations.
  add("logQ_velocity", log(1e-8), -30, -5)

  # Persistent but damped local trend.
  add("rho_raw", p1m_rho_to_raw(0.85), -7, 7)

  # beta=0.5 means extrapolate half of the causal EWMA token momentum into the
  # prior drift; the optimizer may shrink this almost to zero or raise it to 2.
  add("beta_mom_raw", p1m_beta_to_raw(0.50), -7, 7)

  list(par = par, lower = lower, upper = upper)
}

decode_p1m_parameters <- function(par, spec) {
  s <- spec$sessions
  q_level <- stats::setNames(
    vapply(s, function(ss) exp(par[[paste0("logQ_level__", ss)]]), numeric(1)),
    s
  )
  list(
    q_level_by_session = q_level,
    r_underlying = exp(par[["logR_underlying"]]),
    r_xstock = exp(par[["logR_xstock"]]),
    q_velocity = exp(par[["logQ_velocity"]]),
    rho = p1m_rho_from_raw(par[["rho_raw"]]),
    beta_momentum = p1m_beta_from_raw(par[["beta_mom_raw"]])
  )
}

p1m_scalar_update <- function(x, P, y, h, r) {
  Ph <- as.numeric(P %*% h)
  S <- sum(h * Ph) + r
  if (!is.finite(S) || S <= 0) return(NULL)
  v <- y - sum(h * x)
  K <- Ph / S
  x2 <- x + K * v
  P2 <- P - tcrossprod(K, Ph)
  P2 <- (P2 + t(P2)) / 2
  ll <- -0.5 * (log(2 * pi) + log(S) + v * v / S)
  list(x = x2, P = P2, ll = ll, z = v / sqrt(S))
}

run_p1m_filter <- function(par, data, spec, init_state = NULL, init_P = NULL,
                           return_states = TRUE, interval_level = 0.90) {
  dec <- decode_p1m_parameters(par, spec)
  n <- length(data$y_nvda)

  m0 <- initial_m(data)
  x <- if (is.null(init_state)) c(m0, 0) else as.numeric(init_state)
  P <- if (is.null(init_P)) diag(c(1, 1e-4)) else as.matrix(init_P)

  if (return_states) {
    out_m <- out_v <- out_Pm <- out_Pv <- out_ll <- rep(NA_real_, n)
    out_z_u <- out_z_x <- rep(NA_real_, n)
    out_obs <- integer(n)
  }

  total_ll <- 0
  scalar_obs <- 0L

  for (t in seq_len(n)) {
    sid <- data$session[[t]]
    q_level <- unname(dec$q_level_by_session[[sid]])

    F <- matrix(c(
      1, 1,
      0, dec$rho
    ), nrow = 2, byrow = TRUE)

    drift <- dec$beta_momentum * data$momentum[[t]]
    x_pred <- c(
      x[[1]] + x[[2]] + drift,
      dec$rho * x[[2]]
    )

    Q <- diag(c(q_level, dec$q_velocity))
    P_pred <- F %*% P %*% t(F) + Q
    P_pred <- (P_pred + t(P_pred)) / 2

    x <- x_pred
    P <- P_pred
    ll_t <- 0
    obs_t <- 0L
    z_u <- z_x <- NA_real_

    if (is.finite(data$y_nvda[[t]])) {
      up <- p1m_scalar_update(x, P, data$y_nvda[[t]], c(1, 0), dec$r_underlying)
      if (!is.null(up)) {
        x <- up$x; P <- up$P; ll_t <- ll_t + up$ll; z_u <- up$z
        obs_t <- obs_t + 1L; scalar_obs <- scalar_obs + 1L
      }
    }

    if (is.finite(data$y_nvdax[[t]])) {
      up <- p1m_scalar_update(x, P, data$y_nvdax[[t]], c(1, 0), dec$r_xstock)
      if (!is.null(up)) {
        x <- up$x; P <- up$P; ll_t <- ll_t + up$ll; z_x <- up$z
        obs_t <- obs_t + 1L; scalar_obs <- scalar_obs + 1L
      }
    }

    total_ll <- total_ll + ll_t

    if (return_states) {
      out_m[[t]] <- x[[1]]
      out_v[[t]] <- x[[2]]
      out_Pm[[t]] <- max(P[1, 1], 1e-15)
      out_Pv[[t]] <- max(P[2, 2], 1e-15)
      out_ll[[t]] <- ll_t
      out_z_u[[t]] <- z_u
      out_z_x[[t]] <- z_x
      out_obs[[t]] <- obs_t
    }
  }

  ans <- list(
    loglik = total_ll,
    final_state = x,
    final_P = P,
    scalar_obs = scalar_obs
  )

  if (return_states) {
    zcrit <- stats::qnorm((1 + interval_level) / 2)
    ans$states <- data.table::data.table(
      timestamp_utc = data$timestamp,
      m_filt = out_m,
      velocity_filt = out_v,
      P_filt = out_Pm,
      P_velocity = out_Pv,
      fair_value = exp(out_m),
      fair_value_lo = exp(out_m - zcrit * sqrt(out_Pm)),
      fair_value_hi = exp(out_m + zcrit * sqrt(out_Pm)),
      innov_z_underlying = out_z_u,
      innov_z_xstock = out_z_x,
      loglik_t = out_ll,
      observations_used = out_obs
    )
  }

  ans
}

p1m_negative_loglik <- function(par, data, spec) {
  ans <- try(run_p1m_filter(par, data, spec, return_states = FALSE), silent = TRUE)
  if (inherits(ans, "try-error") || !is.finite(ans$loglik)) {
    return(.Machine$double.xmax / 100)
  }
  -ans$loglik
}

fit_p1m <- function(train_data, spec, config, p1a_fit = NULL) {
  prm <- make_p1m_parameterization(spec, p1a_fit = p1a_fit)
  start <- Sys.time()

  opt <- stats::optim(
    par = prm$par,
    fn = p1m_negative_loglik,
    data = train_data,
    spec = spec,
    method = "L-BFGS-B",
    lower = prm$lower,
    upper = prm$upper,
    control = list(maxit = config$maxit, factr = 1e7)
  )

  elapsed <- as.numeric(difftime(Sys.time(), start, units = "secs"))
  filt <- run_p1m_filter(
    opt$par, train_data, spec,
    return_states = TRUE,
    interval_level = config$interval_level
  )

  k <- length(opt$par)
  nobs <- max(filt$scalar_obs, 1L)

  list(
    status = if (opt$convergence == 0) "OK" else "WARN",
    reason = opt$message %||% "",
    model_id = "P1m",
    par = opt$par,
    decoded = decode_p1m_parameters(opt$par, spec),
    optimizer = opt,
    loglik = filt$loglik,
    AIC = 2 * k - 2 * filt$loglik,
    BIC = log(nobs) * k - 2 * filt$loglik,
    n_params = k,
    elapsed_sec = elapsed,
    train_filter = filt,
    spec = spec
  )
}

# Causal one-step replay:
# 1. predict using latent trend + lagged momentum;
# 2. assimilate current xStock;
# 3. record the estimate before seeing current underlying;
# 4. score, then assimilate current underlying for the next row.
p1m_one_step_reference_replay <- function(fit, dt, spec,
                                          init_state = fit$train_filter$final_state,
                                          init_P = fit$train_filter$final_P) {
  data <- prepare_p1m_data(dt, spec, hide_nvda = FALSE)
  dec <- fit$decoded
  x <- as.numeric(init_state)
  P <- as.matrix(init_P)
  n <- nrow(dt)

  out <- data.table::data.table(
    timestamp_utc = dt$timestamp_utc,
    session_state = dt$session_state,
    nvda_log_price = dt$nvda_log_price,
    nvdax_log_price = dt$nvdax_log_price,
    momentum_ewma_lag1 = dt$nvdax_ewma_momentum_lag1,
    reference_hidden_mean = NA_real_,
    reference_hidden_velocity = NA_real_,
    reference_hidden_P = NA_real_,
    reference_predictive_sd = NA_real_,
    signed_score = NA_real_,
    abs_score = NA_real_,
    nvdax_innovation_z = NA_real_
  )

  for (t in seq_len(n)) {
    sid <- data$session[[t]]
    q_level <- unname(dec$q_level_by_session[[sid]])

    F <- matrix(c(1, 1, 0, dec$rho), nrow = 2, byrow = TRUE)
    drift <- dec$beta_momentum * data$momentum[[t]]

    x0 <- c(
      x[[1]] + x[[2]] + drift,
      dec$rho * x[[2]]
    )
    P0 <- F %*% P %*% t(F) + diag(c(q_level, dec$q_velocity))
    P0 <- (P0 + t(P0)) / 2
    z_x <- NA_real_

    if (is.finite(data$y_nvdax[[t]])) {
      up <- p1m_scalar_update(x0, P0, data$y_nvdax[[t]], c(1, 0), dec$r_xstock)
      if (!is.null(up)) {
        x0 <- up$x
        P0 <- up$P
        z_x <- up$z
      }
    }

    out$reference_hidden_mean[[t]] <- x0[[1]]
    out$reference_hidden_velocity[[t]] <- x0[[2]]
    out$reference_hidden_P[[t]] <- max(P0[1, 1], 1e-15)
    out$reference_predictive_sd[[t]] <- sqrt(max(P0[1, 1], 1e-15) + dec$r_underlying)
    out$nvdax_innovation_z[[t]] <- z_x

    if (is.finite(data$y_nvda[[t]])) {
      z <- (data$y_nvda[[t]] - x0[[1]]) /
        sqrt(max(P0[1, 1], 1e-15) + dec$r_underlying)

      out$signed_score[[t]] <- z
      out$abs_score[[t]] <- abs(z)

      up <- p1m_scalar_update(x0, P0, data$y_nvda[[t]], c(1, 0), dec$r_underlying)
      if (!is.null(up)) {
        x0 <- up$x
        P0 <- up$P
      }
    }

    x <- x0
    P <- P0
  }

  out[, minutes_since_last_nvda := minutes_since_last_observed(
    timestamp_utc, is.finite(nvda_log_price)
  )]

  attr(out, "final_state") <- x
  attr(out, "final_P") <- P
  out[]
}

p1m_pseudo_closure_stress <- function(fit, test_dt, spec, cal,
                                      durations_min = c(30L, 60L, 120L, 240L)) {
  normal_data <- prepare_p1m_data(test_dt, spec, hide_nvda = FALSE)
  normal <- run_p1m_filter(
    fit$par, normal_data, spec,
    init_state = fit$train_filter$final_state,
    init_P = fit$train_filter$final_P,
    return_states = TRUE
  )

  rows <- list()
  n <- nrow(test_dt)

  for (dur in durations_min) {
    L <- as.integer(dur / 5L)
    if (L < 1L) next
    i <- 2L
    block_id <- 0L

    while (i + L - 1L <= n) {
      idx <- i:(i + L - 1L)
      ts <- test_dt$timestamp_utc[idx]
      contiguous <- all(diff(as.numeric(ts)) == 300)
      labels <- is.finite(test_dt$nvda_log_price[idx]) &
        is.finite(test_dt$nvdax_log_price[idx])

      if (contiguous && all(labels)) {
        block_id <- block_id + 1L
        block <- test_dt[idx]
        masked_data <- prepare_p1m_data(block, spec, hide_nvda = TRUE)

        init_state <- c(
          normal$states$m_filt[[i - 1L]],
          normal$states$velocity_filt[[i - 1L]]
        )

        # Reconstruct the 2x2 covariance at the block boundary by replaying the
        # prefix once. This avoids throwing away m-v covariance.
        prefix <- test_dt[seq_len(i - 1L)]
        prefix_data <- prepare_p1m_data(prefix, spec, hide_nvda = FALSE)
        prefix_fit <- run_p1m_filter(
          fit$par, prefix_data, spec,
          init_state = fit$train_filter$final_state,
          init_P = fit$train_filter$final_P,
          return_states = FALSE
        )
        init_P <- prefix_fit$final_P
        init_state <- prefix_fit$final_state

        masked <- run_p1m_filter(
          fit$par, masked_data, spec,
          init_state = init_state,
          init_P = init_P,
          return_states = TRUE
        )

        replay <- data.table::data.table(
          timestamp_utc = block$timestamp_utc,
          session_state = block$session_state,
          nvda_log_price = block$nvda_log_price,
          nvdax_log_price = block$nvdax_log_price,
          reference_hidden_mean = masked$states$m_filt,
          reference_hidden_velocity = masked$states$velocity_filt,
          reference_hidden_P = masked$states$P_filt,
          reference_predictive_sd = sqrt(masked$states$P_filt + fit$decoded$r_underlying)
        )

        scored <- apply_calibrator(replay, cal)
        scored[, `:=`(
          duration_min = dur,
          block_id = block_id,
          step_in_block = seq_len(.N)
        )]
        rows[[length(rows) + 1L]] <- scored
        i <- i + L
      } else {
        i <- i + 1L
      }
    }
  }

  if (!length(rows)) {
    return(list(
      detail = data.table::data.table(),
      metrics = data.table::data.table()
    ))
  }

  detail <- data.table::rbindlist(rows, fill = TRUE)
  metrics <- detail[, interval_metrics(.SD, cal$level), by = duration_min]
  list(detail = detail, metrics = metrics)
}
