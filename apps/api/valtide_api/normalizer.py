"""Normalization invariants shared across data sources.

Each data source (scenario, panel, live) assembles its own MarketSnapshot
because the raw shapes differ, but they all enforce the same invariant here so
behaviour can't drift between them.

P0 corporate-action rule (from James's pipeline README): do NOT blindly rescale
the token price by a multiplier. Instead assert the NVDAx/NVDA price scale is
~1; a large divergence means a unit problem to resolve before trusting output.
"""

from __future__ import annotations

# If token/underlying prices differ by more than this fraction during overlap,
# there is likely a token-unit (rebase/multiplier) problem, not an economic move.
_SCALE_TOLERANCE = 0.05


class ScaleMismatchError(ValueError):
    """Raised when the NVDAx/NVDA price scale is not ~1 (unit problem)."""


def assert_scale(token_price: float, nvda_price: float | None) -> None:
    """Fail loudly if NVDAx/NVDA scale is off (no-op when NVDA is absent).

    P0 does not rescale the token by a multiplier; instead it asserts the scale
    is ~1, per James's pipeline README. Reused by the panel and live paths.
    """
    if nvda_price is None or nvda_price <= 0:
        return
    ratio = token_price / nvda_price
    if abs(ratio - 1.0) > _SCALE_TOLERANCE:
        raise ScaleMismatchError(
            f"NVDAx/NVDA scale {ratio:.4f} deviates from 1 beyond tolerance "
            f"{_SCALE_TOLERANCE}; resolve token-unit normalization before trusting output."
        )
