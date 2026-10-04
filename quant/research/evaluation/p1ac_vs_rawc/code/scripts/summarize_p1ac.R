suppressPackageStartupMessages(library(data.table))
out_dir <- Sys.getenv("VALTIDE_OUTPUT_DIR", unset = "outputs/p1a_c")
metrics_path <- file.path(out_dir, "test_interval_metrics.csv")
if (!file.exists(metrics_path)) stop("Missing test_interval_metrics.csv in ", out_dir, call. = FALSE)
m <- fread(metrics_path)
primary <- m[session_state == "ALL" & abs(level - 0.90) < 1e-12]
cat("\nP1a-C 90% interval performance (ALL sessions with observable underlying labels)\n")
print(primary[, .(candidate, n, coverage, coverage_error, mean_width_bps, mean_interval_score_bps, MAE_bps, RMSE_bps)])
boot_path <- file.path(out_dir, "test_block_bootstrap_vs_gaussian.csv")
if (file.exists(boot_path)) {
  cat("\nBlock-bootstrap P1a-C minus Gaussian comparison\n")
  print(fread(boot_path))
}
stress_path <- file.path(out_dir, "pseudo_closure_metrics.csv")
if (file.exists(stress_path)) {
  cat("\nPseudo-closure stress metrics\n")
  print(fread(stress_path))
}
cat("\nFull report: ", file.path(out_dir, "p1a_c_report.json"), "\n", sep = "")
