# P1a-C: empirical calibration for P1a's probabilistic interval.
#
# Core distinction:
#   latent state: m_t | I_t ~ N(mhat_t, P_t)
#   observable trusted reference: y_NVDA,t | I_t ~ N(mhat_t, P_t + R_NVDA)
#
# Only the latter has an observable contemporaneous target, so empirical
# calibration is performed on the reference-equivalent predictive interval.
# The latent state interval remains a model-implied interval and is reported
# separately without claiming empirical coverage.

finite_conformal_quantile <- function(x, level) {
  x <- sort(as.numeric(x[is.finite(x)]))
  n <- length(x)
  if (n == 0) return(NA_real_)
  k <- ceiling((n + 1) * level)
  k <- min(max(k, 1L), n)
  x[[k]]
}

empirical_tail_quantiles <- function(x, level) {
  x <- as.numeric(x[is.finite(x)])
  if (!length(x)) return(c(lo = NA_real_, hi = NA_real_))
  alpha <- 1 - level
  c(
    lo = unname(stats::quantile(x, probs = alpha / 2, type = 1, na.rm = TRUE)),
    hi = unname(stats::quantile(x, probs = 1 - alpha / 2, type = 1, na.rm = TRUE))
  )
}

interval_score_vec <- function(y, lo, hi, level) {
  alpha <- 1 - level
  score <- hi - lo
  score <- score + (2 / alpha) * (lo - y) * (y < lo)
  score <- score + (2 / alpha) * (y - hi) * (y > hi)
  score
}

minutes_since_last_observed <- function(timestamp, observed) {
  out <- rep(NA_real_, length(timestamp))
  last <- as.POSIXct(NA, tz = "UTC")
  for (i in seq_along(timestamp)) {
    if (isTRUE(observed[[i]])) {
      last <- timestamp[[i]]
      out[[i]] <- 0
    } else if (!is.na(last)) {
      out[[i]] <- as.numeric(difftime(timestamp[[i]], last, units = "mins"))
    }
  }
  out
}

# One-step leave-NVDA-out replay for P1a.
# At each row we:
#   (1) predict the latent state;
#   (2) assimilate current NVDAx, if present;
#   (3) record the distribution BEFORE seeing current NVDA;
#   (4) if NVDA is actually observed, assimilate it after scoring so it may be
#       used as past information at the next timestamp.
#
# This is causal and avoids the pathological "hide NVDA for the entire year"
# calibration path while still testing the exact quantity required when the
# trusted reference is unavailable at the current timestamp.
p1a_one_step_reference_replay <- function(fit, dt, spec,
                                           init_state = fit$train_filter$final_state,
                                           init_P = fit$train_filter$final_P) {
  if (!identical(fit$model_id, "P1a")) stop("p1a_one_step_reference_replay requires a P1a fit.")

  data <- prepare_model_data(dt, spec, hide_nvda = FALSE)
  dec <- fit$decoded
  x <- as.numeric(init_state)[1]
  P <- as.numeric(as.matrix(init_P)[1, 1])
  n <- nrow(dt)

  out <- data.table::data.table(
    timestamp_utc = dt$timestamp_utc,
    session_state = dt$session_state,
    nvda_log_price = dt$nvda_log_price,
    nvdax_log_price = dt$nvdax_log_price,
    reference_hidden_mean = NA_real_,
    reference_hidden_P = NA_real_,
    reference_predictive_sd = NA_real_,
    signed_score = NA_real_,
    abs_score = NA_real_,
    nvdax_innovation_z = NA_real_
  )

  for (t in seq_len(n)) {
    sid <- data$session[[t]]
    q <- unname(dec$q_by_session[[sid]])
    r_x <- unname(dec$r_nvdax_by_session[[sid]])

    # Random-walk prediction.
    x0 <- x
    P0 <- P + q
    z_x <- NA_real_

    # Assimilate current token price first. For scalar independent Gaussian
    # measurements, final posterior after both sources is order invariant.
    if (is.finite(data$y_nvdax[[t]])) {
      Sx <- P0 + r_x
      vx <- data$y_nvdax[[t]] - x0
      Kx <- P0 / Sx
      x0 <- x0 + Kx * vx
      P0 <- max(P0 - Kx * P0, 1e-15)
      z_x <- vx / sqrt(Sx)
    }

    out$reference_hidden_mean[[t]] <- x0
    out$reference_hidden_P[[t]] <- P0
    out$reference_predictive_sd[[t]] <- sqrt(P0 + dec$r_nvda)
    out$nvdax_innovation_z[[t]] <- z_x

    # Score the counterfactual interval before observing current NVDA.
    if (is.finite(data$y_nvda[[t]])) {
      z <- (data$y_nvda[[t]] - x0) / sqrt(P0 + dec$r_nvda)
      out$signed_score[[t]] <- z
      out$abs_score[[t]] <- abs(z)

      # Re-anchor for the next timestamp using the trusted observation.
      Sn <- P0 + dec$r_nvda
      vn <- data$y_nvda[[t]] - x0
      Kn <- P0 / Sn
      x0 <- x0 + Kn * vn
      P0 <- max(P0 - Kn * P0, 1e-15)
    }

    x <- x0
    P <- P0
  }

  out[, minutes_since_last_nvda := minutes_since_last_observed(
    timestamp_utc, is.finite(nvda_log_price)
  )]
  attr(out, "final_state") <- c(x)
  attr(out, "final_P") <- matrix(P, 1, 1)
  out[]
}

