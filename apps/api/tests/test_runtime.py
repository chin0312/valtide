"""Persistence, scheduler, and warmed-tick integration tests."""

import asyncio
import json
import threading
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import valtide_api.scheduler as scheduler_module
from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.publisher import PublicationError
from valtide_api.runtime_store import RuntimeStore
from valtide_api.scheduler import LiveScheduler, TickResult, run_live_tick

_ANCHOR = datetime(2026, 9, 19, 13, 0, tzinfo=UTC)


def _snapshot(timestamp: datetime) -> MarketSnapshot:
    return MarketSnapshot(
        asset="NVDAx",
        observation_ts=timestamp,
        token_price=185.1,
        token_volume=50_000.0,
        underlying_reference=None,
        underlying_reference_ts=None,
        last_trusted_reference=180.0,
        last_trusted_reference_ts=_ANCHOR,
        reference_age_seconds=int((timestamp - _ANCHOR).total_seconds()),
        reference_under_test=185.7,
        reference_under_test_source="okx_xperp_index",
        reference_under_test_ts=timestamp,
        reference_under_test_age_seconds=0,
        market_state=MarketState.CLOSED,
        source_provenance={"test": "warmed_runtime"},
    )


def _builder_for(snapshots: list[MarketSnapshot]):
    by_timestamp = {snapshot.observation_ts: snapshot for snapshot in snapshots}
    calls: list[datetime] = []

    def build(*, observation_ts: datetime) -> MarketSnapshot:
        calls.append(observation_ts)
        return by_timestamp[observation_ts]

    return build, calls


def test_warmed_tick_persists_and_restores_across_store_restart(tmp_path):
    first_ts = _ANCHOR + timedelta(hours=1)
    second_ts = first_ts + timedelta(minutes=5)
    snapshots = [_snapshot(first_ts), _snapshot(second_ts)]
    builder, calls = _builder_for(snapshots)
    path = tmp_path / "runtime.sqlite3"

    first_store = RuntimeStore(path)
    first = run_live_tick("NVDAx", first_ts, store=first_store, snapshot_builder=builder)

    assert first.status == "success"
    assert first.gap_steps == 11
    assert first.state_restored is False
    assert len(calls) == 1
    first_record = first_store.load_runtime("NVDAx")
    assert first_record is not None
    assert first_record.state is not None
    assert first_record.state.last_ts == first_ts
    assert first_record.latest_result == first.result
    first_store.close()

    restarted_store = RuntimeStore(path)
    second = run_live_tick("NVDAx", second_ts, store=restarted_store, snapshot_builder=builder)

    assert second.status == "success"
    assert second.gap_steps == 0
    assert second.state_restored is True
    assert len(calls) == 2
    record = restarted_store.load_runtime("NVDAx")
    assert record is not None
    assert record.state is not None
    assert record.state.last_ts == second_ts
    assert record.latest_result == second.result


def test_duplicate_tick_is_idempotent_and_does_not_fetch_again(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, calls = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    first = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    duplicate = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)

    assert first.status == "success"
    assert duplicate.status == "already_processed"
    assert duplicate.result == first.result
    assert len(calls) == 1
    assert store.load_runtime("NVDAx").last_tick_status == "already_processed"


def test_tick_failure_preserves_last_good_state_and_result(tmp_path):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    good_builder, _ = _builder_for([_snapshot(first_ts)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    first = run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=good_builder)
    before = store.load_runtime("NVDAx")

    def failing_builder(*, observation_ts: datetime) -> MarketSnapshot:
        raise RuntimeError("synthetic source outage")

    failed = run_live_tick(
        "NVDAx", second_ts, store=store, snapshot_builder=failing_builder
    )
    after = store.load_runtime("NVDAx")

    assert failed.status == "failure"
    assert "synthetic source outage" in failed.error
    assert before is not None and after is not None
    assert after.state == before.state
    assert after.latest_result == first.result
    assert after.last_tick_status == "failure"
    assert "synthetic source outage" in after.last_tick_error


def test_invalid_initial_chronology_fails_without_backward_state(tmp_path):
    timestamp = _ANCHOR - timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    result = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)

    assert result.status == "failure"
    assert "must not precede" in result.error
    record = store.load_runtime("NVDAx")
    assert record is not None
    assert record.state is None
    assert record.latest_result is None


