"""Canonical data shapes — the contract between all backend modules.

See docs/BACKEND_PLAN.md §5. These shapes are the stable interface the frontend
and X Layer publisher build against; internal modules must not invent their own.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# Assets the backend supports today. One place so routes don't drift.
SUPPORTED_ASSETS = {"NVDAx"}


class MarketState(str, Enum):
    """Market session for the observation timestamp (see session.py).

    The frontend may collapse PREMARKET/AFTERHOURS into a public "extended"
    state; the backend keeps the five research regimes.
    """

    REGULAR = "regular"
    PREMARKET = "premarket"
    AFTERHOURS = "afterhours"
    OVERNIGHT = "overnight"
    CLOSED = "closed"


class EvidenceState(str, Enum):
    """Canonical three-way validation decision (PRD vocabulary).

    This is what the X Layer contract enum and the frontend expect. The backend
    determines the evidence state; a consuming protocol owns any policy action
    taken in response.
    """

    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    CHALLENGED = "CHALLENGED"


class MarketSnapshot(BaseModel):
    """Normalized point-in-time market information — the model input.

    Produced by normalizer.py from raw adapter outputs. All timestamps UTC.
    """

    asset: str = Field(examples=["NVDAx"])
    observation_ts: datetime

    token_price: float | None
    token_volume: float | None = None
    token_volume_usd: float | None = None
    token_source: str | None = None
    token_observed_at: datetime | None = None
    # DEX pool depth in USD when the token source reports it (live path). Used by
    # validation as a market-quality floor; None where a source omits it.
    token_liquidity_usd: float | None = None

    # Current NVDA if the market is open, else None (weekend/overnight).
    underlying_reference: float | None = None
    underlying_reference_ts: datetime | None = None

    # Latest available trusted underlying bar (R0) — always present.
    last_trusted_reference: float
    last_trusted_reference_ts: datetime
    reference_age_seconds: int

    # The reference under test (Pt) — what we validate. Sourced explicitly; never
    # implicitly derived. See BACKEND_PLAN.md §3.
    reference_under_test: float | None
    reference_under_test_source: str = Field(examples=["nvda_live", "okx_xperp_index"])
    reference_under_test_ts: datetime | None = None
    reference_under_test_age_seconds: int | None = None

    market_state: MarketState

    # P0: kept at 1.0; validation flags only a gross NVDAx/NVDA unit mismatch
    # (TOKEN_UNIT_SUSPECT) instead of blindly rescaling (see James's pipeline
    # README). A moderate economic divergence is judged as normal evidence.
    corporate_action_multiplier: float = 1.0
    external_reference: float | None = None  # optional Pyth, comparison only

    source_provenance: dict[str, str] = Field(default_factory=dict)


class ChallengerEstimate(BaseModel):
    """Output of the quant runtime — the independent (NVDAx-only) challenger.

    Carries the log-space state directly so validation never has to reverse-
    engineer sigma from asymmetric price bounds. See BACKEND_PLAN.md §5.2 / §7.
    """

    fair_value: float  # exp(state_m)
    lower_bound: float  # price-space interval (may be asymmetric)
    upper_bound: float
    state_m: float  # posterior mean in LOG space (NVDAx-only)
    state_sd_log: float  # sqrt(P_t) in LOG space — latent-state uncertainty
    reference_predictive_sd_log: float  # sqrt(P_t + R_nvda), used for validation
    coverage_target: float
    interval_calibration_type: str = "session_sym"
    interval_calibration_source: str = "global"

    # State AFTER folding in NVDA (if present), carried into the next step.
    state_m_after_nvda: float
    state_P_after_nvda: float
    model_id: str
    model_version: str
    interval_semantics: str


class ValuationResult(BaseModel):
    """The public result served to the frontend and X Layer publisher.

    See BACKEND_PLAN.md §5.3.
    """

    asset: str
    timestamp: datetime
    market_state: str

    last_trusted_reference: float
    token_price: float | None
    token_source: str | None = None
    token_observed_at: datetime | None = None
    token_volume: float | None = None
    token_volume_usd: float | None = None
    token_liquidity_usd: float | None = None
    external_constructed_reference: float | None = None

    valtide_fair_value: float
    fair_value_lower: float
    fair_value_upper: float
    interval_coverage_target: float

    observed_token_move_pct: float | None
    model_implied_move_pct: float
    residual_premium_discount_pct: float | None

    reference_under_test: float | None
    reference_under_test_source: str
    reference_under_test_ts: datetime | None = None
    reference_under_test_age_seconds: int | None = None
    reference_deviation_pct: float | None
    standardized_deviation: float | None  # log-space z-score

    evidence_state: EvidenceState
    reason_codes: list[str] = Field(default_factory=list)

    # Intentionally null in P0 — no calibrated 0-100 methodology defined yet.
    confidence: int | None = None

    model_id: str
    model_version: str
    interval_semantics: str
    interval_calibration_type: str = "session_sym"
    interval_calibration_source: str = "global"
    reference_age_seconds: int
    source_provenance: dict[str, str] = Field(default_factory=dict)
