"""Thin adapter from backend snapshots to the packaged P1a-C quant service.

The quant package owns model execution, calibrated intervals, and carried state.
This module only translates backend objects at the integration boundary; product
validation remains in :mod:`valtide_api.validation`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType

from valtide_quant_service import (
    FilterState,
    QuantService,
    StateGapError,
)
from valtide_quant_service import (
    MarketSnapshot as QuantMarketSnapshot,
)
from valtide_quant_service.artifacts import load_p1a

from valtide_api.assets import AssetConfig, AssetConfigurationError, resolve_asset_config
from valtide_api.models import ChallengerEstimate, MarketSnapshot


@dataclass(frozen=True)
class QuantRuntimeSpec:
    asset: str
    model_id: str
    model_version: str
    factory: Callable[[FilterState | None], QuantService]


@dataclass(frozen=True)
class _RuntimeRegistration:
    factory: Callable[[FilterState | None], QuantService]
    artifact_identity: Callable[[], tuple[str, str, str]]


def _default_artifact_identity() -> tuple[str, str, str]:
    path = resources.files("valtide_quant_service").joinpath(
        "model_artifacts/p1a_runtime.json"
    )
    artifact = load_p1a(path)
    return artifact.asset, artifact.deployment_model_id, artifact.model_version


def _bundle_registration(bundle: str) -> _RuntimeRegistration:
    root = Path(str(resources.files("valtide_quant_service").joinpath("model_artifacts", bundle)))
    model_path = root / "p1a_runtime.json"
    calibrator_path = root / "p1a_c_calibrator.json"

    def identity() -> tuple[str, str, str]:
        artifact = load_p1a(model_path)
        return artifact.asset, artifact.deployment_model_id, artifact.model_version

    def factory(state: FilterState | None = None) -> QuantService:
        return QuantService.from_artifacts(model_path, calibrator_path, state=state)

    return _RuntimeRegistration(factory, identity)


_QUANT_RUNTIME_FACTORIES = MappingProxyType(
    {
        "nvdax_p1ac_default": _RuntimeRegistration(
            QuantService.from_default_artifacts, _default_artifact_identity
        ),
        "spyx_p1ac_v030": _bundle_registration("spyx"),
        "qqqx_p1ac_v030": _bundle_registration("qqqx"),
        "aaplx_p1ac_v030": _bundle_registration("aaplx"),
    }
)


@lru_cache(maxsize=8)
def _artifact_identity(runtime_key: str) -> tuple[str, str, str]:
    registration = _QUANT_RUNTIME_FACTORIES.get(runtime_key)
    if registration is None:
        raise AssetConfigurationError(f"unknown quant runtime '{runtime_key}'")
    try:
        return registration.artifact_identity()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise AssetConfigurationError("quant artifact metadata is unavailable") from exc


def resolve_quant_runtime(asset: str | AssetConfig) -> QuantRuntimeSpec:
    config = asset if isinstance(asset, AssetConfig) else resolve_asset_config(asset)
    if not config.capabilities.quant:
        raise AssetConfigurationError(f"quant runtime is unavailable for '{config.asset}'")
    registration = _QUANT_RUNTIME_FACTORIES.get(config.quant_runtime_key)
    if registration is None:
        raise AssetConfigurationError(f"unknown quant runtime '{config.quant_runtime_key}'")
    artifact_asset, model_id, model_version = _artifact_identity(config.quant_runtime_key)
    if artifact_asset != config.asset:
        raise AssetConfigurationError("quant artifact asset does not match requested asset")
    return QuantRuntimeSpec(config.asset, model_id, model_version, registration.factory)


def quant_runtime_available(config: AssetConfig) -> bool:
    try:
        resolve_quant_runtime(config)
    except AssetConfigurationError:
        return False
    return True


def get_quant_service(
    asset: str | AssetConfig,
    *,
    state: FilterState | None = None,
) -> QuantService:
    """Resolve the explicitly registered quant artifact for ``asset``.

    Each asset resolves only its explicitly registered, identity-checked
    artifact bundle; there is no cross-asset fallback.
    """

    config = asset if isinstance(asset, AssetConfig) else resolve_asset_config(asset)
    spec = resolve_quant_runtime(config)
    try:
        service = spec.factory(state=state)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise AssetConfigurationError("registered quant artifact cannot be loaded") from exc
    artifact = service.runtime.artifact
    if (
        artifact.asset != config.asset
        or artifact.deployment_model_id != spec.model_id
        or artifact.model_version != spec.model_version
    ):
        raise AssetConfigurationError("loaded quant artifact does not match registered runtime")
    return service


def estimate(
    snapshot: MarketSnapshot,
    prior_m: float | None = None,
    prior_P: float | None = None,
    prior_ts: datetime | None = None,
) -> ChallengerEstimate:
    """Run one public P1a-C service update and translate its quantitative result.

    ``prior_m``/``prior_P``/``prior_ts`` are the backend's serialized carried
    state. The packaged service then preserves its causal order: predict,
    assimilate the selected asset's xStock observation, emit the challenger
    estimate, and only then assimilate its current underlying for the next
    timestamp.
    """
    if (prior_m is None) != (prior_P is None):
        raise ValueError("prior_m and prior_P must be provided together")

    state = (
        FilterState(m=prior_m, P=prior_P, timestamp=prior_ts)
        if prior_m is not None and prior_P is not None
        else None
    )
    asset_config = resolve_asset_config(snapshot.asset)
    service = get_quant_service(asset_config, state=state)
    quant_snapshot = QuantMarketSnapshot(
        asset=asset_config.asset,
        timestamp=snapshot.observation_ts,
        quant_session=snapshot.market_state.value,
        token_price=snapshot.token_price,
        current_underlying_price=snapshot.underlying_reference,
        last_trusted_reference=snapshot.last_trusted_reference,
        last_trusted_reference_timestamp=snapshot.last_trusted_reference_ts,
        external_constructed_reference=snapshot.external_reference,
    )
    quant_result = service.update(quant_snapshot)
    carried = quant_result.carried_state

    return ChallengerEstimate(
        fair_value=quant_result.fair_value,
        lower_bound=quant_result.lower_bound,
        upper_bound=quant_result.upper_bound,
        state_m=quant_result.challenger_m_log,
        state_sd_log=math.sqrt(quant_result.challenger_P_log),
        reference_predictive_sd_log=quant_result.reference_predictive_sd_log,
        coverage_target=quant_result.interval_coverage_target,
        interval_calibration_type=quant_result.interval_calibration_type,
        interval_calibration_source=quant_result.interval_calibration_source,
        state_m_after_nvda=carried.m,
        state_P_after_nvda=carried.P,
        model_id=quant_result.model_id,
        model_version=quant_result.model_version,
        interval_semantics=quant_result.interval_semantics,
    )


__all__ = [
    "QuantRuntimeSpec", "StateGapError", "estimate", "get_quant_service",
    "quant_runtime_available", "resolve_quant_runtime",
]
