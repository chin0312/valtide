"""Fetch a small real data sample so the backend can be tested end-to-end.

Pulls, for a recent window:
  - NVDAx 5-minute candles from OKX OnchainOS   (needs OKX key — you have it)
  - NVDA 5-minute bars from Alpaca              (needs Alpaca key)
  - the current OKX X-Perp NVDA index price     (public, no key)

Writes CSVs to data/sample/. OKX + X-Perp work with what you have now; NVDA
activates once ALPACA_API_KEY / ALPACA_API_SECRET are set in .env.

Run from repo root:
    python scripts/fetch_data.py
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make the api package importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from valtide_api.adapters import dexscreener, equity, okx, reference
from valtide_api.config import get_settings

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
WINDOW_HOURS = 48


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        print(f"  (no rows) {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {len(rows):>5} rows -> {path.relative_to(OUT_DIR.parents[1])}")


def fetch_nvdax(start: datetime, end: datetime) -> None:
    print("OKX NVDAx candles:")
    deployments = okx.discover_nvdax()
    if not deployments:
        print("  no NVDAx deployment found")
        return
    top = deployments[0]
    chain = str(top.get("chainIndex") or top.get("chainId") or "")
    addr = top.get("tokenContractAddress") or top.get("tokenAddress") or ""
    print(f"  deployment: chain={chain} address={addr}")
    candles = okx.get_historical_candles(chain, addr, start, end)
    _write_csv(
        OUT_DIR / "nvdax_5m.csv",
        [
            {
                "ts": c.ts.isoformat(),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "volume_usd": c.volume_usd,
            }
            for c in candles
        ],
    )


def fetch_nvda(start: datetime, end: datetime) -> None:
    print("Alpaca NVDA bars:")
    settings = get_settings()
    if not settings.alpaca_api_key:
        print("  skipped — ALPACA_API_KEY not set yet")
        return
    bars = equity.get_stock_bars("NVDA", start, end)
    _write_csv(
        OUT_DIR / "nvda_5m.csv",
        [
            {
                "ts": b.ts.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
                "vwap": b.vwap,
            }
            for b in bars
        ],
    )


def fetch_xperp() -> None:
    print("OKX X-Perp NVDA index (current):")
    obs = reference.get_okx_xperp_index()
    if obs is None:
        print("  unavailable")
        return
    _write_csv(
        OUT_DIR / "xperp_index.csv",
        [{"ts": obs.ts.isoformat(), "source": obs.source, "price": obs.price}],
    )


def fetch_dexscreener() -> None:
    print("DexScreener NVDAx price (current, no key):")
    q = dexscreener.get_nvdax_price(address=get_settings().dexscreener_nvdax_address or None)
    if q is None:
        print("  unavailable (set DEXSCREENER_NVDAX_ADDRESS for a precise lookup)")
        return
    _write_csv(
        OUT_DIR / "dexscreener_nvdax.csv",
        [
            {
                "ts": q.ts.isoformat(),
                "source": q.source,
                "price": q.price,
                "liquidity_usd": q.liquidity_usd,
                "chain": q.chain,
            }
        ],
    )


def _safe(label: str, fn) -> None:
    """Run a fetch step, reporting failure without aborting the others."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - diagnostic script, show everything
        print(f"  FAILED ({type(exc).__name__}): {exc}")


def main() -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=WINDOW_HOURS)
    print(f"Window: {start.isoformat()} -> {end.isoformat()}\n")
    _safe("nvdax", lambda: fetch_nvdax(start, end))
    _safe("nvda", lambda: fetch_nvda(start, end))
    _safe("xperp", fetch_xperp)
    _safe("dexscreener", fetch_dexscreener)
    print("\nDone. Sample data in data/sample/")


if __name__ == "__main__":
    main()