make_expanding_crossfit_folds <- function(train, initial_fraction = 0.50, n_folds = 4L) {
  n <- nrow(train)
  initial_end <- floor(n * initial_fraction)
  if (initial_end < 100L) stop("Initial cross-fit training window is too small.")
  remaining <- n - initial_end
  if (remaining < n_folds * 20L) stop("Not enough rows for requested cross-fit folds.")

  boundaries <- floor(seq(initial_end, n, length.out = n_folds + 1L))
  folds <- vector("list", n_folds)
  for (k in seq_len(n_folds)) {
    fit_end <- boundaries[[k]]
    score_start <- fit_end + 1L
    score_end <- boundaries[[k + 1L]]
    folds[[k]] <- list(
      fold = k,
      fit_idx = seq_len(fit_end),
      score_idx = score_start:score_end
    )
  }
  folds
}

fit_calibrator <- function(scores, type, level, min_session_scores = 200L) {
  scores <- scores[is.finite(signed_score) & is.finite(abs_score)]
  if (!nrow(scores)) stop("No finite calibration scores.")

  z_gauss <- stats::qnorm((1 + level) / 2)
  global_sym <- finite_conformal_quantile(scores$abs_score, level)
  global_asym <- empirical_tail_quantiles(scores$signed_score, level)

  cal <- list(
    type = type,
    level = level,
    n = nrow(scores),
    global = list(
      sym = global_sym,
      lo = global_asym[["lo"]],
      hi = global_asym[["hi"]]
    ),
    sessions = list(),
    min_session_scores = min_session_scores
  )

  if (type == "gaussian") {
    cal$global$sym <- z_gauss
    cal$global$lo <- -z_gauss
    cal$global$hi <- z_gauss
  }

  if (startsWith(type, "session_")) {
    for (ss in unique(as.character(scores$session_state))) {
      x <- scores[session_state == ss]
      if (nrow(x) < min_session_scores) next
      asym <- empirical_tail_quantiles(x$signed_score, level)
      cal$sessions[[ss]] <- list(
        n = nrow(x),
        sym = finite_conformal_quantile(x$abs_score, level),
        lo = asym[["lo"]],
        hi = asym[["hi"]]
      )
    }
  }
  cal
}

calibrator_bounds <- function(cal, session) {
  type <- cal$type
  use <- cal$global
  source <- "global"

  if (startsWith(type, "session_") && !is.null(cal$sessions[[session]])) {
    use <- cal$sessions[[session]]
    source <- paste0("session:", session)
  } else if (startsWith(type, "session_")) {
    source <- "global_fallback"
  }

  if (type %in% c("gaussian", "global_sym", "session_sym")) {
    c(lo = -use$sym, hi = use$sym, source = source)
  } else {
    c(lo = use$lo, hi = use$hi, source = source)
  }
}

