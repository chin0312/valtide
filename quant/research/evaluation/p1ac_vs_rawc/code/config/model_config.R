VALTIDE_CONFIG <- list(
  # By default, preserve a legacy train/test split if bundled cached files have one.
  # Otherwise use TRAIN_END_UTC, then fall back to an 80/20 chronological split.
  train_end_utc = Sys.getenv("TRAIN_END_UTC", unset = ""),

  models = c("P0", "P1a", "P1b", "P2", "P3", "P4", "P5"),

  # P3: external, point-in-time cross-market features. Auto-detected columns
  # beginning with factor_. Override with VALTIDE_FACTOR_COLS=a,b,c.
  factor_cols = NULL,
  max_factors = 8L,

  # P4: lagged market-quality variables. Auto-detected/derived if NULL.
  quality_cols = NULL,
  max_quality = 6L,

  # Optimizer controls. Later models are warm-started from the previous fit.
  maxit = as.integer(Sys.getenv("VALTIDE_MAXIT", unset = "250")),
  reltol = as.numeric(Sys.getenv("VALTIDE_RELTOL", unset = "1e-7")),

  # Reuse outputs/<MODEL>_fit.rds when TRUE.
  reuse_fits = tolower(Sys.getenv("VALTIDE_REUSE_FITS", unset = "false")) == "true",

  # Model-implied interval used in diagnostic outputs.
  interval_level = 0.90
)
