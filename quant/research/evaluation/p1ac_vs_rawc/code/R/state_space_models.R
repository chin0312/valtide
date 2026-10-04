theta_from_raw <- function(x) 2 * stats::plogis(x)
theta_to_raw <- function(theta) stats::qlogis(pmin(pmax(theta / 2, 1e-6), 1 - 1e-6))
rho_from_raw <- function(x) 0.999 * stats::plogis(x)
rho_to_raw <- function(rho) stats::qlogis(pmin(pmax(rho / 0.999, 1e-6), 1 - 1e-6))

rep_session <- function(x, sessions) stats::setNames(rep(as.numeric(x), length(sessions)), sessions)

make_parameterization <- function(model_id, spec, previous_fit = NULL) {
  s <- spec$sessions
  ns <- length(s)
  f <- spec$factors$cols
  qcols <- spec$quality$cols

  # Warm-start economic parameters from the last successful model.
  if (!is.null(previous_fit)) {
    prev <- previous_fit$decoded
    q0 <- prev$q_by_session
    if (length(q0) == 1) q0 <- rep_session(q0, s) else q0 <- q0[s]
    q0[!is.finite(q0)] <- median(prev$q_by_session, na.rm = TRUE)
    rnvda0 <- prev$r_nvda
    rx0 <- prev$r_nvdax_by_session
    if (length(rx0) == 1) rx0 <- rep_session(rx0, s) else rx0 <- rx0[s]
    rx0[!is.finite(rx0)] <- median(prev$r_nvdax_by_session, na.rm = TRUE)
    th0 <- prev$theta_by_session %||% rep_session(0.95, s)
    if (length(th0) == 1) th0 <- rep_session(th0, s) else th0 <- th0[s]
    th0[!is.finite(th0)] <- 0.95
  } else {
    q0 <- rep_session(1e-6, s)
    rnvda0 <- 1.5e-6
    rx0 <- rep_session(2e-6, s)
    th0 <- rep_session(0.95, s)
  }

  raw <- c()
  lower <- c()
  upper <- c()
  add <- function(name, value, lo, hi) {
    raw <<- c(raw, stats::setNames(value, name))
    lower <<- c(lower, stats::setNames(lo, name))
    upper <<- c(upper, stats::setNames(hi, name))
  }

  if (model_id == "P0") {
    add("logQ", log(median(q0)), -25, -1)
    add("logR_nvda", log(rnvda0), -25, -1)
    add("logR_nvdax", log(median(rx0)), -25, -1)
  } else {
    for (ss in s) add(paste0("logQ__", ss), log(q0[[ss]]), -25, -1)
    add("logR_nvda", log(rnvda0), -25, -1)

    if (model_id == "P1a") {
      add("logR_nvdax", log(median(rx0)), -25, -1)
    } else {
      for (ss in s) add(paste0("logR_nvdax__", ss), log(rx0[[ss]]), -25, -1)
    }

    if (model_id %in% c("P2", "P3", "P4", "P5")) {
      for (ss in s) add(paste0("theta_raw__", ss), theta_to_raw(th0[[ss]]), -7, 7)
    }
    if (model_id %in% c("P3", "P4", "P5")) {
      for (nm in f) add(paste0("beta__", nm), 0, -0.10, 0.10)
    }
    if (model_id %in% c("P4", "P5")) {
      for (nm in qcols) add(paste0("gamma__", nm), 0, -3, 3)
    }
    if (model_id == "P5") {
      add("logQ_basis", log(1e-8), -25, -3)
      add("rho_raw", rho_to_raw(0.95), -7, 7)
    }
  }

  list(par = raw, lower = lower, upper = upper)
}

