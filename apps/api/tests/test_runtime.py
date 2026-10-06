"""Persistence, scheduler, and warmed-tick integration tests."""

import asyncio
import json
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import valtide_api.scheduler as scheduler_module
from valtide_api.config import Settings
from valtide_api.live import ExactNvdaxCandleUnavailable, LiveDataUnavailable
from valtide_api.models import MarketSnapshot, MarketState
from valtide_api.publisher import PublicationError
from valtide_api.replay import run_inference
from valtide_api.runtime_store import (
    RuntimeStateIntegrityError,
    RuntimeStore,
    runtime_identity_for_asset,
)
from valtide_api.scheduler import (
    LiveScheduler,
    TickResult,
    build_enabled_schedulers,
    run_live_tick,
)

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
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
        reference_under_test_ts=timestamp,
        reference_under_test_age_seconds=0,
        market_state=MarketState.CLOSED,
        source_provenance={
            "test": "warmed_runtime",
            "reference_profile": "unified_xstock_p1ac_xperp_evidence_v1",
        },
    )


def _builder_for(snapshots: list[MarketSnapshot]):
    by_timestamp = {snapshot.observation_ts: snapshot for snapshot in snapshots}
    calls: list[datetime] = []

    def build(*, asset: str, observation_ts: datetime) -> MarketSnapshot:
        assert asset == "NVDAx"
        calls.append(observation_ts)
        return by_timestamp[observation_ts]

    return build, calls


