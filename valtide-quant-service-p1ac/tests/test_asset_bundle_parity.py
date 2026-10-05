"""Frozen model-bundle identity and R-to-Python numerical parity checks."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from valtide_quant_service import FilterState, QuantService
from valtide_quant_service.artifacts import load_p1a
from valtide_quant_service.schemas import MarketSnapshot


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    PACKAGE_ROOT.parent / "quant/runtime/p1ac/parity/p1ac_r_expected.json"
)
PARITY_FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, rel_tol=2e-12, abs_tol=2e-12)


@pytest.mark.parametrize("asset", ("SPYx", "QQQx", "AAPLx"))
def test_exported_asset_bundle_matches_frozen_james_r_steps(asset: str) -> None:
    expected = PARITY_FIXTURE["assets"][asset]
    bundle_dir = PACKAGE_ROOT / "src/valtide_quant_service/model_artifacts" / asset.lower()
    model_path = bundle_dir / "p1a_runtime.json"
    calibration_path = bundle_dir / "p1a_c_calibrator.json"
    artifact = load_p1a(model_path)

    assert artifact.asset == asset
    assert artifact.deployment_model_id == "P1a-C"
    assert artifact.model_version == expected["model_version"]
    assert artifact.source_fit_sha256 == expected["source_fit_sha256"]
    assert artifact.source_dataset_sha256 == expected["dataset_sha256"]

    service = QuantService.from_artifacts(
        model_path,
        calibration_path,
        state=FilterState(
            m=expected["initial_state_m"],
            P=expected["initial_state_P"],
        ),
    )
    for expected_step in expected["steps"]:
        snapshot = MarketSnapshot(
            asset=asset,
            timestamp=datetime.fromisoformat(expected_step["timestamp"].replace("Z", "+00:00")),
            quant_session=expected_step["session"],
            token_price=expected_step["token_price"],
            current_underlying_price=expected_step["current_underlying_price"],
            last_trusted_reference=None,
            last_trusted_reference_timestamp=None,
        )
        result = service.update(snapshot)
        for field in (
            "challenger_m_log",
            "challenger_P_log",
            "reference_predictive_sd_log",
            "fair_value",
            "lower_bound",
            "upper_bound",
        ):
            _close(getattr(result, field), expected_step[field])
        _close(result.carried_state.m, expected_step["state_m_after_observation"])
        _close(result.carried_state.P, expected_step["state_P_after_observation"])
        assert result.interval_calibration_type == expected_step["calibration_type"]
        assert result.interval_calibration_source == expected_step["calibration_source"]
        assert result.model_id == "P1a-C"
        assert result.model_version == expected["model_version"]
