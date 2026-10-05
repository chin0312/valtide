"""Loader for canonical five-minute historical market panels."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from valtide_api.assets import AssetConfig, resolve_asset_config
from valtide_api.clock import require_canonical_5m
from valtide_api.config import Settings
from valtide_api.models import MarketSnapshot, MarketState

_NA = {"", "NA", "N/A", "NaN", "nan", "null", "None"}
_FIVE_MINUTES = 300


class PanelTimestampError(ValueError):
    """Raised when a panel is not an ordered canonical 5-minute sequence."""


class PanelIdentityError(ValueError):
    """Raised when a panel's source identity does not match the requested asset."""


@dataclass(frozen=True)
class PanelReadiness:
    """Cheap-to-query panel identity/readiness result (no model replay)."""

    file_available: bool
    schema: str | None = None
    canonical_identity_verified: bool = False
    replay_compatible: bool = False
    error_code: str | None = None


_CANONICAL_IDENTITY = (
    "asset", "underlying_symbol", "token_source", "token_chain_index",
    "token_address", "reference_under_test_instrument", "reference_under_test_source",
)
_CANONICAL_SCHEMA_MARKERS = (
    frozenset(_CANONICAL_IDENTITY)
    - {"reference_under_test_source"}
    | frozenset({
        "token_close", "token_volume", "token_volume_usd", "token_available",
        "token_observed_at", "underlying_close", "underlying_available",
        "underlying_observed_at",
    })
)
_LEGACY_SCHEMA_MARKERS = frozenset({
    "nvda_close", "nvdax_close", "nvda_available", "nvdax_available",
    "nvda_volume", "nvdax_volume", "nvdax_volume_usd",
})


def _panel_schema(fields: set[str]) -> str:
    """Classify canonical and legacy schemas without allowing hybrid fallback."""
    has_canonical_identity = bool(fields & _CANONICAL_SCHEMA_MARKERS)
    has_legacy_fields = bool(fields & _LEGACY_SCHEMA_MARKERS)
    if has_canonical_identity:
        if has_legacy_fields:
            return "canonical_hybrid"
        return "canonical"
    if {"nvda_close", "nvdax_close"}.issubset(fields):
        return "legacy_nvda_diagnostic"
    raise PanelIdentityError("panel does not match a supported canonical or legacy schema")


