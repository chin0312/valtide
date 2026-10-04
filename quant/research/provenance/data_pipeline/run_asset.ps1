param(
  [Parameter(Mandatory=$true)][string]$XStock,
  [Parameter(Mandatory=$true)][string]$Underlying,
  [string]$StartUtc = "",
  [string]$EndUtc = "",
  [string]$Network = "Solana"
)
$ErrorActionPreference = "Stop"
$env:XSTOCK_SYMBOL = $XStock
$env:UNDERLYING_SYMBOL = $Underlying
$env:XSTOCK_NETWORK = $Network
if ($StartUtc) { $env:DATA_START_UTC = $StartUtc }
if ($EndUtc) { $env:DATA_END_UTC = $EndUtc }
Rscript scripts/00_preflight.R
Rscript scripts/02_download_data.R
Rscript scripts/03_build_export.R