def test_scheduler_worker_selection_is_explicit_and_single_asset(tmp_path, monkeypatch):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    settings = SimpleNamespace(
        live_scheduler_enabled=True, live_scheduler_asset="NVDAx", auto_publish_enabled=False
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
    workers = build_enabled_schedulers(settings, store)
    assert len(workers) == 1
    assert workers[0].asset == "NVDAx"
    assert build_enabled_schedulers(settings, store, assets=()) == ()


def test_three_production_workers_require_explicit_asset_selection(tmp_path, monkeypatch):
    store = RuntimeStore(tmp_path / "three-runtime.sqlite3")
    settings = Settings(
        _env_file=None,
        live_scheduler_enabled=True,
        live_scheduler_asset="NVDAx",
        live_scheduler_assets="NVDAx,SPYx,AAPLx",
        auto_publish_enabled=False,
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)

    workers = build_enabled_schedulers(settings, store)

    assert [worker.asset for worker in workers] == ["NVDAx", "SPYx", "AAPLx"]
    assert build_enabled_schedulers(settings, store, assets=()) == ()


def test_three_asset_publish_routing_is_serial_and_failure_is_asset_local(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "three-asset-publishing.sqlite3")
    settings = Settings(
        _env_file=None,
        live_scheduler_enabled=True,
        live_scheduler_asset="NVDAx",
        live_scheduler_assets="NVDAx,SPYx,AAPLx",
        auto_publish_enabled=True,
        publish_enabled=False,
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        scheduler_module.publisher_module,
        "assert_publication_compatible",
        lambda result, _settings, *, asset: result,
    )
    calls = []
    active = 0
    max_active = 0
    call_lock = threading.Lock()

    def fake_publish(result, *, settings, asset):
        nonlocal active, max_active
        assert settings.publish_enabled is False
        assert result.asset == asset
        with call_lock:
            active += 1
            max_active = max(max_active, active)
            calls.append((asset, result.asset))
        try:
            threading.Event().wait(0.01)
            if asset == "SPYx":
                raise PublicationError("synthetic isolated SPY failure")
            return SimpleNamespace(status="published", published_at=1_800_000_000, tx_hash=None)
        finally:
            with call_lock:
                active -= 1

    workers = build_enabled_schedulers(settings, store)
    assert [worker.asset for worker in workers] == ["NVDAx", "SPYx", "AAPLx"]
    ticks = []
    for worker in workers:
        worker.asset_config = replace(
            worker.asset_config,
            capabilities=replace(worker.asset_config.capabilities, onchain=True),
        )
        worker._publisher_fn = fake_publish
        snapshot = _snapshot(timestamp).model_copy(update={"asset": worker.asset})
        result, state = run_inference(snapshot, None)
        store.save_runtime_and_history(
            worker.asset,
            state,
            result,
            tick_status="success",
            tick_attempt_at=timestamp,
            gap_steps=0,
            identity=runtime_identity_for_asset(worker.asset),
        )
        tick = TickResult(worker.asset, timestamp, "success", result, 0, False)
        worker._publish_if_enabled(tick)
        assert worker._pending_publication is result
        ticks.append((worker, result))

    async def publish_all():
        await asyncio.gather(*(worker._publish_one(result) for worker, result in ticks))

    asyncio.run(publish_all())

    assert set(calls) == {("NVDAx", "NVDAx"), ("SPYx", "SPYx"), ("AAPLx", "AAPLx")}
    assert max_active == 1
    expected_status = {"NVDAx": "published", "SPYx": "failed", "AAPLx": "published"}
    for asset, status in expected_status.items():
        publication = store.load_publication(asset)
        assert publication is not None
        assert publication.last_publish_status == status
        assert store.load_runtime(asset).latest_result.asset == asset
    assert store.load_publication("SPYx").last_publish_error == "PublicationError"


def test_multi_worker_selection_skips_known_unready_asset_without_stopping_ready_one(
    tmp_path, monkeypatch
):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    settings = Settings(
        _env_file=None,
        live_scheduler_enabled=True,
        live_scheduler_asset="NVDAx",
        live_scheduler_assets="NVDAx,SPYx",
        auto_publish_enabled=False,
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        scheduler_module,
        "quant_runtime_available",
        lambda config: config.asset == "NVDAx",
    )

    workers = build_enabled_schedulers(settings, store)

    assert [worker.asset for worker in workers] == ["NVDAx"]
    assert build_enabled_schedulers(settings, store, assets=("SPYx",)) == ()


def test_auto_publish_does_not_require_onchain_binding_for_offchain_scheduler(
    tmp_path, monkeypatch
):
    from valtide_api.assets import resolve_asset_config

    calls = []
    timestamp = _ANCHOR + timedelta(minutes=5)
    snapshot = _snapshot(timestamp).model_copy(update={"asset": "SPYx"})
    result, _state = run_inference(snapshot, None)
    settings = SimpleNamespace(
        auto_publish_enabled=True,
        publish_enabled=False,
        live_scheduler_asset="SPYx",
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
    configured = resolve_asset_config("SPYx")
    monkeypatch.setattr(
        scheduler_module,
        "resolve_asset_config",
        lambda _asset, _settings=None: replace(
            configured,
            capabilities=replace(configured.capabilities, onchain=False),
        ),
    )
    scheduler = LiveScheduler(
        asset="SPYx",
        store=RuntimeStore(tmp_path / "spy-runtime.sqlite3"),
        publisher_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    scheduler._publish_if_enabled(
        TickResult(
            asset="SPYx",
            canonical_ts=timestamp,
            status="success",
            result=result,
            gap_steps=0,
            state_restored=False,
        )
    )

    assert calls == []
    assert scheduler._pending_publication is None


def test_wrong_asset_snapshot_is_not_persisted_or_published(tmp_path):
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    timestamp = _ANCHOR + timedelta(minutes=5)
    result = run_live_tick(
        "NVDAx", timestamp, store=store,
        snapshot_builder=lambda **_kwargs: _snapshot(timestamp).model_copy(
            update={"asset": "TESTx"}
        ),
    )
    assert result.status == "failure"
    assert "identity" in result.error
    assert store.load_runtime("NVDAx").latest_result is None
    assert store.load_history("NVDAx") == []
    assert store.load_publication("NVDAx") is None


def _patch_settlement_retry(monkeypatch, *, attempts: int = 5, delay: float = 0.0):
    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(
            live_settlement_max_attempts=attempts,
            live_settlement_retry_delay_seconds=delay,
        ),
    )


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


def test_legacy_sqlite_state_is_preserved_but_not_resumed_without_identity(tmp_path):
    first_ts = _ANCHOR + timedelta(hours=2)
    second_ts = first_ts + timedelta(minutes=5)
    third_ts = second_ts + timedelta(minutes=5)
    path = tmp_path / "legacy-runtime.sqlite3"
    builder, _calls = _builder_for(
        [_snapshot(first_ts), _snapshot(second_ts), _snapshot(third_ts)]
    )
    old_store = RuntimeStore(path)
    first = run_live_tick("NVDAx", first_ts, store=old_store, snapshot_builder=builder)
    assert first.status == "success"
    # Simulate a pre-generation SQLite database while preserving its runtime
    # and history rows exactly as an existing production file would be.
    with old_store._connection:
        old_store._connection.execute("DROP TABLE runtime_generation")
        old_store._connection.execute("DROP TABLE valuation_history_generation")
    old_store.close()

    identity = runtime_identity_for_asset("NVDAx")
    migrated = RuntimeStore(path)
    legacy = migrated.load_runtime("NVDAx", expected_identity=identity)
    assert legacy is not None
    assert legacy.identity_verified is False
    assert legacy.state is None
    assert legacy.latest_result is None
    assert migrated.load_history("NVDAx") == [first.result]
    assert migrated.load_history(
        "NVDAx", expected_identity=identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1"
    ) == []

    second = run_live_tick("NVDAx", second_ts, store=migrated, snapshot_builder=builder)
    assert second.status == "success"
    assert second.state_restored is False
    archived = migrated._connection.execute(
        "SELECT * FROM runtime_state_archive WHERE asset = 'NVDAx'"
    ).fetchone()
    assert archived is not None
    assert archived["prior_runtime_identity"] is None
    assert archived["state_last_ts"] == first_ts.isoformat()
    assert archived["latest_result_json"] == first.result.model_dump_json()
    assert migrated.load_history("NVDAx") == [first.result, second.result]
    assert migrated.load_history(
        "NVDAx", expected_identity=identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1"
    ) == [second.result]
    mismatched = migrated.load_runtime(
        "NVDAx", expected_identity="old-chain1-discovery"
    )
    assert mismatched is not None
    assert mismatched.identity_verified is False
    migrated.close()

    restarted = RuntimeStore(path)
    third = run_live_tick("NVDAx", third_ts, store=restarted, snapshot_builder=builder)
    assert third.status == "success"
    assert third.state_restored is True
    assert restarted.load_history(
        "NVDAx", expected_identity=identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1"
    ) == [second.result, third.result]


def test_old_chain_or_reference_profile_generation_is_archived_not_resumed(tmp_path):
    first_ts = _ANCHOR + timedelta(hours=3)
    second_ts = first_ts + timedelta(minutes=5)
    path = tmp_path / "old-discovery-runtime.sqlite3"
    builder, _calls = _builder_for([_snapshot(first_ts), _snapshot(second_ts)])
    store = RuntimeStore(path)
    first = run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=builder)
    assert first.status == "success"

    # A previous runtime generation may have used an unverified discovered
    # token deployment or a different reference profile. Treat the opaque
    # prior fingerprint as incompatible with today's pinned binding.
    old_identity = "legacy-ethereum-discovery-or-xperp-profile"
    current_identity = runtime_identity_for_asset("NVDAx")
    with store._connection:
        store._connection.execute(
            "UPDATE runtime_generation SET runtime_identity = ? WHERE asset = ?",
            (old_identity, "NVDAx"),
        )
        store._connection.execute(
            "UPDATE valuation_history_generation SET runtime_identity = ? WHERE asset = ?",
            (old_identity, "NVDAx"),
        )

    incompatible = store.load_runtime("NVDAx", expected_identity=current_identity)
    assert incompatible is not None
    assert incompatible.identity_verified is False
    assert incompatible.state is None
    assert incompatible.latest_result is None
    assert store.load_history(
        "NVDAx",
        expected_identity=current_identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
    ) == []
    # Unfiltered local/audit history remains intact and is not deleted.
    assert store.load_history("NVDAx") == [first.result]

    failed = run_live_tick(
        "NVDAx",
        second_ts,
        store=store,
        snapshot_builder=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("temporary source outage")
        ),
    )
    assert failed.status == "failure"
    # A failed new-generation attempt must not relabel the incompatible old
    # carried state as belonging to today's pinned source/profile.
    still_incompatible = store.load_runtime(
        "NVDAx", expected_identity=current_identity
    )
    assert still_incompatible is not None
    assert still_incompatible.identity_verified is False
    assert still_incompatible.state is None
    assert store.load_history("NVDAx") == [first.result]

    second = run_live_tick("NVDAx", second_ts, store=store, snapshot_builder=builder)
    assert second.status == "success"
    assert second.state_restored is False
    archived = store._connection.execute(
        "SELECT prior_runtime_identity FROM runtime_state_archive WHERE asset = ?",
        ("NVDAx",),
    ).fetchone()
    assert archived["prior_runtime_identity"] == old_identity
    assert store.load_history(
        "NVDAx",
        expected_identity=current_identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
    ) == [second.result]
    store.close()

    restarted = RuntimeStore(path)
    record = restarted.load_runtime("NVDAx", expected_identity=current_identity)
    assert record is not None
    assert record.identity_verified is True
    assert record.state is not None
    assert record.state.last_ts == second_ts
    assert restarted.load_history(
        "NVDAx",
        expected_identity=current_identity,
        reference_profile="unified_xstock_p1ac_xperp_evidence_v1",
    ) == [second.result]


