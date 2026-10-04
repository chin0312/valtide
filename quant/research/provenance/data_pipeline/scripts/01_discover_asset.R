source("R/utils.R")
source("R/api_okx.R")
settings <- asset_settings()
raw_dir <- file.path("data/raw", settings$slug)
dir.create(raw_dir, recursive = TRUE, showWarnings = FALSE)

matches <- discover_xstock(settings$xstock, settings$underlying)
target_chain <- network_chain_index(settings$network)
matches[, target_network := as.character(chainIndex) == target_chain]
data.table::fwrite(matches, file.path(raw_dir, "okx_deployments.csv"))

network_matches <- matches[as.character(chainIndex) == target_chain]
if (!nrow(network_matches)) {
  stop(sprintf("No %s deployment (chainIndex=%s) found for %s / %s.", settings$network, target_chain, settings$xstock, settings$underlying), call. = FALSE)
}

cols <- intersect(c("chainIndex", "tokenSymbol", "stockCode", "tokenContractAddress", "volume24h", "price", "stockPrice", "tokenToAssetRatio", "target_network"), names(matches))
print(matches[, ..cols])
message("Saved all deployment candidates to ", file.path(raw_dir, "okx_deployments.csv"))
message("Target network: ", settings$network, " (chainIndex=", target_chain, ")")
message("Highest-volume matching deployment on target network:")
print(network_matches[1, ..cols])
