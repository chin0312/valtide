"""Canonical data shapes — the contract between all backend modules.

See docs/BACKEND_ARCHITECTURE.md. These shapes are the stable interface the frontend
and X Layer publisher build against; internal modules must not invent their own.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from valtide_api.assets import supported_asset_names

# Compatibility export for existing route/import callers.  The registry in
# assets.py is the source of truth; this derived immutable set prevents routes
# from drifting into their own asset lists.
SUPPORTED_ASSETS = frozenset(supported_asset_names())


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

    # Current underlying-equity observation for this asset when available.
    underlying_reference: float | None = None
    underlying_reference_ts: datetime | None = None

    # Latest available trusted underlying bar (R0) — always present.
    last_trusted_reference: float
    last_trusted_reference_ts: datetime
    reference_age_seconds: int

    # Compatibility comparator retained for existing API consumers. In the
    # unified profile the validation target is xStock; OKX X-Perp is separate
    # market evidence, not the primary reference-under-test.
    reference_under_test: float | None
    reference_under_test_source: str = Field(examples=["nvda_live", "okx_xperp_index"])
    reference_profile: str = "unspecified"
    reference_under_test_ts: datetime | None = None
    reference_under_test_age_seconds: int | None = None

    # Preserve separately sourced OKX X-Perp/index evidence explicitly. It is a
    # second market challenger in the unified profile; no Gaussian residual
    # calibration is implied.
    xperp_index_price: float | None = None
    xperp_index_source: str | None = None
    xperp_index_ts: datetime | None = None

    market_state: MarketState

    # P0: kept at 1.0; validation flags only a gross token/underlying unit mismatch
    # (TOKEN_UNIT_SUSPECT) instead of blindly rescaling (see James's pipeline
    # README). A moderate economic divergence is judged as normal evidence.
    corporate_action_multiplier: float = 1.0
    external_reference: float | None = None  # optional Pyth, comparison only

    source_provenance: dict[str, str] = Field(default_factory=dict)


class ChallengerEstimate(BaseModel):
    """Output of the asset-specific quant runtime's model-based challenger.

    Carries the log-space state directly so validation never has to reverse-
    engineer sigma from asymmetric price bounds. See docs/BACKEND_ARCHITECTURE.md.
    """

    fair_value: float  # exp(state_m)
    lower_bound: float  # price-space interval (may be asymmetric)
    upper_bound: float
    state_m: float  # posterior mean in LOG space
    state_sd_log: float  # sqrt(P_t) in LOG space — latent-state uncertainty
    reference_predictive_sd_log: float  # sqrt(P_t + R_nvda), used for validation
    coverage_target: float
    interval_calibration_type: str = "session_sym"
    interval_calibration_source: str = "global"

    # Legacy field name: state after folding in the current underlying, carried
    # into the next step for every asset.
    state_m_after_nvda: float
    state_P_after_nvda: float
    model_id: str
    model_version: str
    interval_semantics: str


class ChallengerDetectorEvidence(BaseModel):
    """Frozen research score band kept separate from canonical Evidence State."""

    artifact_version: str
    score_name: str
    score: float | None
    review_threshold: float
    challenge_threshold: float
    research_band: str
    promotion_status: str


class ValuationResult(BaseModel):
    """The public asset-scoped result served to clients and optional publisher.

    See docs/BACKEND_ARCHITECTURE.md.
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
    reference_profile: str = "unspecified"
    reference_under_test_ts: datetime | None = None
    reference_under_test_age_seconds: int | None = None
    reference_deviation_pct: float | None
    standardized_deviation: float | None  # log-space z-score

    # Explicit pairwise diagnostics. They are descriptive quantities only and
    # are not additional threshold inputs to Evidence State.
    xperp_index_price: float | None = None
    xperp_index_source: str | None = None
    xperp_index_ts: datetime | None = None
    xstock_vs_p1ac_deviation_pct: float | None = None
    xperp_vs_p1ac_deviation_pct: float | None = None
    xstock_vs_xperp_deviation_pct: float | None = None
    xperp_deviation_scaled_by_model_predictive_sd: float | None = None
    evidence_state_basis: str = "selected_reference_under_test"
    # Additive semantic identity. Defaults keep old persisted result JSON
    # readable while new unified-profile results identify their actual target.
    validation_target: str = "reference_under_test"
    evidence_semantics: str = "legacy_reference_under_test_v1"
    xperp_role: str = "reference_under_test"
    challenger_detector: ChallengerDetectorEvidence | None = None

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
