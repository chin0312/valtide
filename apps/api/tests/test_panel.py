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

    assert len(snapshots) == 3
    assert snapshots[0].token_price is None
    assert snapshots[1].token_price == 180.3


def test_reference_is_live_then_explicit_stale_reference(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    assert snapshots[0].observation_ts.minute == 5
    assert snapshots[0].reference_under_test == 180.0
    assert snapshots[0].reference_under_test_source == "stale_nvda"
    assert snapshots[0].underlying_reference is None
    assert snapshots[0].last_trusted_reference == 180.0
    assert snapshots[0].last_trusted_reference_ts.minute == 0


def test_reference_age_grows_over_canonical_grid(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    ages = [snapshot.reference_age_seconds for snapshot in snapshots]
    assert ages == [300, 600, 900]
    assert ages[-1] > ages[0]


def test_panel_replays_through_quant_and_validation(tmp_path):
    snapshots = load_panel_snapshots(_write(tmp_path))

    results = replay(snapshots)

    assert len(results) == len(snapshots)
    assert results[0].evidence_state == EvidenceState.INCONCLUSIVE
    assert "TOKEN_DATA_UNAVAILABLE" in results[0].reason_codes
    assert results[0].observed_token_move_pct is None
    assert results[0].residual_premium_discount_pct is None
    assert results[0].model_id == "P1a-C"
    assert results[0].interval_calibration_source == "global_fallback"
    assert "CALIBRATION_GLOBAL_FALLBACK" in results[0].reason_codes
    assert results[1].timestamp == snapshots[1].observation_ts
    assert results[1].token_price == 180.3


def test_current_nvda_uses_prior_anchor_and_first_anchor_is_not_public(tmp_path):
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:05:00Z,181.0,1000,181.1,500,TRUE,TRUE,closed,5",
        "2026-09-20T14:10:00Z,NA,NA,181.2,500,FALSE,TRUE,closed,10",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *rows]) + "\n"))

    assert [snapshot.observation_ts.minute for snapshot in snapshots] == [5, 10]
    assert snapshots[0].last_trusted_reference == 180.0
    assert snapshots[0].last_trusted_reference_ts.minute == 0
    assert snapshots[0].underlying_reference == 181.0
    assert snapshots[0].underlying_reference_ts == snapshots[0].observation_ts
    assert snapshots[1].last_trusted_reference == 181.0
    assert snapshots[1].last_trusted_reference_ts.minute == 5


def test_explicit_lookback_anchor_keeps_first_requested_row_causal(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,last_trusted_reference,"
        "last_trusted_reference_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "179.0,2026-09-20T13:55:00Z",
        "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,"
        "180.0,2026-09-20T14:00:00Z",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))

    assert len(snapshots) == 2
    assert snapshots[0].last_trusted_reference == 179.0
    assert snapshots[0].last_trusted_reference_ts.minute == 55
    assert snapshots[0].underlying_reference == 180.0
    assert snapshots[0].underlying_reference_ts == snapshots[0].observation_ts


def test_explicit_reference_columns_do_not_fill_missing_observations(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,"
        "reference_under_test,reference_under_test_available,"
        "reference_under_test_source,reference_under_test_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "190.0,TRUE,okx_xperp_index,2026-09-20T14:00:00Z",
        "2026-09-20T14:05:00Z,NA,NA,NA,NA,FALSE,FALSE,closed,"
        ",FALSE,okx_xperp_index,",
        "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,"
        ",FALSE,okx_xperp_index,",
    ]
    snapshots = load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))

    assert len(snapshots) == 2
    assert snapshots[0].reference_under_test is None
    assert snapshots[0].reference_under_test_source == "okx_xperp_index"
    assert snapshots[0].token_price is None
    assert snapshots[1].reference_under_test is None


def test_non_five_minute_panel_fails_explicitly(tmp_path):
    bad_rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:10:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,10",
    ]
    with pytest.raises(PanelTimestampError, match="exactly 5 minutes"):
        load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *bad_rows]) + "\n"))


def test_noncanonical_panel_boundary_fails_explicitly(tmp_path):
    rows = [
        "2026-09-20T14:02:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,0",
        "2026-09-20T14:07:00Z,NA,NA,180.3,900,FALSE,TRUE,closed,5",
    ]
    with pytest.raises(PanelTimestampError, match="canonical 5-minute"):
        load_panel_snapshots(_write(tmp_path, "\n".join([_COLS, *rows]) + "\n"))


def test_panel_rejects_future_reference_observation(tmp_path):
    columns = (
        "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
        "nvda_available,nvdax_available,session_state,"
        "reference_under_test,reference_under_test_available,"
        "reference_under_test_source,reference_under_test_ts"
    )
    rows = [
        "2026-09-20T14:00:00Z,180.0,1000,180.1,500,TRUE,TRUE,closed,"
        "190.0,TRUE,okx_xperp_index,2026-09-20T14:05:00Z",
    ]
    with pytest.raises(PanelTimestampError, match="must not be after"):
        load_panel_snapshots(_write(tmp_path, "\n".join([columns, *rows]) + "\n"))
