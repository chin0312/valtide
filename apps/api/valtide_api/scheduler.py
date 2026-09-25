"""Single-process warmed live runtime and five-minute scheduler."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from valtide_api import publisher as publisher_module
from valtide_api.clock import (
    FIVE_MINUTES,
    canonical_5m_boundary,
    next_5m_boundary,
    require_canonical_5m,
)
from valtide_api.config import get_settings
from valtide_api.live import ExactNvdaxCandleUnavailable, build_live_snapshot
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
_PUBLICATION_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_NVDAX_SETTLEMENT_MAX_ATTEMPTS = 3
_NVDAX_SETTLEMENT_RETRY_DELAY_SECONDS = 2.0

SnapshotBuilder = Callable[..., MarketSnapshot]
NowProvider = Callable[[], datetime]
SleepProvider = Callable[[float], Awaitable[None]]
PublishFunction = Callable[..., object]


def _build_snapshot_with_settlement_retry(
    snapshot_builder: SnapshotBuilder,
    canonical_ts: datetime,
) -> MarketSnapshot:
    """Retry only temporary absence of the exact settled NVDAx candle."""
    for attempt in range(_NVDAX_SETTLEMENT_MAX_ATTEMPTS):
        try:
            return snapshot_builder(observation_ts=canonical_ts)
        except ExactNvdaxCandleUnavailable:
            if attempt + 1 == _NVDAX_SETTLEMENT_MAX_ATTEMPTS:
                raise
            time.sleep(_NVDAX_SETTLEMENT_RETRY_DELAY_SECONDS)
    raise AssertionError("settlement retry loop exited without a snapshot or exception")


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

        snapshot = _build_snapshot_with_settlement_retry(snapshot_builder, canonical_ts)
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
        store.save_runtime_and_history(
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
        publisher_fn: PublishFunction | None = None,
    ):
        settings = get_settings()
        self.asset = asset or settings.live_scheduler_asset
        self.store = store or get_runtime_store()
        self._tick = tick
        self._now = now or (lambda: datetime.now(UTC))
        self._sleep = sleep or asyncio.sleep
        self._settings = settings
        self._auto_publish_enabled = bool(getattr(settings, "auto_publish_enabled", False))
        self._publisher_fn = publisher_fn or publisher_module.publish
        self._task: asyncio.Task[None] | None = None
        self._publication_task: asyncio.Task[None] | None = None
        self._publication_wakeup: asyncio.Event | None = None
        self._pending_publication: ValuationResult | None = None
        self._publication_stop_requested = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def publication_running(self) -> bool:
        return self._publication_task is not None and not self._publication_task.done()

    async def start(self) -> None:
        if self._task is not None or self._publication_task is not None:
            return
        self._publication_stop_requested = False
        self._publication_wakeup = asyncio.Event()
        if self._auto_publish_enabled:
            self._publication_task = asyncio.create_task(
                self._publication_worker(),
                name="valtide-publication-worker",
            )
            if self._pending_publication is not None:
                self._publication_wakeup.set()
        self._task = asyncio.create_task(self._run(), name="valtide-live-scheduler")

    async def stop(self) -> None:
        scheduler_task = self._task
        self._task = None
        if scheduler_task is not None:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass

        publication_task = self._publication_task
        self._publication_stop_requested = True
        self._pending_publication = None
        if self._publication_wakeup is not None:
            self._publication_wakeup.set()
        if publication_task is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(publication_task),
                    timeout=_PUBLICATION_SHUTDOWN_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                logger.warning(
                    "publication worker shutdown timed out; abandoning its await while "
                    "the underlying thread finishes"
                )
                publication_task.cancel()
                try:
                    await publication_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            finally:
                self._publication_task = None
                self._publication_wakeup = None

    def _publish_if_enabled(self, tick: TickResult) -> None:
        """Queue a newly persisted result without waiting for blockchain delivery."""
        if not self._auto_publish_enabled or tick.status != "success" or tick.result is None:
            return

        result = tick.result
        pending = self._pending_publication
        if pending is None or result.timestamp > pending.timestamp:
            self._pending_publication = result
            if self._publication_wakeup is not None:
                self._publication_wakeup.set()

    @staticmethod
    def _safe_publication_error(exc: Exception) -> str:
        """Return a non-sensitive publication error identifier for storage/logs."""
        return type(exc).__name__

    async def _publish_one(self, result: ValuationResult) -> None:
        """Publish one result; the worker is the only caller of this method."""
        self.store.record_publication_attempt(self.asset, result.timestamp)
        try:
            receipt = await asyncio.to_thread(
                self._publisher_fn,
                result,
                settings=self._settings,
            )
        except publisher_module.PublisherError as exc:
            error = self._safe_publication_error(exc)
            self.store.record_publication_failure(
                self.asset,
                result.timestamp,
                error=error,
            )
            logger.warning(
                "auto-publish asset=%s observed_at=%s status=failed error=%s",
                self.asset,
                result.timestamp.isoformat(),
                error,
            )
            return
        except Exception as exc:  # noqa: BLE001 - delivery must not stop valuation
            error = self._safe_publication_error(exc)
            self.store.record_publication_failure(
                self.asset,
                result.timestamp,
                error=error,
            )
            logger.warning(
                "auto-publish asset=%s observed_at=%s status=failed error=%s",
                self.asset,
                result.timestamp.isoformat(),
                error,
            )
            return

        status = str(getattr(receipt, "status", "published"))
        self.store.record_publication_success(
            self.asset,
            result.timestamp,
            status=status,
            published_at=getattr(receipt, "published_at", None),
            tx_hash=getattr(receipt, "tx_hash", None),
        )
        logger.info(
            "auto-publish asset=%s observed_at=%s status=%s",
            self.asset,
            result.timestamp.isoformat(),
            status,
        )

    async def _publication_worker(self) -> None:
        """Serialize publication and coalesce pending results to the newest one."""
        while True:
            wakeup = self._publication_wakeup
            if wakeup is None:
                return
            await wakeup.wait()
            wakeup.clear()
            if self._publication_stop_requested:
                return

            while self._pending_publication is not None:
                result = self._pending_publication
                self._pending_publication = None
                await self._publish_one(result)
                if self._publication_stop_requested:
                    self._pending_publication = None
                    return

    async def _process_tick(self, canonical_ts: datetime) -> TickResult:
        """Run one valuation tick and enqueue delivery without awaiting it."""
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
        self._publish_if_enabled(result)
        return result

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
            await self._process_tick(canonical_ts)


__all__ = ["LiveScheduler", "TickResult", "run_live_tick"]
