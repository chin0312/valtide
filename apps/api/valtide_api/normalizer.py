"""Normalization invariants shared across data sources.

Each data source (scenario, panel, live) assembles its own MarketSnapshot
because the raw shapes differ, but they all reason about token-unit sanity the
same way here so behaviour can't drift between them.

P0 corporate-action rule (from James's pipeline README): do NOT blindly rescale
the token price by a multiplier. A tokenized equity should trade at ~1x its
underlying, so a *gross* deviation (e.g. >2x or <0.5x) signals a unit/rebase
problem in the feed rather than an economic move.

Crucially, a *moderate* divergence is a real economic basis (a depeg) and must
flow through to the Evidence State as a normal CHALLENGED judgment — the product
must never blind itself to a depeg. This helper therefore only flags the gross,
almost-certainly-non-economic case; validation decides the rest.
"""

from __future__ import annotations

# Ratios outside this band are treated as a unit/feed problem, not economics.
# A cents-vs-dollars error is ~100x and a rebase ~2x; a genuine depeg is far
# smaller and stays inside the band so the reference comparison judges it.
_UNIT_SCALE_LOW = 0.5
_UNIT_SCALE_HIGH = 2.0


def is_unit_scale_suspect(
    token_price: float | None,
    underlying_price: float | None,
    *,
    low: float = _UNIT_SCALE_LOW,
    high: float = _UNIT_SCALE_HIGH,
) -> bool:
    """Return True when token/underlying is so far from 1 it is a probable unit bug.

    A no-op (False) when either price is missing or the underlying is non-positive,
    mirroring the old "no NVDA, no check" behaviour. Moderate economic divergence
    stays False so the reference comparison, not this guard, judges the depeg.
    """
    if token_price is None or underlying_price is None or underlying_price <= 0:
        return False
    ratio = token_price / underlying_price
    return ratio < low or ratio > high
