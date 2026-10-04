packages <- c("data.table", "jsonlite", "ggplot2")
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  install.packages(missing, repos = "https://cloud.r-project.org")
}
message("Packages ready: ", paste(packages, collapse = ", "))
