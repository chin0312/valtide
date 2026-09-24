"""Persistence, scheduler, and warmed-tick integration tests."""

import asyncio
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
        await scheduler.stop()
        assert not scheduler.running

    asyncio.run(exercise())
    assert len(calls) == 1
    # The scheduler values the just-settled bar, one boundary before the clock's
    # current 14:05 boundary.
    assert calls[0] == datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    assert sleep_calls >= 1


def _scheduler_with_publisher(store, publisher_fn, monkeypatch, *, enabled=True):
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
        publisher_fn=publisher_fn,
    )


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
    asyncio.run(scheduler._publish_if_enabled(tick))

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
    asyncio.run(scheduler._publish_if_enabled(tick))

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
    asyncio.run(scheduler._publish_if_enabled(tick))

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

    asyncio.run(scheduler._publish_if_enabled(duplicate))
    asyncio.run(scheduler._publish_if_enabled(failed))

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
    asyncio.run(scheduler._publish_if_enabled(first))

    failed_publication = store.load_publication("NVDAx")
    assert failed_publication is not None
    assert failed_publication.last_publish_status == "failed"
    assert failed_publication.last_publish_error == "PublicationError"
    assert store.load_runtime("NVDAx").latest_result == first.result

    second = run_live_tick("NVDAx", second_ts, store=store, snapshot_builder=builder)
    asyncio.run(scheduler._publish_if_enabled(second))

    successful_publication = store.load_publication("NVDAx")
    assert calls == 2
    assert second.status == "success"
    assert successful_publication.last_publish_status == "published"


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
