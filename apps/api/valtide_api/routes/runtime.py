"""GET /api/runtime/{asset} — warmed runtime and scheduler status."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from valtide_api.config import get_settings
from valtide_api.models import SUPPORTED_ASSETS
from valtide_api.runtime_store import RuntimeStateIntegrityError, get_runtime_store

router = APIRouter(prefix="/api", tags=["runtime"])


class RuntimeStatus(BaseModel):
    asset: str
    scheduler_enabled: bool
    has_state: bool
    has_live_result: bool
    last_state_timestamp: datetime | None
    last_result_timestamp: datetime | None
    last_tick_status: str | None
    last_tick_attempt_at: datetime | None
    last_error: str | None
    last_gap_steps: int = 0
    auto_publish_enabled: bool = False
    last_publish_status: str | None = None
    last_publish_attempt_at: datetime | None = None
    last_publish_observation_ts: datetime | None = None
    last_published_observation_ts: datetime | None = None
    last_published_at: int | None = None
    last_publish_tx_hash: str | None = None
    last_publish_error: str | None = None


def _parse_optional(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


def _load_publication_status(store, asset: str):
    try:
        return store.load_publication(asset), None
    except RuntimeStateIntegrityError:
        return None, "RuntimeStateIntegrityError: publication state is invalid"


def _publication_fields(settings, publication, publication_error: str | None):
    if publication_error is not None:
        return {
            "auto_publish_enabled": settings.auto_publish_enabled,
            "last_publish_status": "invalid",
            "last_publish_attempt_at": None,
            "last_publish_observation_ts": None,
            "last_published_observation_ts": None,
            "last_published_at": None,
            "last_publish_tx_hash": None,
            "last_publish_error": publication_error,
        }

    return {
        "auto_publish_enabled": settings.auto_publish_enabled,
        "last_publish_status": publication.last_publish_status if publication else None,
        "last_publish_attempt_at": (
            publication.last_publish_attempt_at if publication else None
        ),
        "last_publish_observation_ts": (
            publication.last_publish_observation_ts if publication else None
        ),
        "last_published_observation_ts": (
            publication.last_published_observation_ts if publication else None
        ),
        "last_published_at": publication.last_published_at if publication else None,
        "last_publish_tx_hash": publication.last_publish_tx_hash if publication else None,
        "last_publish_error": publication.last_publish_error if publication else None,
    }


@router.get("/runtime/{asset}", response_model=RuntimeStatus)
def get_runtime(asset: str) -> RuntimeStatus:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    settings = get_settings()
    store = get_runtime_store()
    try:
        record = store.load_runtime(asset)
    except RuntimeStateIntegrityError:
        runtime_error = "RuntimeStateIntegrityError: runtime state is invalid"
        raw = store.raw_status(asset) or {}
    else:
        runtime_error = None
        raw = {}

    publication, publication_error = _load_publication_status(store, asset)
    publication_fields = _publication_fields(
        settings, publication, publication_error
    )

    if runtime_error is not None:
        return RuntimeStatus(
            asset=asset,
            scheduler_enabled=(
                settings.live_scheduler_enabled and settings.live_scheduler_asset == asset
            ),
            has_state=False,
            has_live_result=False,
            last_state_timestamp=_parse_optional(raw.get("state_last_ts")),
            last_result_timestamp=_parse_optional(raw.get("latest_result_ts")),
            last_tick_status=raw.get("last_tick_status"),
            last_tick_attempt_at=_parse_optional(raw.get("last_tick_attempt_at")),
            last_error=runtime_error,
            last_gap_steps=int(raw.get("last_gap_steps") or 0),
            **publication_fields,
        )

    return RuntimeStatus(
        asset=asset,
        scheduler_enabled=(
            settings.live_scheduler_enabled and settings.live_scheduler_asset == asset
        ),
        has_state=record is not None and record.state is not None,
        has_live_result=record is not None and record.latest_result is not None,
        last_state_timestamp=record.state.last_ts if record and record.state else None,
        last_result_timestamp=(
            record.latest_result.timestamp if record and record.latest_result else None
        ),
        last_tick_status=record.last_tick_status if record else None,
        last_tick_attempt_at=record.last_tick_attempt_at if record else None,
        last_error=record.last_tick_error if record else None,
        last_gap_steps=record.last_gap_steps if record else 0,
        **publication_fields,
    )
