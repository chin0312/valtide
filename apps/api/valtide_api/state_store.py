"""In-memory state store — Kalman state + latest result per asset.

MVP: a process-local singleton (BACKEND_PLAN.md §10). Swap for SQLite/Redis later
without touching business logic. NOT the thing that advances state — the replay
driver / scheduler owns writes; API routes only read latest results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from valtide_api.models import ValuationResult


@dataclass
class KalmanState:
    m: float
    P: float
    last_ts: datetime | None = None


_states: dict[str, KalmanState] = {}
_results: dict[str, ValuationResult] = {}


def load_state(asset: str) -> KalmanState | None:
    return _states.get(asset)


def save_state(asset: str, state: KalmanState) -> None:
    _states[asset] = state


def get_latest_result(asset: str) -> ValuationResult | None:
    return _results.get(asset)


def save_latest_result(asset: str, result: ValuationResult) -> None:
    _results[asset] = result


def reset() -> None:
    """Clear all state — used by tests."""
    _states.clear()
    _results.clear()
