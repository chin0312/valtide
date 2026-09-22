"""Panel loader tests — parses James's p0_panel_5m.csv format into snapshots."""

from valtide_api.panel import load_panel_snapshots

# Mimics build_panel.R output: NVDA present Friday, absent over the weekend.
_COLS = (
    "timestamp_utc,nvda_close,nvda_volume,nvdax_close,nvdax_volume,"
    "nvda_available,nvdax_available,session_state,time_since_nvda_min"
)
_ROWS = [
    "2026-09-18T19:55:00Z,180.0,1000,180.1,500,TRUE,TRUE,regular,0",
    "2026-09-18T20:00:00Z,180.0,1200,180.2,400,TRUE,TRUE,afterhours,0",
    "2026-09-19T14:00:00Z,NA,NA,182.5,700,FALSE,TRUE,closed,1080",
    "2026-09-19T22:00:00Z,NA,NA,,,FALSE,FALSE,closed,1560",
    "2026-09-20T14:00:00Z,NA,NA,185.1,900,FALSE,TRUE,closed,2520",
]
_CSV = "\n".join([_COLS, *_ROWS]) + "\n"


def _write(tmp_path):
    p = tmp_path / "p0_panel_5m.csv"
    p.write_text(_CSV)
    return p


def test_skips_rows_without_token_price(tmp_path):
    snaps = load_panel_snapshots(_write(tmp_path))
    # 5 rows, but the 22:00 row has no token price -> skipped -> 4 snapshots.
    assert len(snaps) == 4


def test_reference_is_live_nvda_when_open(tmp_path):
    snaps = load_panel_snapshots(_write(tmp_path))
    first = snaps[0]
    assert first.reference_under_test == 180.0
    assert first.reference_under_test_source == "nvda_live"
    assert first.underlying_reference == 180.0


def test_reference_is_stale_close_on_weekend(tmp_path):
    snaps = load_panel_snapshots(_write(tmp_path))
    weekend = [s for s in snaps if s.market_state.value == "closed"]
    assert weekend, "expected weekend rows"
    for s in weekend:
        # No live NVDA -> reference falls back to last trusted close (180.0).
        assert s.reference_under_test == 180.0
        assert s.reference_under_test_source == "stale_nvda"
        assert s.underlying_reference is None


def test_reference_age_grows_over_weekend(tmp_path):
    snaps = load_panel_snapshots(_write(tmp_path))
    ages = [s.reference_age_seconds for s in snaps]
    assert ages == sorted(ages)  # monotonically non-decreasing
    assert ages[-1] > ages[0]


def test_token_price_carried_through(tmp_path):
    snaps = load_panel_snapshots(_write(tmp_path))
    assert snaps[-1].token_price == 185.1
    assert snaps[-1].token_volume == 900.0