apply_calibrator <- function(replay, cal) {
  out <- data.table::copy(replay)
  lo_z <- hi_z <- rep(NA_real_, nrow(out))
  source <- rep(NA_character_, nrow(out))

  for (i in seq_len(nrow(out))) {
    b <- calibrator_bounds(cal, as.character(out$session_state[[i]]))
    lo_z[[i]] <- as.numeric(b[["lo"]])
    hi_z[[i]] <- as.numeric(b[["hi"]])
    source[[i]] <- as.character(b[["source"]])
  }

  out[, `:=`(
    calibration_type = cal$type,
    calibration_level = cal$level,
    calibration_source = source,
    q_lower = lo_z,
    q_upper = hi_z,
    calibrated_log_lo = reference_hidden_mean + lo_z * reference_predictive_sd,
    calibrated_log_hi = reference_hidden_mean + hi_z * reference_predictive_sd
  )]
  out[, `:=`(
    calibrated_price_mid = exp(reference_hidden_mean),
    calibrated_price_lo = exp(calibrated_log_lo),
    calibrated_price_hi = exp(calibrated_log_hi)
  )]
  out[]
}

interval_metrics <- function(x, level) {
  ok <- is.finite(x$nvda_log_price) & is.finite(x$calibrated_log_lo) & is.finite(x$calibrated_log_hi)
  x <- x[ok]
  if (!nrow(x)) {
    return(data.table::data.table(
      n = 0L, coverage = NA_real_, coverage_error = NA_real_,
      lower_miss_rate = NA_real_, upper_miss_rate = NA_real_,
      mean_width_bps = NA_real_, median_width_bps = NA_real_,
      mean_interval_score_bps = NA_real_, MAE_bps = NA_real_, RMSE_bps = NA_real_
    ))
  }

  y <- x$nvda_log_price
  lo <- x$calibrated_log_lo
  hi <- x$calibrated_log_hi
  mid <- x$reference_hidden_mean
  err <- mid - y
  score <- interval_score_vec(y, lo, hi, level)

  data.table::data.table(
    n = nrow(x),
    coverage = mean(y >= lo & y <= hi),
    coverage_error = mean(y >= lo & y <= hi) - level,
    lower_miss_rate = mean(y < lo),
    upper_miss_rate = mean(y > hi),
    mean_width_bps = 10000 * mean(hi - lo),
    median_width_bps = 10000 * stats::median(hi - lo),
    mean_interval_score_bps = 10000 * mean(score),
    MAE_bps = 10000 * mean(abs(err)),
    RMSE_bps = 10000 * sqrt(mean(err^2))
  )
}

evaluate_calibrator <- function(replay, cal, label = NULL) {
  scored <- apply_calibrator(replay, cal)
  overall <- interval_metrics(scored, cal$level)
  overall[, `:=`(
    candidate = label %||% cal$type,
    level = cal$level,
    session_state = "ALL"
  )]

  by_session <- scored[, {
    m <- interval_metrics(.SD, cal$level)
    m
  }, by = session_state]
  by_session[, `:=`(
    candidate = label %||% cal$type,
    level = cal$level
  )]

  list(scored = scored, metrics = data.table::rbindlist(list(overall, by_session), fill = TRUE))
}

select_calibrator_type <- function(validation_metrics, level, coverage_tolerance = 0.03) {
  m <- validation_metrics[session_state == "ALL" & abs(validation_metrics$level - level) < 1e-12]
  if (!nrow(m)) stop("No validation metrics for primary level.")

  m[, coverage_abs_error := abs(coverage - level)]
  eligible <- m[coverage_abs_error <= coverage_tolerance]
  if (nrow(eligible)) {
    data.table::setorder(eligible, mean_interval_score_bps, coverage_abs_error, mean_width_bps)
    return(as.character(eligible$candidate[[1]]))
  }

  data.table::setorder(m, coverage_abs_error, mean_interval_score_bps, mean_width_bps)
  as.character(m$candidate[[1]])
}

calibrator_to_jsonable <- function(cal) {
  list(
    type = cal$type,
    level = cal$level,
    n = cal$n,
    global = cal$global,
    sessions = cal$sessions,
    min_session_scores = cal$min_session_scores
  )
}

