packages <- c("data.table", "httr2", "jsonlite", "lubridate", "digest", "openssl")
project_library <- .libPaths()[1]
missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) install.packages(missing, lib = project_library, dependencies = NA)
still_missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(still_missing)) stop("Package installation failed: ", paste(still_missing, collapse = ", "))
message("Packages ready: ", paste(packages, collapse = ", "))
