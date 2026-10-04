P1A_C_CONFIG <- list(
  primary_level = 0.90,
  interval_levels = c(0.50, 0.80, 0.90, 0.95),
  crossfit_initial_fraction = 0.50,
  crossfit_folds = 4L,
  min_session_scores = 200L,
  coverage_tolerance = 0.03,
  bootstrap_reps = as.integer(Sys.getenv("P1AC_BOOTSTRAP_REPS", unset = "2000")),
  random_seed = 97L,
  pseudo_closure_minutes = c(30L, 60L, 120L, 240L),
  # For cross-asset tests the safe default is FALSE. Reuse is accepted only if
  # the saved fit has the same asset id and dataset SHA as the staged dataset.
  reuse_full_p1a_fit = tolower(Sys.getenv("VALTIDE_REUSE_FITS", unset = "false")) == "true"
)