def test_initial_tick_failure_status_is_bound_without_creating_state(tmp_path):
    store = RuntimeStore(tmp_path / "first-failure.sqlite3")
    identity = runtime_identity_for_asset("NVDAx")
    store.record_tick_status(
        "NVDAx",
        "failure",
        error="ExactTokenCandleUnavailable",
        identity=identity,
    )

    record = store.load_runtime("NVDAx", expected_identity=identity)

    assert record is not None
    assert record.identity_verified is True
    assert record.state is None
    assert record.latest_result is None
    assert record.last_tick_status == "failure"
    assert record.last_tick_error == "ExactTokenCandleUnavailable"


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

    def failing_builder(*, asset: str, observation_ts: datetime) -> MarketSnapshot:
        assert asset == "NVDAx"
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


def test_settlement_retry_uses_same_timestamp_and_persists_once(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    snapshot = _snapshot(timestamp)
    requested: list[datetime] = []
    builder_attempts = 0
    inference_calls: list[datetime] = []
    original_inference = scheduler_module.run_inference

    def delayed_builder(*, asset, observation_ts):
        assert asset == "NVDAx"
        nonlocal builder_attempts
        requested.append(observation_ts)
        builder_attempts += 1
        if builder_attempts < 4:
            raise ExactNvdaxCandleUnavailable("exact T not indexed yet")
        return snapshot

    def counted_inference(snapshot, state):
        inference_calls.append(snapshot.observation_ts)
        return original_inference(snapshot, state)

    _patch_settlement_retry(monkeypatch)
    monkeypatch.setattr(scheduler_module, "run_inference", counted_inference)

    tick = run_live_tick(
        "NVDAx",
        timestamp,
        store=store,
        snapshot_builder=delayed_builder,
    )

    assert tick.status == "success"
    assert requested == [timestamp, timestamp, timestamp, timestamp]
    assert inference_calls == [timestamp]
    assert store.load_runtime("NVDAx").state.last_ts == timestamp
    assert [result.timestamp for result in store.load_history("NVDAx")] == [timestamp]


def test_settlement_retry_exhaustion_preserves_old_runtime_and_history(tmp_path, monkeypatch):
    first_ts = _ANCHOR + timedelta(minutes=5)
    failed_ts = first_ts + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    builder, _ = _builder_for([_snapshot(first_ts)])
    first = run_live_tick("NVDAx", first_ts, store=store, snapshot_builder=builder)
    before = store.load_runtime("NVDAx")
    assert first.status == "success"
    requested: list[datetime] = []

    def unavailable_builder(*, asset, observation_ts):
        assert asset == "NVDAx"
        requested.append(observation_ts)
        raise ExactNvdaxCandleUnavailable("exact T still unavailable")

    _patch_settlement_retry(monkeypatch)
    failed = run_live_tick(
        "NVDAx",
        failed_ts,
        store=store,
        snapshot_builder=unavailable_builder,
    )

    after = store.load_runtime("NVDAx")
    assert failed.status == "failure"
    assert requested == [failed_ts] * 5
    assert before is not None and after is not None
    assert after.state == before.state
    assert after.latest_result == before.latest_result
    assert after.last_tick_status == "failure"
    assert store.load_history("NVDAx") == [first.result]


def test_non_settlement_live_error_is_not_retried(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    attempts = 0

    def alpaca_failure(*, asset, observation_ts):  # noqa: ARG001
        assert asset == "NVDAx"
        nonlocal attempts
        attempts += 1
        raise LiveDataUnavailable("NVDA underlying unavailable (Alpaca)")

    _patch_settlement_retry(monkeypatch)
    failed = run_live_tick(
        "NVDAx",
        timestamp,
        store=store,
        snapshot_builder=alpaca_failure,
    )

    assert failed.status == "failure"
    assert attempts == 1
    assert "Alpaca" in failed.error
    assert store.load_history("NVDAx") == []


def test_runtime_integrity_error_is_not_retried(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    attempts = 0

    def integrity_failure(*, asset, observation_ts):  # noqa: ARG001
        assert asset == "NVDAx"
        nonlocal attempts
        attempts += 1
        raise RuntimeStateIntegrityError("synthetic persisted-state corruption")

    _patch_settlement_retry(monkeypatch)
    failed = run_live_tick(
        "NVDAx",
        timestamp,
        store=store,
        snapshot_builder=integrity_failure,
    )

    assert failed.status == "failure"
    assert attempts == 1


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


def test_scheduler_has_single_process_start_stop_lifecycle(tmp_path, monkeypatch):
    calls: list[datetime] = []
    clock_values = [datetime(2026, 9, 19, 14, 4, 30, tzinfo=UTC)]
    sleep_delays: list[float] = []

    monkeypatch.setattr(
        scheduler_module,
        "get_settings",
        lambda: SimpleNamespace(
            auto_publish_enabled=False,
            live_scheduler_asset="NVDAx",
            live_settlement_grace_seconds=60,
        ),
    )

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
        sleep_delays.append(delay)
        if len(sleep_delays) > 1:
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
    # The scheduler waits until 14:06 (14:05 boundary plus 60 seconds) but
    # values the just-settled bar whose event-time timestamp is still 14:00.
    assert calls[0] == datetime(2026, 9, 19, 14, 0, tzinfo=UTC)
    assert sleep_delays[0] == 90.0


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
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "deployments" / "xlayer-testnet.json").read_text())
    manifest["assets"]["NVDAx"]["publicationCompatibility"] = {
        "asset": "NVDAx",
        "referenceId": manifest["assets"]["NVDAx"]["referenceId"],
        "referenceProfile": "unified_xstock_p1ac_xperp_evidence_v1",
        "evidenceSemantics": "p1a_xstock_band_with_xperp_review_corroboration_v2",
        "modelId": "P1a-C",
        "modelVersion": "0.2.0",
    }
    manifest_path = Path(store.path).with_name("compatible-xlayer-manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        auto_publish_enabled=enabled,
        live_scheduler_enabled=True,
        live_scheduler_asset="NVDAx",
        deployment_manifest_path=manifest_path,
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
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


def test_auto_publish_is_blocked_before_publisher_for_legacy_binding(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    calls = []
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "deployments" / "xlayer-testnet.json").read_text())
    nvda = manifest["assets"]["NVDAx"]
    manifest["demo"] = {
        key: nvda[key] for key in ("assetId", "referenceId", "modelVersion")
    }
    manifest["contracts"]["DemoCollateralVault"] = nvda["demoVault"]
    manifest.pop("assets")
    manifest.pop("deploymentReceipts", None)
    manifest["deployment"] = manifest.pop("initialDeployment")
    legacy_manifest = tmp_path / "legacy-nvdax-manifest.json"
    legacy_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        auto_publish_enabled=True,
        live_scheduler_enabled=True,
        deployment_manifest_path=legacy_manifest,
    )
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)
    scheduler = LiveScheduler(
        asset="NVDAx",
        store=store,
        publisher_fn=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    scheduler._publish_if_enabled(tick)

    publication = store.load_publication("NVDAx")
    assert calls == []
    assert scheduler._pending_publication is None
    assert publication is not None
    assert publication.last_publish_status == "publication_blocked_semantic_mismatch"
    assert publication.last_publish_error == "deployed_binding_semantics_unverified"
    assert publication.last_publish_observation_ts == timestamp
    assert store.load_runtime("NVDAx").latest_result == tick.result


def test_auto_publish_persists_tick_before_publishing_and_records_success(tmp_path, monkeypatch):
    timestamp = _ANCHOR + timedelta(minutes=5)
    builder, _ = _builder_for([_snapshot(timestamp)])
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    tick = run_live_tick("NVDAx", timestamp, store=store, snapshot_builder=builder)
    calls = []

    def fake_publish(result, *, settings, asset):
        assert asset == "NVDAx"
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

    def fake_publish(result, *, settings, asset):  # noqa: ARG001
        assert asset == "NVDAx"
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

    def failing_builder(*, asset, observation_ts):  # noqa: ARG001
        assert asset == "NVDAx"
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

    def fake_publish(result, *, settings, asset):  # noqa: ARG001
        assert asset == "NVDAx"
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

    def slow_publish(result, *, settings, asset):  # noqa: ARG001
        assert asset == "NVDAx"
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

    def slow_publish(result, *, settings, asset):  # noqa: ARG001
        assert asset == "NVDAx"
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

    def failing_first_publish(result, *, settings, asset):  # noqa: ARG001
        assert asset == "NVDAx"
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


def test_semantic_publication_block_status_survives_restart(tmp_path):
    timestamp = _ANCHOR + timedelta(minutes=5)
    path = tmp_path / "runtime.sqlite3"
    store = RuntimeStore(path)
    store.record_publication_blocked_semantic_mismatch("NVDAx", timestamp)
    store.close()

    restarted = RuntimeStore(path)
    publication = restarted.load_publication("NVDAx")

    assert publication is not None
    assert publication.last_publish_status == "publication_blocked_semantic_mismatch"
    assert publication.last_publish_error == "deployed_binding_semantics_unverified"
    assert publication.last_publish_observation_ts == timestamp
    assert publication.last_published_observation_ts is None


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
