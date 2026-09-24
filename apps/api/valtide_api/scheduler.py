"""Single-process warmed live runtime and five-minute scheduler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from valtide_api.clock import (
    FIVE_MINUTES,
    canonical_5m_boundary,
    next_5m_boundary,
    require_canonical_5m,
)
from valtide_api.config import get_settings
from valtide_api.live import build_live_snapshot
from valtide_api.models import MarketSnapshot, ValuationResult
from valtide_api.replay import (
    _warm_state_to_first_observation_with_count,
    advance_without_measurements,
    run_inference,
)
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    RuntimeStore,
    get_runtime_store,
)
from valtide_api.state_store import KalmanState, save_latest_result, save_state

logger = logging.getLogger("valtide.runtime")

SnapshotBuilder = Callable[..., MarketSnapshot]
NowProvider = Callable[[], datetime]
SleepProvider = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class TickResult:
    asset: str
    canonical_ts: datetime
    status: str
    result: ValuationResult | None
    gap_steps: int
    state_restored: bool
    error: str | None = None


def _previous_anchor(record) -> tuple[float | None, datetime | None]:
    if record.latest_result is None or record.state is None:
        return None, None
    age = record.latest_result.reference_age_seconds
    return (
        record.latest_result.last_trusted_reference,
        record.state.last_ts - timedelta(seconds=age),
    )


def run_live_tick(
    asset: str,
    canonical_ts: datetime,
    *,
    store: RuntimeStore | None = None,
    snapshot_builder: SnapshotBuilder | None = None,
) -> TickResult:
    """Fetch, infer, validate, and persist one canonical live observation."""
    store = store or get_runtime_store()
    snapshot_builder = snapshot_builder or build_live_snapshot
    attempt_at = datetime.now(UTC)

    try:
        canonical_ts = require_canonical_5m(canonical_ts, "canonical_ts")
        record = store.load_runtime(asset)
        if record is not None and record.state is not None:
            prior = record.state
            if prior.last_ts is None:
                raise RuntimeStateIntegrityError("persisted state has no timestamp")
            if prior.last_ts > canonical_ts:
                raise RuntimeStateIntegrityError(
                    f"persisted state {prior.last_ts.isoformat()} is after requested tick "
                    f"{canonical_ts.isoformat()}"
                )
            if prior.last_ts == canonical_ts:
                store.record_tick_status(
                    asset,
                    "already_processed",
                    attempt_at=attempt_at,
                    gap_steps=0,
                )
                return TickResult(
                    asset=asset,
                    canonical_ts=canonical_ts,
                    status="already_processed",
                    result=record.latest_result,
                    gap_steps=0,
                    state_restored=True,
                )

        snapshot = snapshot_builder(observation_ts=canonical_ts)
        state: KalmanState | None = record.state if record is not None else None
        state_restored = state is not None
        gap_steps = 0

        if state is None:
            state, gap_steps = _warm_state_to_first_observation_with_count(snapshot)
        else:
            anchor_reference, anchor_ts = _previous_anchor(record)
            if record.latest_result is None:
                raise RuntimeStateIntegrityError(
                    "persisted carried state has no corresponding latest result"
                )
            state, gap_steps = advance_without_measurements(
                state,
                state.last_ts,
                canonical_ts,
                snapshot,
                anchor_reference=anchor_reference,
                anchor_ts=anchor_ts,
            )

        result, new_state = run_inference(snapshot, state)
        store.save_runtime(
            asset,
            new_state,
            result,
            tick_status="success",
            tick_attempt_at=attempt_at,
            gap_steps=gap_steps,
        )
        # Keep the old in-memory compatibility layer warm for non-HTTP callers;
        # SQLite remains the canonical source for the API.
        save_state(asset, new_state)
        save_latest_result(asset, result)
        return TickResult(
            asset=asset,
            canonical_ts=canonical_ts,
            status="success",
            result=result,
            gap_steps=gap_steps,
            state_restored=state_restored,
        )
    except Exception as exc:  # noqa: BLE001 - tick failures must preserve prior state
        error = f"{type(exc).__name__}: {exc}"
        store.record_tick_status(asset, "failure", error=error, attempt_at=attempt_at)
        logger.exception("Live tick failed for %s at %s", asset, canonical_ts)
        return TickResult(
            asset=asset,
            canonical_ts=canonical_ts,
            status="failure",
            result=None,
            gap_steps=0,
            state_restored=False,
            error=error,
        )


class LiveScheduler:
    """A deliberately small single-process scheduler for the hackathon MVP."""

    def __init__(
        self,
        asset: str | None = None,
        *,
        store: RuntimeStore | None = None,
        tick: Callable[..., TickResult] = run_live_tick,
        now: NowProvider | None = None,
        sleep: SleepProvider | None = None,
    ):
        settings = get_settings()
        self.asset = asset or settings.live_scheduler_asset
        self.store = store or get_runtime_store()
        self._tick = tick
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep or asyncio.sleep
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if not self.running:
            self._task = asyncio.create_task(self._run(), name="valtide-live-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run(self) -> None:
        while True:
            # Wait for the next completed boundary. Starting at the current
            # floor could label a few minutes of newly fetched data as if it
            # had been observed at an already-past timestamp.
            now = self._now()
            next_boundary = next_5m_boundary(now)
            await self._sleep(max(0.0, (next_boundary - now).total_seconds() + 1.0))
            # Value the bar that just settled, not the one now forming: its
            # confirmed reference candle exists, so the comparator is present.
            canonical_ts = canonical_5m_boundary(self._now()) - FIVE_MINUTES
            result = await asyncio.to_thread(
                self._tick,
                self.asset,
                canonical_ts,
                store=self.store,
            )
            evidence = result.result.evidence_state.value if result.result else None
            logger.info(
                "live tick asset=%s canonical_ts=%s status=%s evidence=%s "
                "state_restored=%s gap_steps=%d",
                self.asset,
                canonical_ts.isoformat(),
                result.status,
                evidence,
                result.state_restored,
                result.gap_steps,
            )


__all__ = ["LiveScheduler", "TickResult", "run_live_tick"]
