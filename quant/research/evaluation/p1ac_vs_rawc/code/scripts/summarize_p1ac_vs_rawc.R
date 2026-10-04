suppressPackageStartupMessages(library(data.table))

out_dir <- Sys.getenv("VALTIDE_OUTPUT_DIR", unset = "outputs/p1a_c")

cmp_path <- file.path(out_dir, "test_interval_metrics_comparison.csv")
pt_path <- file.path(out_dir, "test_point_estimate_comparison.csv")
boot_path <- file.path(out_dir, "test_block_bootstrap_rawc_vs_p1ac.csv")
stress_path <- file.path(out_dir, "pseudo_closure_comparison.csv")
report_path <- file.path(out_dir, "p1ac_vs_rawc_report.json")

if (!file.exists(cmp_path)) stop("Missing test_interval_metrics_comparison.csv in ", out_dir, call. = FALSE)

if (file.exists(pt_path)) {
  cat("\nPoint-estimate comparison on identical labeled test rows\n")
  p <- fread(pt_path)
  print(p[session_state == "ALL"])
}

m <- fread(cmp_path)
primary <- m[session_state == "ALL" & abs(level - 0.90) < 1e-12]
cat("\n90% interval comparison\n")
print(primary[, .(
  candidate, n, coverage, coverage_error,
  mean_width_bps, mean_interval_score_bps, MAE_bps, RMSE_bps
)])

if (file.exists(boot_path)) {
  cat("\nBlock-bootstrap Raw-xStock-C minus P1a-C comparison\n")
  cat("Negative score difference favors Raw-xStock-C.\n")
  print(fread(boot_path))
}

if (file.exists(stress_path)) {
  cat("\nPseudo-closure comparison\n")
  print(fread(stress_path))
}

cat("\nFull comparison report: ", report_path, "\n", sep = "")