def test_scheduler_has_single_process_start_stop_lifecycle(tmp_path):
    calls: list[datetime] = []
    clock_values = [
        datetime(2026, 9, 19, 14, 2, tzinfo=UTC),
        datetime(2026, 9, 19, 14, 5, 1, tzinfo=UTC),
    ]
    sleep_calls = 0

    def fake_now() -> datetime:
        return (
            clock_values.pop(0)
            if clock_values
            else datetime(2026, 9, 19, 14, 5, 1, tzinfo=UTC)
        )

    def fake_tick(asset, canonical_ts, *, store):
        calls.append(canonical_ts)
        return TickResult(
            asset=asset,
            canonical_ts=canonical_ts,
            status="success",
            result=None,
            gap_steps=0,
            state_restored=False,
        )

    async def fake_sleep(delay: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            await asyncio.Event().wait()

    async def exercise() -> None:
        scheduler = LiveScheduler(
            asset="NVDAx",
            store=RuntimeStore(tmp_path / "runtime.sqlite3"),
            tick=fake_tick,
            now=fake_now,
            sleep=fake_sleep,
        )
        await scheduler.start()
        await asyncio.sleep(0)
        assert scheduler.running
        scheduler_task = scheduler._task
        await scheduler.start()
        assert scheduler._task is scheduler_task
        await scheduler.stop()
        assert not scheduler.running

    asyncio.run(exercise())
    assert len(calls) == 1
    # The scheduler values the just-settled bar, one boundary before the clock's
    # current 14:05 boundary.
    assert calls[0] == datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    assert sleep_calls >= 1


async def _blocked_sleep(_delay: float) -> None:
    await asyncio.Event().wait()


async def _wait_until(predicate, *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition did not become true")


async def _wait_for_thread_event(event: threading.Event) -> None:
    await _wait_until(event.is_set)


def _scheduler_with_publisher(
    store,
    publisher_fn,
    monkeypatch,
    *,
    enabled=True,
    tick=run_live_tick,
):
    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(
            auto_publish_enabled=enabled,
            publish_enabled=False,
            live_scheduler_asset="NVDAx",
        ),
    )
    return LiveScheduler(
        asset="NVDAx",
        store=store,
        tick=tick,
        sleep=_blocked_sleep,
        publisher_fn=publisher_fn,
    )


def test_scheduler_publication_worker_start_stop_is_idempotent(tmp_path, monkeypatch):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    scheduler = _scheduler_with_publisher(
        store,
        lambda *args, **kwargs: None,
        monkeypatch,
    )

    async def exercise() -> None:
        await scheduler.start()
        scheduler_task = scheduler._task
        publication_task = scheduler._publication_task
        assert scheduler.running
        assert scheduler.publication_running

        await scheduler.start()
        assert scheduler._task is scheduler_task
        assert scheduler._publication_task is publication_task

        await scheduler.stop()
        assert not scheduler.running
        assert not scheduler.publication_running
        assert scheduler._task is None
        assert scheduler._publication_task is None
        assert scheduler._publication_wakeup is None

    asyncio.run(exercise())


def test_auto_publish_disabled_does_not_call_publisher(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    calls = []

    scheduler = _scheduler_with_publisher(
        store,
        lambda *args, **kwargs: calls.append((args, kwargs)),
        monkeypatch,
        enabled=False,
    )
    async def exercise() -> None:
        await scheduler.start()
        scheduler._publish_if_enabled(tick)
        await scheduler.stop()

    asyncio.run(exercise())

    assert calls == []
    assert store.load_publication("NVDAx") is None


def test_auto_publish_persists_tick_before_publishing_and_records_success(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    calls = []

    def fake_publish(result, *, settings):
        assert settings.auto_publish_enabled is True
        assert settings.publish_enabled is False
        persisted = store.load_runtime("NVDAx")
        assert persisted is not None
        assert persisted.latest_result == result
        calls.append(result)
        return SimpleNamespace(
            status="published",
            published_at=1_800_000_000,
            tx_hash="0x" + "11" * 32,
        )

    scheduler = _scheduler_with_publisher(store, fake_publish, monkeypatch)
    async def exercise() -> None:
        await scheduler.start()
        scheduler._publish_if_enabled(tick)
        await _wait_until(
            lambda: (
                (publication := store.load_publication("NVDAx")) is not None
                and publication.last_publish_status == "published"
            )
        )
        await scheduler.stop()

    asyncio.run(exercise())

    assert calls == [tick.result]
    publication = store.load_publication("NVDAx")
    assert publication is not None
    assert publication.last_publish_status == "published"
    assert publication.last_published_observation_ts == timestamp
    assert publication.last_published_at == 1_800_000_000
    assert publication.last_publish_tx_hash == "0x" + "11" * 32


def test_auto_publish_already_published_records_idempotent_status(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)

    def fake_publish(result, *, settings):  # noqa: ARG001
        return SimpleNamespace(
            status="already_published",
            published_at=1_800_000_001,
            tx_hash=None,
        )

    scheduler = _scheduler_with_publisher(store, fake_publish, monkeypatch)
    async def exercise() -> None:
        await scheduler.start()
        scheduler._publish_if_enabled(tick)
        await _wait_until(
            lambda: (
                (publication := store.load_publication("NVDAx")) is not None
                and publication.last_publish_status == "already_published"
            )
        )
        await scheduler.stop()

    asyncio.run(exercise())

    publication = store.load_publication("NVDAx")
    assert publication is not None
    assert publication.last_publish_status == "already_published"
    assert publication.last_publish_tx_hash is None


def test_failed_or_already_processed_tick_does_not_publish(tmp_path, monkeypatch):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    good_builder, _ = _builder_for([_snapshot(first_ts)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=good_builder)
    duplicate = run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=good_builder)

    def failing_builder(*, observation_ts):  # noqa: ARG001
        raise RuntimeError("synthetic source outage")

    failed = run_live_tick("NVDAx", second_ts, store=store, snapshot_builder=failing_builder)
    calls = []
    scheduler = _scheduler_with_publisher(
        store,
        lambda *args, **kwargs: calls.append((args, kwargs)),
        monkeypatch,
    )

    async def exercise() -> None:
        await scheduler.start()
        scheduler._publish_if_enabled(duplicate)
        scheduler._publish_if_enabled(failed)
        await asyncio.sleep(0.05)
        await scheduler.stop()

    asyncio.run(exercise())

    assert calls == []
    assert store.load_publication("NVDAx") is None


def test_auto_publish_failure_preserves_successful_runtime_and_scheduler_continues(
    tmp_path, monkeypatch
):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(first_ts), _snapshot(second_ts)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    first = run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=builder)
    calls = 0

    def fake_publish(result, *, settings):  # noqa: ARG001
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PublicationError("synthetic publisher outage")
        return SimpleNamespace(status="published", published_at=1_800_000_002, tx_hash="0x22")

    scheduler = _scheduler_with_publisher(store, fake_publish, monkeypatch)
    async def exercise() -> None:
        await scheduler.start()
        scheduler._publish_if_enabled(first)
        await _wait_until(
            lambda: (
                (publication := store.load_publication("NVDAx")) is not None
                and publication.last_publish_status == "failed"
            )
        )
        failed_publication = store.load_publication("NVDAx")
        assert failed_publication is not None
        assert failed_publication.last_publish_error == "PublicationError"

        second = run_live_tick("NVDAx", second_ts, store=store, snapshot_builder=builder)
        scheduler._publish_if_enabled(second)
        await _wait_until(
            lambda: (
                (publication := store.load_publication("NVDAx")) is not None
                and publication.last_publish_status == "published"
                and publication.last_published_observation_ts == second_ts
            )
        )
        await scheduler.stop()
        return second

    second = asyncio.run(exercise())
    failed_publication = store.load_publication("NVDAx")
    assert failed_publication is not None
    assert failed_publication.last_publish_status == "published"
    assert failed_publication.last_publish_error is None
    assert store.load_runtime("NVDAx").latest_result == second.result
    assert [result.timestamp for result in store.load_history("NVDAx")] == [
        first_ts,
        second_ts,
    ]

    assert calls == 2
    assert second.status == "success"


def test_slow_publication_does_not_block_next_tick_and_stays_serialized(tmp_path, monkeypatch):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    snapshots = [_snapshot(first_ts), _snapshot(second_ts)]
    builder, _ = _builder_for(snapshots)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    publication_started = threading.Event()
    release_publication = threading.Event()
    lock = threading.Lock()
    published: list[datetime] = []
    active_calls = 0
    max_active_calls = 0

    def fake_tick(asset, canonical_ts, *, store):
        return run_live_tick(asset, canonical_ts, store=store, snapshot_builder=builder)

    def slow_publish(result, *, settings):  # noqa: ARG001
        nonlocal active_calls, max_active_calls
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
            published.append(result.timestamp)
        try:
            if result.timestamp == first_ts:
                publication_started.set()
                assert release_publication.wait(timeout=5)
            return SimpleNamespace(
                status="published",
                published_at=int(result.timestamp.timestamp()) + 1,
                tx_hash="0xslow",
            )
        finally:
            with lock:
                active_calls -= 1

    scheduler = _scheduler_with_publisher(
        store,
        slow_publish,
        monkeypatch,
        tick=fake_tick,
    )

    async def exercise() -> None:
        await scheduler.start()
        first = await scheduler._process_tick(first_ts)
        assert first.status == "success"
        await _wait_for_thread_event(publication_started)

        second = await scheduler._process_tick(second_ts)
        assert second.status == "success"
        assert store.load_runtime("NVDAx").state.last_ts == second_ts
        with lock:
            assert published == [first_ts]

        release_publication.set()
        await _wait_until(lambda: published == [first_ts, second_ts])
        assert max_active_calls == 1
        await scheduler.stop()

    asyncio.run(exercise())


def test_newest_pending_observation_supersedes_older_pending_publication(
    tmp_path, monkeypatch
):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    third_ts = second_ts + timedelta(minutes=5)
    snapshots = [_snapshot(first_ts), _snapshot(second_ts), _snapshot(third_ts)]
    builder, _ = _builder_for(snapshots)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    publication_started = threading.Event()
    release_publication = threading.Event()
    lock = threading.Lock()
    published: list[datetime] = []
    active_calls = 0
    max_active_calls = 0

    def fake_tick(asset, canonical_ts, *, store):
        return run_live_tick(asset, canonical_ts, store=store, snapshot_builder=builder)

    def slow_publish(result, *, settings):  # noqa: ARG001
        nonlocal active_calls, max_active_calls
        with lock:
            active_calls += 1
            max_active_calls = max(max_active_calls, active_calls)
            published.append(result.timestamp)
        try:
            if result.timestamp == first_ts:
                publication_started.set()
                assert release_publication.wait(timeout=5)
            return SimpleNamespace(
                status="published",
                published_at=int(result.timestamp.timestamp()) + 1,
                tx_hash="0xcoalesced",
            )
        finally:
            with lock:
                active_calls -= 1

    scheduler = _scheduler_with_publisher(
        store,
        slow_publish,
        monkeypatch,
        tick=fake_tick,
    )

    async def exercise() -> None:
        await scheduler.start()
        await scheduler._process_tick(first_ts)
        await _wait_for_thread_event(publication_started)
        await scheduler._process_tick(second_ts)
        await scheduler._process_tick(third_ts)
        with lock:
            assert published == [first_ts]

        release_publication.set()
        await _wait_until(lambda: published == [first_ts, third_ts])
        assert max_active_calls == 1
        await scheduler.stop()

    asyncio.run(exercise())


def test_failed_in_flight_publication_still_delivers_newest_pending_observation(
    tmp_path, monkeypatch
):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    third_ts = second_ts + timedelta(minutes=5)
    snapshots = [_snapshot(first_ts), _snapshot(second_ts), _snapshot(third_ts)]
    builder, _ = _builder_for(snapshots)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    publication_started = threading.Event()
    release_publication = threading.Event()
    published: list[datetime] = []

    def fake_tick(asset, canonical_ts, *, store):
        return run_live_tick(asset, canonical_ts, store=store, snapshot_builder=builder)

    def failing_first_publish(result, *, settings):  # noqa: ARG001
        published.append(result.timestamp)
        if result.timestamp == first_ts:
            publication_started.set()
            assert release_publication.wait(timeout=5)
            raise PublicationError("synthetic first publication failure")
        return SimpleNamespace(
            status="published",
            published_at=int(result.timestamp.timestamp()) + 1,
            tx_hash="0xrecovered",
        )

    scheduler = _scheduler_with_publisher(
        store,
        failing_first_publish,
        monkeypatch,
        tick=fake_tick,
    )

    async def exercise() -> None:
        await scheduler.start()
        await scheduler._process_tick(first_ts)
        await _wait_for_thread_event(publication_started)
        await scheduler._process_tick(second_ts)
        await scheduler._process_tick(third_ts)

        release_publication.set()
        await _wait_until(
            lambda: published == [first_ts, third_ts]
            and (publication := store.load_publication("NVDAx")) is not None
            and publication.last_publish_status == "published"
        )
        await scheduler.stop()

    asyncio.run(exercise())

    assert published == [first_ts, third_ts]


def test_successful_publication_generation_replaces_stale_transaction_metadata(
    tmp_path,
):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    store.record_publication_success(
        "NVDAx",
        first_ts,
        status="published",
        published_at=1_800_000_010,
        tx_hash="0x" + "11" * 32,
    )
    store.record_publication_success(
        "NVDAx",
        second_ts,
        status="already_published",
        published_at=1_800_000_020,
        tx_hash=None,
    )

    publication = store.load_publication("NVDAx")

    assert publication is not None
    assert publication.last_published_observation_ts == second_ts
    assert publication.last_published_at == 1_800_000_020
    assert publication.last_publish_tx_hash is None


def test_successful_publication_generation_does_not_inherit_published_at(
    tmp_path,
):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    store.record_publication_success(
        "NVDAx",
        first_ts,
        status="published",
        published_at=1_800_000_030,
        tx_hash="0x" + "22" * 32,
    )
    store.record_publication_success(
        "NVDAx",
        second_ts,
        status="already_published",
        published_at=None,
        tx_hash=None,
    )

    publication = store.load_publication("NVDAx")

    assert publication is not None
    assert publication.last_published_observation_ts == second_ts
    assert publication.last_published_at is None
    assert publication.last_publish_tx_hash is None


def test_failed_newer_publication_preserves_previous_success_generation(tmp_path):
    first_ts = _ANCHOR + timedelta(minutes=5)
    second_ts = first_ts + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    store.record_publication_success(
        "NVDAx",
        first_ts,
        status="published",
        published_at=1_800_000_040,
        tx_hash="0x" + "33" * 32,
    )
    store.record_publication_failure(
        "NVDAx",
        second_ts,
        error="PublicationError",
    )

    publication = store.load_publication("NVDAx")

    assert publication is not None
    assert publication.last_publish_status == "failed"
    assert publication.last_publish_error == "PublicationError"
    assert publication.last_publish_observation_ts == second_ts
    assert publication.last_published_observation_ts == first_ts
    assert publication.last_published_at == 1_800_000_040
    assert publication.last_publish_tx_hash == "0x" + "33" * 32


def test_publication_status_persists_across_runtime_store_restart(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    path = tmp_path / "runtime.sqlite3"
    store = RuntimeStore(path)
    store.record_publication_attempt("NVDAx", timestamp)
    store.record_publication_success(
        "NVDAx",
        timestamp,
        status="published",
        published_at=1_800_000_003,
        tx_hash="0x" + "33" * 32,
    )
    store.close()

    restarted = RuntimeStore(path)
    publication = restarted.load_publication("NVDAx")

    assert publication is not None
    assert publication.last_publish_status == "published"
    assert publication.last_publish_observation_ts == timestamp
    assert publication.last_published_at == 1_800_000_003
    assert publication.last_publish_tx_hash == "0x" + "33" * 32


def test_legacy_result_payload_without_new_provenance_fields_still_loads(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    assert tick.result is not None

    payload = tick.result.model_dump()
    for field in (
        "token_source",
        "token_observed_at",
        "token_volume",
        "token_volume_usd",
        "token_liquidity_usd",
        "source_provenance",
    ):
        payload.pop(field, None)
    with store._lock, store._connection:
        store._connection.execute(
            "UPDATE runtime_state SET latest_result_json = ? WHERE asset = ?",
            (json.dumps(payload, default=str), "NVDAx"),
        )

    restored = store.load_runtime("NVDAx")
    assert restored is not None and restored.latest_result is not None
    assert restored.latest_result.token_source is None
    assert restored.latest_result.token_volume_usd is None
    assert restored.latest_result.source_provenance == {}
