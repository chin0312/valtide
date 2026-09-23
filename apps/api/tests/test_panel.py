"""Panel loader and backend × quant replay integration tests."""

import pytest

from valtide_api.models import EvidenceState
from valtide_api.panel import PanelTimestampError, load_panel_snapshots
from valtide_api.replay import replay

_COLS = (
    "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
    "nvda_available,nvdax_available,session_state,time_since_nvda_min"
)
_ROWS = [
    "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
    "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,5",
    "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,10",
    "2026-09-20T14:15:00Z,NA,NA,180.4,950,FALSE,TRUE,closed,15",
]
_CSV = "\n".join([_COLS, *_ROWS]) + "\n"


def _write(tmp_path, contents: str = _CSV):
    path = tmp_path / "p0_panel_5m.csv"
    path.write_text(contents)
    return path


def test_missing_token_row_is_preserved(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    assert len(snapshots) == 4
    assert snapshots[1].token_price is None
    assert snapshots[2].token_price == 180.3


def test_reference_is_live_then_explicit_stale_reference(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    assert snapshots[0].reference_under_test == 180.0
    assert snapshots[0].reference_under_test_source == "nvda_live"
    assert snapshots[1].reference_under_test == 180.0
    assert snapshots[1].reference_under_test_source == "stale_nvda"
    assert snapshots[1].underlying_reference is None


def test_reference_age_grows_over_canonical_grid(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    ages = [snapshot.reference_age_seconds for snapshot in snapshots]
    assert ages == sorted(ages)
    assert ages[-1] > ages[0]


def test_panel_replays_through_quant_and_validation(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    results = replay(snapshots)

    assert len(results) == len(snapshots)
    assert results[1].evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_DATA_UNAVAILABLE" in results[1].reason_codes
    assert results[1].observed_token_move_pct is None
    assert results[1].residual_premium_discount_pct is None
    assert results[1].model_id == "P1a-C"
    assert results[1].interval_calibration_source == "global_fallback"
    assert "CALIBRATION_GLOBAL_FALLBACK" in results[1].reason_codes
    assert results[2].timestamp == snapshots[2].observation_ts
    assert results[2].token_price == 180.3


def test_non_five_minute_panel_fails_explicitly(tmp_path):
    bad_rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,10",
    ]
    with pytest.raises(PanelTimestampError, match="exactly 5 minutes"):
        load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *bad_rows]) + "\n"))
