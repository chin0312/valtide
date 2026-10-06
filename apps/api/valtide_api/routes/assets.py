"""GET /api/assets — catalog entries with independent readiness dimensions."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from valtide_api import publisher
from valtide_api.assets import (
    AssetConfigurationError,
    api_asset_configs,
    inspect_historical_panel,
)
from valtide_api.challenger_detector import (
    resolve_challenger_detector,
    resolve_tri_source_state_capability,
)
from valtide_api.config import get_settings, scheduler_asset_enabled
from valtide_api.quant_runtime import quant_runtime_available
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    get_runtime_store,
    runtime_identity_for_asset,
)

router = APIRouter(prefix="/api", tags=["assets"])


class AssetInfo(BaseModel):
    asset: str
    token_source: str
    underlying_source: str
    reference_profile: str
    registered: bool = True
    api_exposed: bool = True
    model_available: bool
    quant_artifact_ready: bool
    historical_data_available: bool
    historical_panel_file_available: bool
    canonical_panel_verified: bool
    historical_replay_ready: bool
    historical_replay_mode: str | None = None
    historical_panel_error_code: str | None = None
    challenger_detector_status: str
    evidence_state_capability: str
    live_data_configured: bool
    live_market_data_available: bool
    runtime_ready: bool
    operational_ready: bool
    operational_scheduler_enabled: bool
    latest_observation_timestamp: datetime | None = None
    latest_observation_age_seconds: int | None = None
    latest_observation_freshness: str = "unavailable"
    onchain_binding_configured: bool
    readiness_error_codes: list[str]


def _live_data_configured(config, settings) -> bool:
    return bool(
        config.capabilities.live_data
        and settings.okx_api_key
        and settings.okx_api_secret
        and settings.okx_api_passphrase
        and settings.alpaca_api_key
        and settings.alpaca_api_secret
        and (
            (config.okx_chain_index and config.token_address)
            or config.allow_token_discovery
        )
    )


def _onchain_binding_configured(config, settings) -> bool:
    if not config.capabilities.onchain:
        return False
    try:
        publisher.resolve_asset_deployment(config.asset, settings)
    except (publisher.PublisherError, AssetConfigurationError, ValueError):
        return False
    return True


def _evidence_state_capability(asset: str) -> tuple[str, str, bool]:
    """Expose frozen detector status and the separate tri-source state authority."""
    try:
        detector = resolve_challenger_detector(asset)
        capability = resolve_tri_source_state_capability(asset)
    except (KeyError, TypeError, ValueError):
        return "DETECTOR_ARTIFACT_INVALID", "ABSTAIN_ONLY", False
    if detector is None or capability is None:
        return "DETECTOR_UNAVAILABLE", "ABSTAIN_ONLY", False
    if capability.support_enabled and capability.challenge_enabled:
        state_capability = "TRI_SOURCE_SUPPORTED_AND_CHALLENGED"
    elif capability.support_enabled:
        state_capability = "TRI_SOURCE_SUPPORTED_ONLY"
    elif capability.challenge_enabled:
        state_capability = "TRI_SOURCE_CHALLENGED_ONLY"
    else:
        state_capability = "ABSTAIN_ONLY"
    return detector.promotion_status, state_capability, True


@router.get("/assets", response_model=list[AssetInfo])
def list_assets() -> list[AssetInfo]:
    settings = get_settings()
    store = get_runtime_store()
    items: list[AssetInfo] = []
    for config in api_asset_configs():
        detector_status, evidence_capability, detector_ready = (
            _evidence_state_capability(config.asset)
        )
        quant_ready = quant_runtime_available(config)
        panel_status = inspect_historical_panel(config, settings)
        panel_file_available = panel_status.file_available
        canonical_panel_verified = panel_status.canonical_identity_verified
        historical_replay_ready = bool(
            config.capabilities.historical_data
            and panel_status.replay_compatible
            and quant_ready
        )
        historical_replay_mode = (
            "canonical"
            if historical_replay_ready and canonical_panel_verified
            else "legacy_diagnostic"
            if historical_replay_ready
            else None
        )
        live_configured = _live_data_configured(config, settings)
        scheduler_selected = scheduler_asset_enabled(settings, config.asset)
        scheduler_enabled = bool(
            scheduler_selected
            and config.capabilities.runtime
            and config.capabilities.live_data
            and quant_ready
        )
        onchain_configured = _onchain_binding_configured(config, settings)
        try:
            record = (
                store.load_runtime(
                    config.asset,
                    expected_identity=runtime_identity_for_asset(config.asset, settings),
                )
                if quant_ready and config.capabilities.runtime
                else None
            )
        except RuntimeStateIntegrityError:
            record = None
        result = record.latest_result if record is not None else None
        timestamp = result.timestamp if result is not None else None
        age_seconds = (
            max(0, int((datetime.now(UTC) - timestamp).total_seconds()))
            if timestamp is not None
            else None
        )
        freshness = (
            "fresh" if age_seconds is not None and age_seconds <= 900
            else "stale" if age_seconds is not None
            else "unavailable"
        )
        live_observation_available = bool(
            live_configured
            and result is not None
            and result.asset == config.asset
            and result.token_source == config.token_source
            and result.reference_profile == config.reference_profile
            and result.token_observed_at is not None
            and freshness == "fresh"
        )

        readiness_errors: list[str] = []
        if not live_configured:
            readiness_errors.append("LIVE_DATA_CONFIGURATION_INCOMPLETE")
        elif not live_observation_available:
            readiness_errors.append("LIVE_MARKET_DATA_NOT_OBSERVED")
        if not config.capabilities.quant:
            readiness_errors.append("MODEL_FIT_BLOCKED")
        elif not quant_ready:
            readiness_errors.append("QUANT_ARTIFACT_UNAVAILABLE")
        if not detector_ready:
            readiness_errors.append("CHALLENGER_DETECTOR_UNAVAILABLE")
        if panel_status.error_code:
            readiness_errors.append(panel_status.error_code)
        if not historical_replay_ready:
            readiness_errors.append("HISTORICAL_DATA_UNAVAILABLE")
        if not config.capabilities.runtime or not quant_ready:
            readiness_errors.append("RUNTIME_NOT_READY")
        if not scheduler_selected:
            readiness_errors.append("SCHEDULER_NOT_ENABLED")
        elif not scheduler_enabled:
            readiness_errors.append("SCHEDULER_ASSET_NOT_READY")
        if config.capabilities.onchain and not onchain_configured:
            readiness_errors.append("ONCHAIN_BINDING_UNAVAILABLE")

        runtime_ready = config.capabilities.runtime and quant_ready
        items.append(
            AssetInfo(
                asset=config.asset,
                token_source=config.token_source,
                underlying_source=config.underlying_source,
                reference_profile=config.reference_profile,
                model_available=quant_ready,
                quant_artifact_ready=quant_ready,
                # Backward-compatible field now means the replay path can
                # actually execute, not merely that an arbitrary CSV exists.
                historical_data_available=historical_replay_ready,
                historical_panel_file_available=panel_file_available,
                canonical_panel_verified=canonical_panel_verified,
                historical_replay_ready=historical_replay_ready,
                historical_replay_mode=historical_replay_mode,
                historical_panel_error_code=panel_status.error_code,
                challenger_detector_status=detector_status,
                evidence_state_capability=evidence_capability,
                live_data_configured=live_configured,
                live_market_data_available=live_observation_available,
                runtime_ready=runtime_ready,
                operational_ready=bool(
                    live_observation_available
                    and runtime_ready
                    and scheduler_enabled
                    and result is not None
                    and freshness == "fresh"
                ),
                operational_scheduler_enabled=scheduler_enabled,
                latest_observation_timestamp=timestamp,
                latest_observation_age_seconds=age_seconds,
                latest_observation_freshness=freshness,
                onchain_binding_configured=onchain_configured,
                readiness_error_codes=readiness_errors,
            )
        )
    return items
