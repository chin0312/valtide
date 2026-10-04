"""Durable single-process runtime state for warmed live inference."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from valtide_api.clock import require_canonical_5m
from valtide_api.config import get_settings
from valtide_api.models import ValuationResult
from valtide_api.state_store import KalmanState


class RuntimeStateIntegrityError(RuntimeError):
    """Raised when persisted runtime state cannot be trusted safely."""


@dataclass(frozen=True)
class RuntimeRecord:
    asset: str
    state: KalmanState | None
    latest_result: ValuationResult | None
    updated_at: datetime | None
    last_tick_status: str | None
    last_tick_error: str | None
    last_tick_attempt_at: datetime | None
    last_gap_steps: int
    identity_verified: bool | None = None


@dataclass(frozen=True)
class PublicationRecord:
    """Durable downstream publication delivery state for one asset."""

    asset: str
    last_publish_status: str | None
    last_publish_error: str | None
    last_publish_attempt_at: datetime | None
    last_publish_observation_ts: datetime | None
    last_published_observation_ts: datetime | None
    last_published_at: int | None
    last_publish_tx_hash: str | None


def _parse_datetime(value: str | None, label: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeStateIntegrityError(f"invalid persisted {label}: {value!r}") from exc
    if parsed.tzinfo is None:
        raise RuntimeStateIntegrityError(f"persisted {label} must be timezone-aware")
    return parsed.astimezone(UTC)


def _parse_optional_int(value: int | str | None, label: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeStateIntegrityError(f"invalid persisted {label}: {value!r}") from exc


def runtime_identity_for_asset(asset: str, settings=None) -> str:
    """Return a non-secret fingerprint for the active data/profile/model binding."""
    from valtide_api.assets import resolve_asset_config
    from valtide_api.quant_runtime import resolve_quant_runtime

    config = resolve_asset_config(asset, settings)
    runtime = resolve_quant_runtime(config)
    binding = {
        "asset": config.asset,
        "token_source": config.token_source,
        "token_chain_index": config.okx_chain_index,
        "token_address": config.token_address,
        "reference_profile": config.reference_profile,
        "reference_source": config.reference_under_test_source,
        "reference_instrument": config.reference_under_test_instrument,
        "quant_runtime_key": config.quant_runtime_key,
        "model_id": runtime.model_id,
        "model_version": runtime.model_version,
    }
    encoded = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class RuntimeStore:
    """SQLite-backed state store with one connection for the MVP process."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            db_path = Path(self.path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    asset TEXT PRIMARY KEY,
                    state_m REAL,
                    state_p REAL,
                    state_last_ts TEXT,
                    latest_result_json TEXT,
                    latest_result_ts TEXT,
                    updated_at TEXT,
                    last_tick_status TEXT,
                    last_tick_error TEXT,
                    last_tick_attempt_at TEXT,
                    last_gap_steps INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS publication_state (
                    asset TEXT PRIMARY KEY,
                    last_publish_status TEXT,
                    last_publish_error TEXT,
                    last_publish_attempt_at TEXT,
                    last_publish_observation_ts TEXT,
                    last_published_observation_ts TEXT,
                    last_published_at INTEGER,
                    last_publish_tx_hash TEXT
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS valuation_history (
                    asset TEXT NOT NULL,
                    observation_ts TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (asset, observation_ts)
                )
                """
            )
            # Additive generation tables keep legacy SQLite rows intact while
            # allowing current state/history to be bound to a verified runtime
            # identity. Rows without generation records remain preserved but
            # are not resumable or included in current-profile history APIs.
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_generation (
                    asset TEXT PRIMARY KEY,
                    runtime_identity TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state_archive (
                    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    prior_runtime_identity TEXT,
                    archived_at TEXT NOT NULL,
                    state_m REAL,
                    state_p REAL,
                    state_last_ts TEXT,
                    latest_result_json TEXT,
                    latest_result_ts TEXT,
                    updated_at TEXT,
                    last_tick_status TEXT,
                    last_tick_error TEXT,
                    last_tick_attempt_at TEXT,
                    last_gap_steps INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS valuation_history_generation (
                    asset TEXT NOT NULL,
                    observation_ts TEXT NOT NULL,
                    runtime_identity TEXT NOT NULL,
                    reference_profile TEXT NOT NULL,
                    PRIMARY KEY (asset, observation_ts)
                )
                """
            )

    def load_runtime(
        self, asset: str, *, expected_identity: str | None = None
    ) -> RuntimeRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM runtime_state WHERE asset = ?", (asset,)
            ).fetchone()
            identity_row = self._connection.execute(
                "SELECT runtime_identity FROM runtime_generation WHERE asset = ?",
                (asset,),
            ).fetchone()
        if row is None:
            return None

        identity_verified = None
        if expected_identity is not None:
            stored_identity = identity_row["runtime_identity"] if identity_row else None
            identity_verified = stored_identity == expected_identity
            if not identity_verified:
                # Do not parse or resume stale carried state/result. The original
                # runtime_state and history rows remain untouched for audit.
                return RuntimeRecord(
                    asset=asset,
                    state=None,
                    latest_result=None,
                    updated_at=_parse_datetime(row["updated_at"], "updated_at"),
                    last_tick_status=row["last_tick_status"],
                    last_tick_error=(
                        "persisted runtime identity is unverified for the active binding"
                    ),
                    last_tick_attempt_at=_parse_datetime(
                        row["last_tick_attempt_at"], "last_tick_attempt_at"
                    ),
                    last_gap_steps=int(row["last_gap_steps"] or 0),
                    identity_verified=False,
                )

        state_values = (row["state_m"], row["state_p"], row["state_last_ts"])
        if any(value is not None for value in state_values) and not all(
            value is not None for value in state_values
        ):
            raise RuntimeStateIntegrityError(f"partial persisted state for asset {asset}")

        state: KalmanState | None = None
        if all(value is not None for value in state_values):
            last_ts = _parse_datetime(row["state_last_ts"], "state_last_ts")
            assert last_ts is not None
            try:
                last_ts = require_canonical_5m(last_ts, "persisted state_last_ts")
            except ValueError as exc:
                raise RuntimeStateIntegrityError(str(exc)) from exc
            state = KalmanState(
                m=float(row["state_m"]),
                P=float(row["state_p"]),
                last_ts=last_ts,
            )

        latest_result = None
        if row["latest_result_json"] is not None:
            try:
                latest_result = ValuationResult.model_validate_json(row["latest_result_json"])
            except (TypeError, ValueError) as exc:
                raise RuntimeStateIntegrityError(
                    f"invalid persisted latest_result_json for asset {asset}"
                ) from exc
            try:
                result_timestamp = require_canonical_5m(
                    latest_result.timestamp, "persisted latest_result.timestamp"
                )
            except ValueError as exc:
                raise RuntimeStateIntegrityError(str(exc)) from exc
            if state is not None and result_timestamp != state.last_ts:
                raise RuntimeStateIntegrityError(
                    f"persisted state/result timestamps disagree for asset {asset}"
                )
            if latest_result.asset != asset:
                raise RuntimeStateIntegrityError(
                    f"persisted latest result asset does not match its key for asset {asset}"
                )

        return RuntimeRecord(
            asset=asset,
            state=state,
            latest_result=latest_result,
            updated_at=_parse_datetime(row["updated_at"], "updated_at"),
            last_tick_status=row["last_tick_status"],
            last_tick_error=row["last_tick_error"],
            last_tick_attempt_at=_parse_datetime(
                row["last_tick_attempt_at"], "last_tick_attempt_at"
            ),
            last_gap_steps=int(row["last_gap_steps"] or 0),
            identity_verified=identity_verified,
        )

    def load_publication(self, asset: str) -> PublicationRecord | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM publication_state WHERE asset = ?", (asset,)
            ).fetchone()
        if row is None:
            return None
        return PublicationRecord(
            asset=asset,
            last_publish_status=row["last_publish_status"],
            last_publish_error=row["last_publish_error"],
            last_publish_attempt_at=_parse_datetime(
                row["last_publish_attempt_at"], "last_publish_attempt_at"
            ),
            last_publish_observation_ts=_parse_datetime(
                row["last_publish_observation_ts"], "last_publish_observation_ts"
            ),
            last_published_observation_ts=_parse_datetime(
                row["last_published_observation_ts"], "last_published_observation_ts"
            ),
            last_published_at=_parse_optional_int(
                row["last_published_at"], "last_published_at"
            ),
            last_publish_tx_hash=row["last_publish_tx_hash"],
        )

    def load_history(
        self,
        asset: str,
        limit: int = 72,
        *,
        expected_identity: str | None = None,
        reference_profile: str | None = None,
    ) -> list[ValuationResult]:
        """Return successful warmed observations in chronological order."""
        if not 1 <= int(limit) <= 2016:
            raise ValueError("history limit must be between 1 and 2016")
        with self._lock:
            if expected_identity is None and reference_profile is None:
                rows = self._connection.execute(
                    """
                    SELECT result_json, NULL AS stored_reference_profile
                    FROM valuation_history
                    WHERE asset = ?
                    ORDER BY observation_ts DESC
                    LIMIT ?
                    """,
                    (asset, int(limit)),
                ).fetchall()
            else:
                clauses = ["h.asset = ?"]
                params: list[str | int] = [asset]
                if expected_identity is not None:
                    clauses.append("g.runtime_identity = ?")
                    params.append(expected_identity)
                if reference_profile is not None:
                    clauses.append("g.reference_profile = ?")
                    params.append(reference_profile)
                params.append(int(limit))
                rows = self._connection.execute(
                    f"""
                    SELECT h.result_json, g.reference_profile AS stored_reference_profile
                    FROM valuation_history AS h
                    JOIN valuation_history_generation AS g
                      ON g.asset = h.asset AND g.observation_ts = h.observation_ts
                    WHERE {' AND '.join(clauses)}
                    ORDER BY h.observation_ts DESC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
        results: list[ValuationResult] = []
        for row in reversed(rows):
            try:
                result = ValuationResult.model_validate_json(row["result_json"])
                require_canonical_5m(result.timestamp, "persisted history.timestamp")
                if result.asset != asset:
                    raise ValueError("persisted history asset does not match its key")
                stored_profile = row["stored_reference_profile"]
                if stored_profile is not None and result.reference_profile != stored_profile:
                    raise ValueError("persisted history profile does not match its generation")
            except (TypeError, ValueError) as exc:
                raise RuntimeStateIntegrityError(
                    f"invalid persisted valuation history for asset {asset}"
                ) from exc
            results.append(result)
        return results

    @staticmethod
    def _publication_timestamp(value: datetime, label: str) -> datetime:
        try:
            return require_canonical_5m(value, label)
        except ValueError as exc:
            raise RuntimeStateIntegrityError(str(exc)) from exc

    def record_publication_attempt(
        self,
        asset: str,
        observation_ts: datetime,
        *,
        attempt_at: datetime | None = None,
    ) -> None:
        observation_ts = self._publication_timestamp(observation_ts, "observation_ts")
        attempt_at = attempt_at or datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO publication_state (
                    asset, last_publish_status, last_publish_error,
                    last_publish_attempt_at, last_publish_observation_ts
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    last_publish_status = excluded.last_publish_status,
                    last_publish_error = excluded.last_publish_error,
                    last_publish_attempt_at = excluded.last_publish_attempt_at,
                    last_publish_observation_ts = excluded.last_publish_observation_ts
                """,
                (
                    asset,
                    "attempting",
                    None,
                    attempt_at.astimezone(UTC).isoformat(),
                    observation_ts.isoformat(),
                ),
            )

    def record_publication_success(
        self,
        asset: str,
        observation_ts: datetime,
        *,
        status: str,
        published_at: int | None,
        tx_hash: str | None,
        attempt_at: datetime | None = None,
    ) -> None:
        observation_ts = self._publication_timestamp(observation_ts, "observation_ts")
        attempt_at = attempt_at or datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO publication_state (
                    asset, last_publish_status, last_publish_error,
                    last_publish_attempt_at, last_publish_observation_ts,
                    last_published_observation_ts, last_published_at,
                    last_publish_tx_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    last_publish_status = excluded.last_publish_status,
                    last_publish_error = excluded.last_publish_error,
                    last_publish_attempt_at = excluded.last_publish_attempt_at,
                    last_publish_observation_ts = excluded.last_publish_observation_ts,
                    last_published_observation_ts = excluded.last_published_observation_ts,
                    last_published_at = excluded.last_published_at,
                    last_publish_tx_hash = excluded.last_publish_tx_hash
                """,
                (
                    asset,
                    status,
                    None,
                    attempt_at.astimezone(UTC).isoformat(),
                    observation_ts.isoformat(),
                    observation_ts.isoformat(),
                    published_at,
                    tx_hash,
                ),
            )

    def record_publication_failure(
        self,
        asset: str,
        observation_ts: datetime,
        *,
        error: str,
        attempt_at: datetime | None = None,
    ) -> None:
        observation_ts = self._publication_timestamp(observation_ts, "observation_ts")
        attempt_at = attempt_at or datetime.now(UTC)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO publication_state (
                    asset, last_publish_status, last_publish_error,
                    last_publish_attempt_at, last_publish_observation_ts
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    last_publish_status = excluded.last_publish_status,
                    last_publish_error = excluded.last_publish_error,
                    last_publish_attempt_at = excluded.last_publish_attempt_at,
                    last_publish_observation_ts = excluded.last_publish_observation_ts
                """,
                (
                    asset,
                    "failed",
                    error,
                    attempt_at.astimezone(UTC).isoformat(),
                    observation_ts.isoformat(),
                ),
            )

    @staticmethod
    def _validated_runtime_values(
        state: KalmanState,
        result: ValuationResult,
        *,
        asset: str,
    ) -> tuple[datetime, datetime]:
        if result.asset != asset:
            raise RuntimeStateIntegrityError(
                f"result asset {result.asset} does not match runtime key {asset}"
            )
        if state.last_ts is None:
            raise RuntimeStateIntegrityError("cannot persist state without last_ts")
        try:
            last_ts = require_canonical_5m(state.last_ts, "state.last_ts")
        except ValueError as exc:
            raise RuntimeStateIntegrityError(str(exc)) from exc
        try:
            result_ts = require_canonical_5m(result.timestamp, "result.timestamp")
        except ValueError as exc:
            raise RuntimeStateIntegrityError(str(exc)) from exc
        if result_ts != last_ts:
            raise RuntimeStateIntegrityError("state and result timestamps must match")
        return last_ts, result_ts

    def _save_runtime_locked(
        self,
        asset: str,
        state: KalmanState,
        result: ValuationResult,
        *,
        tick_status: str = "success",
        tick_error: str | None = None,
        tick_attempt_at: datetime | None = None,
        gap_steps: int = 0,
        identity: str | None = None,
    ) -> None:
        last_ts, result_ts = self._validated_runtime_values(state, result, asset=asset)
        attempt_at = tick_attempt_at or datetime.now(UTC)
        updated_at = datetime.now(UTC)
        if identity is not None:
            prior = self._connection.execute(
                "SELECT * FROM runtime_state WHERE asset = ?", (asset,)
            ).fetchone()
            prior_generation = self._connection.execute(
                "SELECT runtime_identity FROM runtime_generation WHERE asset = ?",
                (asset,),
            ).fetchone()
            prior_identity = (
                prior_generation["runtime_identity"] if prior_generation else None
            )
            if (
                prior is not None
                and prior_identity != identity
                and any(
                    prior[field] is not None
                    for field in (
                        "state_m", "state_p", "state_last_ts",
                        "latest_result_json", "latest_result_ts",
                    )
                )
            ):
                # Preserve the complete old row before its single-active-runtime
                # slot is advanced. This is additive migration behavior; legacy
                # operational history itself is never deleted or rewritten.
                self._connection.execute(
                    """
                    INSERT INTO runtime_state_archive (
                        asset, prior_runtime_identity, archived_at, state_m, state_p,
                        state_last_ts, latest_result_json, latest_result_ts, updated_at,
                        last_tick_status, last_tick_error, last_tick_attempt_at,
                        last_gap_steps
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        asset,
                        prior_identity,
                        datetime.now(UTC).isoformat(),
                        prior["state_m"],
                        prior["state_p"],
                        prior["state_last_ts"],
                        prior["latest_result_json"],
                        prior["latest_result_ts"],
                        prior["updated_at"],
                        prior["last_tick_status"],
                        prior["last_tick_error"],
                        prior["last_tick_attempt_at"],
                        prior["last_gap_steps"],
                    ),
                )
        self._connection.execute(
            """
            INSERT INTO runtime_state (
                asset, state_m, state_p, state_last_ts, latest_result_json,
                latest_result_ts, updated_at, last_tick_status, last_tick_error,
                last_tick_attempt_at, last_gap_steps
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET
                state_m = excluded.state_m,
                state_p = excluded.state_p,
                state_last_ts = excluded.state_last_ts,
                latest_result_json = excluded.latest_result_json,
                latest_result_ts = excluded.latest_result_ts,
                updated_at = excluded.updated_at,
                last_tick_status = excluded.last_tick_status,
                last_tick_error = excluded.last_tick_error,
                last_tick_attempt_at = excluded.last_tick_attempt_at,
                last_gap_steps = excluded.last_gap_steps
            """,
            (
                asset,
                state.m,
                state.P,
                last_ts.isoformat(),
                result.model_dump_json(),
                result_ts.isoformat(),
                updated_at.isoformat(),
                tick_status,
                tick_error,
                attempt_at.isoformat(),
                gap_steps,
            )
        )
        if identity is not None:
            self._connection.execute(
                """
                INSERT INTO runtime_generation (asset, runtime_identity, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    runtime_identity = excluded.runtime_identity,
                    updated_at = excluded.updated_at
                """,
                (asset, identity, updated_at.isoformat()),
            )

    def save_runtime(
        self,
        asset: str,
        state: KalmanState,
        result: ValuationResult,
        *,
        tick_status: str = "success",
        tick_error: str | None = None,
        tick_attempt_at: datetime | None = None,
        gap_steps: int = 0,
        identity: str | None = None,
    ) -> None:
        with self._lock, self._connection:
            self._save_runtime_locked(
                asset,
                state,
                result,
                tick_status=tick_status,
                tick_error=tick_error,
                tick_attempt_at=tick_attempt_at,
                gap_steps=gap_steps,
                identity=identity,
            )

    def save_runtime_and_history(
        self,
        asset: str,
        state: KalmanState,
        result: ValuationResult,
        *,
        tick_status: str = "success",
        tick_error: str | None = None,
        tick_attempt_at: datetime | None = None,
        gap_steps: int = 0,
        identity: str | None = None,
    ) -> None:
        """Persist the latest warmed state and successful observation atomically."""
        _last_ts, result_ts = self._validated_runtime_values(state, result, asset=asset)
        with self._lock, self._connection:
            self._save_runtime_locked(
                asset,
                state,
                result,
                tick_status=tick_status,
                tick_error=tick_error,
                tick_attempt_at=tick_attempt_at,
                gap_steps=gap_steps,
                identity=identity,
            )
            inserted = self._connection.execute(
                """
                INSERT INTO valuation_history (asset, observation_ts, result_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(asset, observation_ts) DO NOTHING
                """,
                (
                    asset,
                    result_ts.isoformat(),
                    result.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            if identity is not None and inserted.rowcount == 1:
                self._connection.execute(
                    """
                    INSERT INTO valuation_history_generation (
                        asset, observation_ts, runtime_identity, reference_profile
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (asset, result_ts.isoformat(), identity, result.reference_profile),
                )

    def record_tick_status(
        self,
        asset: str,
        status: str,
        *,
        error: str | None = None,
        attempt_at: datetime | None = None,
        gap_steps: int = 0,
        identity: str | None = None,
    ) -> None:
        attempt_at = attempt_at or datetime.now(UTC)
        updated_at = datetime.now(UTC)
        with self._lock, self._connection:
            previous = self._connection.execute(
                "SELECT state_m, state_p, state_last_ts, latest_result_json, latest_result_ts "
                "FROM runtime_state WHERE asset = ?",
                (asset,),
            ).fetchone()
            previous_generation = self._connection.execute(
                "SELECT runtime_identity FROM runtime_generation WHERE asset = ?",
                (asset,),
            ).fetchone()
            has_persisted_generation = previous is not None and any(
                previous[field] is not None
                for field in (
                    "state_m", "state_p", "state_last_ts",
                    "latest_result_json", "latest_result_ts",
                )
            )
            may_bind_identity = bool(
                identity is not None
                and (
                    not has_persisted_generation
                    or (
                        previous_generation is not None
                        and previous_generation["runtime_identity"] == identity
                    )
                )
            )
            self._connection.execute(
                """
                INSERT INTO runtime_state (
                    asset, updated_at, last_tick_status, last_tick_error,
                    last_tick_attempt_at, last_gap_steps
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    last_tick_status = excluded.last_tick_status,
                    last_tick_error = excluded.last_tick_error,
                    last_tick_attempt_at = excluded.last_tick_attempt_at,
                    last_gap_steps = excluded.last_gap_steps
                """,
                (
                    asset,
                    updated_at.isoformat(),
                    status,
                    error,
                    attempt_at.isoformat(),
                    gap_steps,
                ),
            )
            if may_bind_identity:
                self._connection.execute(
                    """
                    INSERT INTO runtime_generation (asset, runtime_identity, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(asset) DO UPDATE SET
                        runtime_identity = excluded.runtime_identity,
                        updated_at = excluded.updated_at
                    """,
                    (asset, identity, updated_at.isoformat()),
                )

    def reset_runtime(self, asset: str) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM runtime_state WHERE asset = ?", (asset,))
            self._connection.execute("DELETE FROM runtime_generation WHERE asset = ?", (asset,))

    def raw_status(self, asset: str) -> dict[str, Any] | None:
        """Read status columns without parsing state, for corruption diagnostics."""
        with self._lock:
            row = self._connection.execute(
                """
                SELECT state_last_ts, latest_result_ts, last_tick_status,
                       last_tick_error, last_tick_attempt_at, last_gap_steps
                FROM runtime_state WHERE asset = ?
                """,
                (asset,),
            ).fetchone()
        return dict(row) if row is not None else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()


def get_runtime_store() -> RuntimeStore:
    """Return the process-wide store configured by the environment."""
    return _get_runtime_store(str(get_settings().resolved_state_db_path))


@lru_cache(maxsize=8)
def _get_runtime_store(path: str) -> RuntimeStore:
    return RuntimeStore(path)


def clear_runtime_store_cache() -> None:
    """Clear the cached store factory; useful for tests and controlled shutdown."""
    _get_runtime_store.cache_clear()


__all__ = [
    "PublicationRecord",
    "RuntimeRecord",
    "RuntimeStateIntegrityError",
    "RuntimeStore",
    "clear_runtime_store_cache",
    "get_runtime_store",
]