def _canonical_row(row: dict[str, str], config: AssetConfig, *, legacy: bool) -> dict[str, str]:
    if legacy:
        if config.asset != "NVDAx":
            raise PanelIdentityError("legacy NVDA panel cannot be loaded for another asset")
        if row.get("reference_under_test_source") not in (
            None, "", config.reference_under_test_source
        ):
            raise PanelIdentityError("legacy panel reference source does not match requested asset")
        return {
            **row,
            "asset": "NVDAx",
            "underlying_symbol": "NVDA",
            "token_source": config.token_source,
            "token_close": row.get("nvdax_close", ""),
            "token_volume": row.get("nvdax_volume", ""),
            "token_volume_usd": row.get("nvdax_volume_usd", ""),
            "token_available": row.get("nvdax_available", ""),
            "underlying_close": row.get("nvda_close", ""),
            "underlying_available": row.get("nvda_available", ""),
        }
    expected = {
        "asset": config.asset,
        "underlying_symbol": config.underlying_symbol,
        "token_source": config.token_source,
        "reference_under_test_instrument": config.reference_under_test_instrument,
        "reference_under_test_source": config.reference_under_test_source,
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise PanelIdentityError("canonical panel identity does not match requested asset")
    panel_profile = (row.get("reference_profile") or "").strip()
    if panel_profile and panel_profile != config.reference_profile:
        raise PanelIdentityError("canonical panel reference profile does not match requested asset")
    if not panel_profile and config.reference_profile != "legacy_xperp_vs_p1ac":
        raise PanelIdentityError("canonical panel is missing its reference-profile identity")
    if not row.get("token_chain_index") or not row.get("token_address"):
        raise PanelIdentityError("canonical panel has no token deployment identity")
    if row["token_chain_index"] != config.okx_chain_index:
        raise PanelIdentityError("canonical panel token chain does not match configured asset")
    if row["token_address"] != config.token_address:
        raise PanelIdentityError("canonical panel token address does not match configured asset")
    return row


def _validate_panel_header(
    schema: str,
    fields: set[str],
    config: AssetConfig,
    settings: Settings,
) -> None:
    legacy = schema == "legacy_nvda_diagnostic"
    if schema == "canonical_hybrid" and not set(_CANONICAL_IDENTITY).issubset(fields):
        raise PanelIdentityError("ambiguous hybrid canonical/legacy panel schema")
    if not legacy and not set(_CANONICAL_IDENTITY).issubset(fields):
        raise PanelIdentityError("canonical panel is missing required identity fields")
    if not legacy and config.asset == "NVDAx" and not (
        settings.okx_nvdax_chain_index and settings.okx_nvdax_token_address
    ):
        raise PanelIdentityError(
            "canonical NVDAx panel provenance is unverified; pin "
            "OKX_NVDAX_CHAIN_INDEX and OKX_NVDAX_TOKEN_ADDRESS"
        )
    if not legacy and (not config.okx_chain_index or not config.token_address):
        raise PanelIdentityError(
            "canonical panel deployment is unverified; pin OKX_NVDAX_CHAIN_INDEX "
            "and OKX_NVDAX_TOKEN_ADDRESS for offline verification"
        )
    if legacy and config.asset != "NVDAx":
        raise PanelIdentityError("legacy NVDA panel cannot be loaded for another asset")
    if not legacy and not {
        "token_close", "token_available", "underlying_close", "underlying_available",
        "reference_under_test_available", "reference_under_test_source",
    }.issubset(fields):
        raise PanelIdentityError("canonical panel is missing required market fields")


def inspect_panel_readiness(
    path: str | Path,
    *,
    asset: str,
    settings: Settings | None = None,
) -> PanelReadiness:
    """Verify panel identity and structural replayability without inference.

    The CSV is scanned once per file stat/configuration and the result is cached.
    This avoids constructing a large snapshot sequence or running the quant model
    for every `/api/assets` request while still checking identity on every row.
    """
    if settings is None:
        from valtide_api.config import get_settings

        settings = get_settings()
    try:
        config = resolve_asset_config(asset, settings)
        panel_path = Path(path).resolve(strict=True)
        stat = panel_path.stat()
    except (OSError, ValueError):
        return PanelReadiness(False, error_code="PANEL_FILE_UNAVAILABLE")

    return _inspect_panel_cached(
        str(panel_path),
        stat.st_mtime_ns,
        stat.st_size,
        config,
        str(getattr(settings, "okx_nvdax_chain_index", "") or "").strip(),
        str(getattr(settings, "okx_nvdax_token_address", "") or "").strip(),
    )


@lru_cache(maxsize=32)
def _inspect_panel_cached(
    path: str,
    _mtime_ns: int,
    _size: int,
    config: AssetConfig,
    nvda_chain_pin: str,
    nvda_address_pin: str,
) -> PanelReadiness:
    # Recreate only the two legacy NVDA pin fields needed by the shared header
    # validator. No network lookup or deployment discovery occurs here.
    from valtide_api.config import Settings

    settings = Settings(
        _env_file=None,
        okx_nvdax_chain_index=nvda_chain_pin,
        okx_nvdax_token_address=nvda_address_pin,
    )
    schema: str | None = None
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise PanelIdentityError("panel has duplicate header columns")
            fields = set(headers)
            schema = _panel_schema(fields)
            _validate_panel_header(schema, fields, config, settings)
            legacy = schema == "legacy_nvda_diagnostic"
            last_close: float | None = None
            previous_ts: datetime | None = None
            row_count = 0
            replay_rows = 0

            for raw_row in reader:
                if None in raw_row:
                    raise PanelIdentityError("panel row has more fields than its header")
                if not any(value not in (None, "") for value in raw_row.values()):
                    raise PanelIdentityError("panel contains an empty row")
                row = _canonical_row(raw_row, config, legacy=legacy)
                if schema == "canonical_hybrid":
                    # Check row identity before classifying the otherwise
                    # ambiguous schema, so an incorrect identity is never hidden.
                    raise PanelIdentityError("ambiguous hybrid canonical/legacy panel schema")
                try:
                    timestamp = require_canonical_5m(
                        _parse_ts(row["timestamp_utc"]), "panel timestamp"
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise PanelTimestampError("invalid canonical panel timestamp") from exc
                if previous_ts is not None and (timestamp - previous_ts).total_seconds() != 300:
                    raise PanelTimestampError(
                        "panel timestamps must advance by exactly 5 minutes"
                    )
                previous_ts = timestamp
                row_count += 1

                token = _num(row.get("token_close"))
                token_available = _flag(row.get("token_available"))
                underlying = (
                    _num(row.get("underlying_close"))
                    if _flag(row.get("underlying_available"))
                    else None
                )
                if token_available and token is None:
                    raise PanelIdentityError("available token observation has no price")
                if _flag(row.get("underlying_available")) and underlying is None:
                    raise PanelIdentityError("available underlying observation has no price")
                for price_field in (
                    "token_volume", "token_volume_usd", "reference_under_test",
                    "last_trusted_reference",
                ):
                    _num(row.get(price_field))

                for value_field, available, label in (
                    ("token_observed_at", token_available, "token"),
                    (
                        "underlying_observed_at",
                        _flag(row.get("underlying_available")),
                        "underlying",
                    ),
                ):
                    value = row.get(value_field)
                    if available and value and _parse_ts(value) != timestamp:
                        raise PanelIdentityError(
                            f"{label} observation does not match canonical timestamp"
                        )

                reference_available = _flag(row.get("reference_under_test_available"))
                reference = _num(row.get("reference_under_test"))
                if reference_available and reference is None:
                    raise PanelIdentityError("available reference observation has no price")
                reference_ts_value = row.get("reference_under_test_ts")
                if reference_available and reference_ts_value:
                    if _parse_ts(reference_ts_value) > timestamp:
                        raise PanelTimestampError(
                            "reference-under-test timestamp must not be after its panel observation"
                        )

                anchor = _num(row.get("last_trusted_reference"))
                anchor_ts_value = row.get("last_trusted_reference_ts")
                anchor_ts = _parse_ts(anchor_ts_value) if anchor_ts_value else None
                if anchor is not None and anchor_ts is not None and anchor_ts >= timestamp:
                    raise PanelTimestampError(
                        "last trusted reference timestamp must be strictly before "
                        "its panel observation"
                    )
                prior_anchor = last_close is not None or (
                    anchor is not None and anchor_ts is not None
                )
                if prior_anchor:
                    replay_rows += 1
                elif underlying is not None:
                    last_close = underlying
                if underlying is not None:
                    last_close = underlying

            if schema == "canonical_hybrid":
                raise PanelIdentityError("ambiguous hybrid canonical/legacy panel schema")
            if row_count < 2 or replay_rows == 0:
                return PanelReadiness(
                    True, schema, schema == "canonical" and row_count > 0, False,
                    "PANEL_HAS_NO_REPLAY_OBSERVATIONS",
                )
            return PanelReadiness(
                True,
                schema,
                schema == "canonical",
                True,
                None,
            )
    except PanelTimestampError:
        return PanelReadiness(True, schema, False, False, "PANEL_TIMESTAMP_INVALID")
    except PanelIdentityError as exc:
        message = str(exc)
        error_code = (
            "PANEL_SCHEMA_AMBIGUOUS"
            if "ambiguous" in message
            else "PANEL_IDENTITY_INVALID"
        )
        return PanelReadiness(True, schema, False, False, error_code)
    except (OSError, csv.Error, KeyError, TypeError, ValueError, OverflowError):
        return PanelReadiness(True, schema, False, False, "PANEL_FORMAT_INVALID")


def _num(value: str | None) -> float | None:
    if value is None or value.strip() in _NA:
        return None
    return float(value)


def _flag(value: str | None) -> bool:
    return (value or "").strip().upper() in {"TRUE", "T", "1"}


def _parse_ts(value: str) -> datetime:
    s = value.strip().replace(" ", "T").replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def load_panel_snapshots(
    path: str | Path,
    *,
    asset: str = "NVDAx",
    settings: Settings | None = None,
) -> list[MarketSnapshot]:
    """Build one snapshot per canonical row after an R0 anchor is established.

    Missing token observations remain in the sequence as ``token_price=None``.
    This preserves the quant runtime's 5-minute state transition without
    fabricating a token price or silently introducing a state gap. New real
    panels provide explicit reference-under-test columns. The old NVDAx panel
    format is normalized only by the contained legacy compatibility path.
    """
    if settings is None:
        from valtide_api.config import get_settings

        settings = get_settings()
    asset_config = resolve_asset_config(asset, settings)
    path = Path(path)
    snapshots: list[MarketSnapshot] = []
    last_close: float | None = None
    last_close_ts: datetime | None = None
    previous_ts: datetime | None = None

    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise PanelIdentityError("panel has duplicate header columns")
        fields = set(headers)
        schema = _panel_schema(fields)
        _validate_panel_header(schema, fields, asset_config, settings)
        legacy = schema == "legacy_nvda_diagnostic"
        for raw_row in reader:
            row = _canonical_row(raw_row, asset_config, legacy=legacy)
            if schema == "canonical_hybrid":
                raise PanelIdentityError("ambiguous hybrid canonical/legacy panel schema")
            try:
                ts = require_canonical_5m(_parse_ts(row["timestamp_utc"]), "panel timestamp")
            except ValueError as exc:
                raise PanelTimestampError(str(exc)) from exc
            if previous_ts is not None:
                delta = (ts - previous_ts).total_seconds()
                if delta != _FIVE_MINUTES:
                    raise PanelTimestampError(
                        "panel timestamps must advance by exactly 5 minutes; "
                        f"got {delta:g} seconds between {previous_ts.isoformat()} "
                        f"and {ts.isoformat()}"
                    )
            previous_ts = ts

            underlying = (
                _num(row.get("underlying_close"))
                if _flag(row.get("underlying_available")) else None
            )
            token = (
                _num(row.get("token_close")) if _flag(row.get("token_available")) else None
            )
            if token is not None and row.get("token_observed_at"):
                if _parse_ts(row["token_observed_at"]) != ts:
                    raise PanelIdentityError("token observation does not match canonical timestamp")
            if underlying is not None and row.get("underlying_observed_at"):
                if _parse_ts(row["underlying_observed_at"]) != ts:
                    raise PanelIdentityError(
                        "underlying observation does not match canonical timestamp"
                    )

            # Validate explicit provenance timestamps even on an anchor-only
            # row that will not be emitted as a public snapshot.
            if (
                "reference_under_test_available" in row
                and _flag(row.get("reference_under_test_available"))
                and row.get("reference_under_test_ts")
            ):
                reference_ts = _parse_ts(row["reference_under_test_ts"])
                if reference_ts > ts:
                    raise PanelTimestampError(
                        "reference-under-test timestamp must not be after its panel observation"
                    )

            # Capture the strictly prior trusted anchor before constructing
            # this row so the current underlying cannot become same-timestamp R0.
            previous_last_close = last_close
            previous_last_close_ts = last_close_ts
            if previous_last_close is None or previous_last_close_ts is None:
                explicit_anchor = _num(row.get("last_trusted_reference"))
                explicit_anchor_ts = (
                    _parse_ts(row["last_trusted_reference_ts"])
                    if row.get("last_trusted_reference_ts")
                    else None
                )
                if explicit_anchor is not None and explicit_anchor_ts is not None:
                    if explicit_anchor_ts >= ts:
                        raise PanelTimestampError(
                            "last trusted reference timestamp must be strictly before "
                            "its panel observation"
                        )
                    previous_last_close = explicit_anchor
                    previous_last_close_ts = explicit_anchor_ts

            # The first trusted underlying row establishes the anchor only;
            # it is not a public/evaluable challenger observation.
            if previous_last_close is None or previous_last_close_ts is None:
                if underlying is not None:
                    last_close, last_close_ts = underlying, ts
                continue

            # A gross token/underlying unit mismatch is now judged per-snapshot by
            # validation (TOKEN_UNIT_SUSPECT); a real economic depeg must survive
            # panel assembly and reach the Evidence State, never crash the replay.
            (
                reference,
                reference_source,
                reference_ts,
                reference_age,
            ) = _reference_fields(
                row,
                ts,
                underlying,
                previous_last_close,
                previous_last_close_ts,
            )

            snapshots.append(
                MarketSnapshot(
                    asset=asset_config.asset,
                    observation_ts=ts,
                    token_price=token,
                    token_volume=_num(row.get("token_volume")),
                    token_volume_usd=_num(row.get("token_volume_usd")),
                    token_source=asset_config.token_source if token is not None else None,
                    token_observed_at=ts if token is not None else None,
                    underlying_reference=underlying,
                    underlying_reference_ts=ts if underlying is not None else None,
                    last_trusted_reference=previous_last_close,
                    last_trusted_reference_ts=previous_last_close_ts,
                    reference_age_seconds=int((ts - previous_last_close_ts).total_seconds()),
                    reference_under_test=reference,
                    reference_under_test_source=reference_source,
                    reference_profile=(
                        row.get("reference_profile") or asset_config.reference_profile
                    ),
                    reference_under_test_ts=reference_ts,
                    reference_under_test_age_seconds=reference_age,
                    market_state=_market_state(row.get("session_state"), ts),
                    source_provenance={
                        "panel": path.name,
                        "token": asset_config.token_source if token is not None else "",
                        "reference_under_test": reference_source,
                        "reference_profile": (
                            row.get("reference_profile") or asset_config.reference_profile
                        ),
                        "reference_relationship": (
                            "xstock_is_model_input;_xperp_is_separate_market_evidence"
                        ),
                        "panel_schema": schema,
                        "token_deployment_verified": str(not legacy).lower(),
                        "token_deployment": (
                            f"{row.get('token_chain_index', '')}:"
                            f"{row.get('token_address', '')}"
                        ) if not legacy else "unverified_legacy_nvda",
                    },
                )
            )

            # Make the current underlying available as the trusted anchor for
            # the next canonical observation, never for this one.
            if underlying is not None:
                last_close, last_close_ts = underlying, ts

        if schema == "canonical_hybrid":
            raise PanelIdentityError("ambiguous hybrid canonical/legacy panel schema")
    return snapshots


def _reference_fields(
    row: dict[str, str],
    timestamp: datetime,
    current_underlying: float | None,
    last_close: float,
    last_close_ts: datetime,
) -> tuple[float | None, str, datetime | None, int | None]:
    """Read an explicit reference-under-test when present, else legacy fields."""
    if "reference_under_test_available" in row:
        source = (row.get("reference_under_test_source") or "reference_under_test").strip()
        available = _flag(row.get("reference_under_test_available"))
        if not available:
            return None, source, None, None
        reference = _num(row.get("reference_under_test"))
        if reference is None:
            return None, source, None, None
        reference_ts = (
            _parse_ts(row["reference_under_test_ts"])
            if row.get("reference_under_test_ts")
            else timestamp
        )
        if reference_ts > timestamp:
            raise PanelTimestampError(
                "reference-under-test timestamp must not be after its panel observation"
            )
        age = int((timestamp - reference_ts).total_seconds())
        return reference, source, reference_ts, age

    if current_underlying is not None:
        return current_underlying, "nvda_live", timestamp, 0
    return last_close, "stale_nvda", last_close_ts, max(
        0, int((timestamp - last_close_ts).total_seconds())
    )


def _market_state(value: str | None, timestamp: datetime) -> MarketState:
    if not value:
        from valtide_api.session import classify

        return classify(timestamp)
    try:
        return MarketState((value or "").strip().lower())
    except ValueError:
        from valtide_api.session import classify

        return classify(timestamp)