decode_parameters <- function(model_id, par, spec) {
  s <- spec$sessions
  if (model_id == "P0") {
    q <- rep_session(exp(par[["logQ"]]), s)
    rx <- rep_session(exp(par[["logR_nvdax"]]), s)
  } else {
    q <- stats::setNames(vapply(s, function(ss) exp(par[[paste0("logQ__", ss)]]), numeric(1)), s)
    if (model_id == "P1a") {
      rx <- rep_session(exp(par[["logR_nvdax"]]), s)
    } else {
      rx <- stats::setNames(vapply(s, function(ss) exp(par[[paste0("logR_nvdax__", ss)]]), numeric(1)), s)
    }
  }

  theta <- if (model_id %in% c("P2", "P3", "P4", "P5")) {
    stats::setNames(vapply(s, function(ss) theta_from_raw(par[[paste0("theta_raw__", ss)]]), numeric(1)), s)
  } else rep_session(1, s)

  beta <- if (model_id %in% c("P3", "P4", "P5") && length(spec$factors$cols)) {
    stats::setNames(vapply(spec$factors$cols, function(nm) par[[paste0("beta__", nm)]], numeric(1)), spec$factors$cols)
  } else numeric()

  gamma <- if (model_id %in% c("P4", "P5") && length(spec$quality$cols)) {
    stats::setNames(vapply(spec$quality$cols, function(nm) par[[paste0("gamma__", nm)]], numeric(1)), spec$quality$cols)
  } else numeric()

  list(
    q_by_session = q,
    r_nvda = exp(par[["logR_nvda"]]),
    r_nvdax_by_session = rx,
    theta_by_session = theta,
    beta = beta,
    gamma = gamma,
    q_basis = if (model_id == "P5") exp(par[["logQ_basis"]]) else NA_real_,
    rho = if (model_id == "P5") rho_from_raw(par[["rho_raw"]]) else NA_real_
  )
}

