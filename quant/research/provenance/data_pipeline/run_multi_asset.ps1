param(
  [string]$StartUtc = "2025-07-01T00:00:00Z",
  [string]$EndUtc = "2026-09-20T23:59:59Z"
)
$ErrorActionPreference = "Stop"

$assets = @(
  @{ XStock = "NVDAx"; Underlying = "NVDA" },
  @{ XStock = "SPYx";  Underlying = "SPY"  },
  @{ XStock = "QQQx";  Underlying = "QQQ"  },
  @{ XStock = "TSLAx"; Underlying = "TSLA" },
  @{ XStock = "AAPLx"; Underlying = "AAPL" }
)

foreach ($asset in $assets) {
  Write-Host "=== $($asset.XStock) / $($asset.Underlying) on Solana (chainIndex 501) ==="
  .\run_asset.ps1 -XStock $asset.XStock -Underlying $asset.Underlying `
    -StartUtc $StartUtc -EndUtc $EndUtc -Network "Solana"
}

Write-Host "All five local Solana exports completed. Inspect exports/<asset>/ before GCP upload."