# Block bootstrap by New York trading date. This is used for uncertainty around
# the test comparison; five-minute rows are not treated as iid observations.
block_bootstrap_difference <- function(a, b, level, reps = 2000L, seed = 97L) {
  stopifnot(nrow(a) == nrow(b))
  x <- data.table::data.table(
    timestamp_utc = a$timestamp_utc,
    y = a$nvda_log_price,
    a_lo = a$calibrated_log_lo,
    a_hi = a$calibrated_log_hi,
    b_lo = b$calibrated_log_lo,
    b_hi = b$calibrated_log_hi
  )
  x <- x[is.finite(y) & is.finite(a_lo) & is.finite(a_hi) & is.finite(b_lo) & is.finite(b_hi)]
  if (!nrow(x)) return(data.table::data.table())

  # Base R timezone conversion avoids an additional package dependency.
  x[, block_date := format(timestamp_utc, tz = "America/New_York", format = "%Y-%m-%d")]
  per_block <- x[, .(
    score_a = mean(interval_score_vec(y, a_lo, a_hi, level)),
    score_b = mean(interval_score_vec(y, b_lo, b_hi, level)),
    width_a = mean(a_hi - a_lo),
    width_b = mean(b_hi - b_lo),
    coverage_a = mean(y >= a_lo & y <= a_hi),
    coverage_b = mean(y >= b_lo & y <= b_hi)
  ), by = block_date]
  if (nrow(per_block) < 5L) return(data.table::data.table())

  set.seed(seed)
  n <- nrow(per_block)
  boots <- matrix(NA_real_, nrow = reps, ncol = 3)
  colnames(boots) <- c("score_diff_bps", "width_diff_bps", "coverage_diff")
  for (r in seq_len(reps)) {
    idx <- sample.int(n, size = n, replace = TRUE)
    z <- per_block[idx]
    boots[r, 1] <- 10000 * mean(z$score_a - z$score_b)
    boots[r, 2] <- 10000 * mean(z$width_a - z$width_b)
    boots[r, 3] <- mean(z$coverage_a - z$coverage_b)
  }

  q <- function(v) stats::quantile(v, c(0.025, 0.975), na.rm = TRUE, type = 7)
  data.table::data.table(
    n_blocks = n,
    reps = reps,
    mean_score_diff_bps = 10000 * mean(per_block$score_a - per_block$score_b),
    score_diff_ci_low_bps = q(boots[, 1])[[1]],
    score_diff_ci_high_bps = q(boots[, 1])[[2]],
    mean_width_diff_bps = 10000 * mean(per_block$width_a - per_block$width_b),
    width_diff_ci_low_bps = q(boots[, 2])[[1]],
    width_diff_ci_high_bps = q(boots[, 2])[[2]],
    mean_coverage_diff = mean(per_block$coverage_a - per_block$coverage_b),
    coverage_diff_ci_low = q(boots[, 3])[[1]],
    coverage_diff_ci_high = q(boots[, 3])[[2]]
  )
}

pseudo_closure_stress <- function(fit, test_dt, spec, cal, durations_min = c(30L, 60L, 120L, 240L)) {
  normal_data <- prepare_model_data(test_dt, spec, hide_nvda = FALSE)
  normal <- run_state_filter(
    "P1a", fit$par, normal_data, spec,
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
      labels <- is.finite(test_dt$nvda_log_price[idx]) & is.finite(test_dt$nvdax_log_price[idx])

      if (contiguous && all(labels)) {
        block_id <- block_id + 1L
        block <- test_dt[idx]
        masked_data <- prepare_model_data(block, spec, hide_nvda = TRUE)
        init_state <- c(normal$states$m_filt[[i - 1L]])
        init_P <- matrix(normal$states$P_filt[[i - 1L]], 1, 1)
        masked <- run_state_filter(
          "P1a", fit$par, masked_data, spec,
          init_state = init_state, init_P = init_P,
          return_states = TRUE
        )

        replay <- data.table::data.table(
          timestamp_utc = block$timestamp_utc,
          session_state = block$session_state,
          nvda_log_price = block$nvda_log_price,
          nvdax_log_price = block$nvdax_log_price,
          reference_hidden_mean = masked$states$m_filt,
          reference_hidden_P = masked$states$P_filt,
          reference_predictive_sd = sqrt(masked$states$P_filt + fit$decoded$r_nvda)
        )
        scored <- apply_calibrator(replay, cal)
        scored[, `:=`(duration_min = dur, block_id = block_id, step_in_block = seq_len(.N))]
        rows[[length(rows) + 1L]] <- scored
        i <- i + L
      } else {
        i <- i + 1L
      }
    }
  }

  if (!length(rows)) return(list(detail = data.table::data.table(), metrics = data.table::data.table()))
  detail <- data.table::rbindlist(rows, fill = TRUE)
  metrics <- detail[, {
    m <- interval_metrics(.SD, cal$level)
    m
  }, by = duration_min]
  list(detail = detail, metrics = metrics)
}
