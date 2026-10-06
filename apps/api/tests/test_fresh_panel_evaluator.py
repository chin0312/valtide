from datetime import UTC, datetime, timedelta

import pytest
from quant.tools.evaluate_fresh_panels import evaluate_panel

from valtide_api.assets import resolve_asset_config
from valtide_api.config import Settings


def _iso(timestamp):
    return timestamp.isoformat().replace("+00:00", "Z")


def _write_spy_panel(path):
    config = resolve_asset_config("SPYx", Settings(_env_file=None))
    header = (
        "timestamp_utc,asset,underlying_symbol,token_source,token_chain_index,"
        "token_address,reference_under_test_instrument,session_state,token_close,"
        "token_volume,token_volume_usd,token_available,token_observed_at,"
        "underlying_close,underlying_available,underlying_observed_at,"
        "last_trusted_reference,last_trusted_reference_ts,reference_under_test,"
        "reference_under_test_available,reference_under_test_source,"
        "reference_under_test_ts,reference_profile"
    )
    rows = []
    start = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    for index in range(4):
        timestamp = start + timedelta(minutes=5 * index)
        underlying = 500.0 + index * 0.1
        token = 500.1 + index * 0.1
        reference = 500.2 + index * 0.1
        timestamp_text = _iso(timestamp)
        prior_timestamp_text = _iso(timestamp - timedelta(minutes=5))
        row = (
            f"{timestamp_text},SPYx,SPY,"
            f"okx_onchainos,{config.okx_chain_index},{config.token_address},SPY-USD,"
            f"regular,{token},100,50000,TRUE,{timestamp_text},"
            f"{underlying},TRUE,{timestamp_text},"
            f"{underlying - 0.1},{prior_timestamp_text},"
            f"{reference},TRUE,okx_xperp_index,{timestamp_text},"
            "unified_xstock_p1ac_xperp_evidence_v1"
        )
        rows.append(row)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_fresh_panel_evaluator_uses_verified_asset_runtime_and_real_replay(tmp_path):
    panel = _write_spy_panel(tmp_path / "spyx.csv")

    result = evaluate_panel("SPYx", panel)

    assert result["asset"] == "SPYx"
    assert result["panel"]["canonical_identity_verified"] is True
    assert result["panel"]["replay_compatible"] is True
    assert result["panel"]["input_rows"] == 4
    assert result["panel"]["replay_observations"] == 4
    assert result["identity"]["chain_index"] == "501"
    assert result["identity"]["token_address"] == (
        "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"
    )
    assert result["runtime"]["model_id"] == "P1a-C"
    assert result["runtime"]["model_version"] == "0.3.0"
    assert result["source_counts"]["xperp_index"] == 4
    assert result["token_update_weight"]["n_token_observations"] == 4
    assert 0 <= result["token_update_weight"]["max_gain"] <= 1
    assert result["n_evaluable"] == 4
    assert sum(result["evidence_state_counts"].values()) == 4
    assert "not create a newly calibrated combined" in result["interpretation"][
        "evidence_states"
    ]


def test_fresh_panel_evaluator_rejects_cross_asset_panel(tmp_path):
    panel = _write_spy_panel(tmp_path / "spyx.csv")

    with pytest.raises(ValueError, match="not verified/replay-ready"):
        evaluate_panel("QQQx", panel)
