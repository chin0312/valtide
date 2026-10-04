from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verify_runtime import validate_runtime_binding


DATASET_SHA256 = "722929383e6ca1aa28382e828879efeccb60faabdf2bd5e05f14a721f7fc740d"


def test_runtime_binding_accepts_exact_asset_and_dataset() -> None:
    binding = validate_runtime_binding("NVDAx", DATASET_SHA256)
    assert binding["deployment_model_id"] == "P1a-C"
    assert binding["calibration_method"] == "session_sym"


def test_asset_mismatch_is_rejected() -> None:
    try:
        validate_runtime_binding("TSLAx", DATASET_SHA256)
    except ValueError as exc:
        assert "asset mismatch" in str(exc)
    else:
        raise AssertionError("asset mismatch was accepted")


def test_dataset_mismatch_is_rejected() -> None:
    try:
        validate_runtime_binding("NVDAx", "0" * 64)
    except ValueError as exc:
        assert "dataset mismatch" in str(exc)
    else:
        raise AssertionError("dataset mismatch was accepted")


def test_required_runtime_metadata_is_present() -> None:
    binding = json.loads((ROOT / "metadata" / "runtime_binding.json").read_text())
    required = {
        "asset_id",
        "dataset_sha256",
        "model_version",
        "training_end_utc",
        "calibration_generated_at_utc",
        "calibration_method",
        "parameter_sha256",
        "calibration_sha256",
    }
    assert required <= set(binding)