scalar_update <- function(x, P, y, h, r) {
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

run_state_filter <- function(model_id, par, data, spec, init_state = NULL, init_P = NULL,
                             return_states = TRUE, interval_level = 0.90) {
  dec <- decode_parameters(model_id, par, spec)
  n <- length(data$y_nvda)
  ns <- length(spec$sessions)
  state_dim <- if (model_id %in% c("P0", "P1a", "P1b")) 1L else if (model_id == "P5") 3L else 2L

  m0 <- initial_m(data)
  if (is.null(init_state)) {
    x <- if (state_dim == 1L) c(m0) else if (state_dim == 2L) c(m0, m0) else c(m0, m0, 0)
  } else x <- as.numeric(init_state)

  if (is.null(init_P)) {
    P <- diag(if (state_dim == 3L) c(1, 1, 1e-4) else rep(1, state_dim))
  } else P <- as.matrix(init_P)

  if (return_states) {
    out_m <- out_P <- out_ll <- out_z_nvda <- out_z_nvdax <- rep(NA_real_, n)
    out_basis <- rep(NA_real_, n)
    out_obs <- integer(n)
  }

  total_ll <- 0
  scalar_obs <- 0L

  for (t in seq_len(n)) {
    sid <- data$session[t]
    q <- unname(dec$q_by_session[sid])
    r_x_base <- unname(dec$r_nvdax_by_session[sid])
    theta <- unname(dec$theta_by_session[sid])

    drift <- 0
    if (length(dec$beta)) drift <- sum(dec$beta * data$X[t, , drop = TRUE])

    if (state_dim == 1L) {
      x_pred <- x
      x_pred[1] <- x[1] + drift
      P_pred <- matrix(P[1, 1] + q, 1, 1)
    } else if (state_dim == 2L) {
      x_pred <- c(x[1] + drift, x[1])
      p11 <- P[1, 1]
      P_pred <- matrix(c(p11 + q, p11, p11, p11), 2, 2, byrow = TRUE)
    } else {
      rho <- dec$rho
      x_pred <- c(x[1] + drift, x[1], rho * x[3])
      p11 <- P[1, 1]
      p13 <- P[1, 3]
      p33 <- P[3, 3]
      P_pred <- matrix(c(
        p11 + q, p11, rho * p13,
        p11,     p11, rho * p13,
        rho * p13, rho * p13, rho * rho * p33 + dec$q_basis
      ), 3, 3, byrow = TRUE)
    }

    x <- x_pred
    P <- P_pred
    ll_t <- 0
    obs_t <- 0L
    z_nvda <- z_nvdax <- NA_real_

    if (is.finite(data$y_nvda[t])) {
      h <- if (state_dim == 1L) c(1) else if (state_dim == 2L) c(1, 0) else c(1, 0, 0)
      up <- scalar_update(x, P, data$y_nvda[t], h, dec$r_nvda)
      if (!is.null(up)) {
        x <- up$x; P <- up$P; ll_t <- ll_t + up$ll; z_nvda <- up$z
        obs_t <- obs_t + 1L; scalar_obs <- scalar_obs + 1L
      }
    }

    if (is.finite(data$y_nvdax[t])) {
      if (state_dim == 1L) h <- c(1)
      else if (state_dim == 2L) h <- c(theta, 1 - theta)
      else h <- c(theta, 1 - theta, 1)

      r_x <- r_x_base
      if (model_id %in% c("P4", "P5") && length(dec$gamma)) {
        log_mult <- sum(dec$gamma * data$Zq[t, , drop = TRUE])
        log_mult <- min(max(log_mult, -6), 6)
        r_x <- r_x_base * exp(log_mult)
      }
      r_x <- min(max(r_x, 1e-12), 0.25)

      up <- scalar_update(x, P, data$y_nvdax[t], h, r_x)
      if (!is.null(up)) {
        x <- up$x; P <- up$P; ll_t <- ll_t + up$ll; z_nvdax <- up$z
        obs_t <- obs_t + 1L; scalar_obs <- scalar_obs + 1L
      }
    }

    total_ll <- total_ll + ll_t
    if (return_states) {
      out_m[t] <- x[1]
      out_P[t] <- max(P[1, 1], 1e-15)
      out_ll[t] <- ll_t
      out_z_nvda[t] <- z_nvda
      out_z_nvdax[t] <- z_nvdax
      out_basis[t] <- if (state_dim == 3L) x[3] else NA_real_
      out_obs[t] <- obs_t
    }
  }

  result <- list(loglik = total_ll, final_state = x, final_P = P, scalar_obs = scalar_obs)
  if (return_states) {
    alpha <- (1 + interval_level) / 2
    zcrit <- stats::qnorm(alpha)
    states <- data.table::data.table(
      timestamp_utc = data$timestamp,
      m_filt = out_m,
      P_filt = out_P,
      fair_value = exp(out_m),
      fair_value_lo = exp(out_m - zcrit * sqrt(out_P)),
      fair_value_hi = exp(out_m + zcrit * sqrt(out_P)),
      basis_log = out_basis,
      loglik_t = out_ll,
      innov_z_nvda = out_z_nvda,
      innov_z_nvdax = out_z_nvdax,
      observations_used = out_obs
    )
    result$states <- states
  }
  result
}

negative_loglik <- function(par, model_id, data, spec) {
  ans <- try(run_state_filter(model_id, par, data, spec, return_states = FALSE), silent = TRUE)
  if (inherits(ans, "try-error") || !is.finite(ans$loglik)) return(.Machine$double.xmax / 100)
  -ans$loglik
}

fit_state_model <- function(model_id, train_data, spec, config, previous_fit = NULL) {
  if (model_id == "P3" && length(spec$factors$cols) == 0) {
    return(list(status = "SKIPPED", reason = "No external factor_* columns were found."))
  }
  if (model_id == "P4" && length(spec$quality$cols) == 0) {
    return(list(status = "SKIPPED", reason = "No market-quality columns were found or derived."))
  }

  prm <- make_parameterization(model_id, spec, previous_fit)
  start <- Sys.time()
  opt <- stats::optim(
    par = prm$par,
    fn = negative_loglik,
    model_id = model_id,
    data = train_data,
    spec = spec,
    method = "L-BFGS-B",
    lower = prm$lower,
    upper = prm$upper,
    control = list(maxit = config$maxit, factr = 1e7)
  )
  elapsed <- as.numeric(difftime(Sys.time(), start, units = "secs"))

  filt <- run_state_filter(model_id, opt$par, train_data, spec, return_states = TRUE,
                           interval_level = config$interval_level)
  k <- length(opt$par)
  nobs <- max(filt$scalar_obs, 1L)
  decoded <- decode_parameters(model_id, opt$par, spec)

  list(
    status = if (opt$convergence == 0) "OK" else "WARN",
    reason = opt$message %||% "",
    model_id = model_id,
    par = opt$par,
    decoded = decoded,
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
