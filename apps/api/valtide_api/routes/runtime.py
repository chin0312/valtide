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


def _parse_optional(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


@router.get("/runtime/{asset}", response_model=RuntimeStatus)
def get_runtime(asset: str) -> RuntimeStatus:
    if asset not in SUPPORTED_ASSETS:
        raise HTTPException(status_code=404, detail=f"asset '{asset}' not supported")

    settings = get_settings()
    store = get_runtime_store()
    try:
        record = store.load_runtime(asset)
    except RuntimeStateIntegrityError as exc:
        raw = store.raw_status(asset) or {}
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
            last_error=f"RuntimeStateIntegrityError: {exc}",
            last_gap_steps=int(raw.get("last_gap_steps") or 0),
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
    )
