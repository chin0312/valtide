from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def canonical_text_sha256(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def validate_runtime_binding(
    expected_asset: str,
    expected_dataset_sha256: str,
    root: Path = ROOT,
) -> dict:
    binding = json.loads((root / "metadata" / "runtime_binding.json").read_text())
    if binding["asset_id"] != expected_asset:
        raise ValueError(
            f"asset mismatch: expected {expected_asset}, artifact is {binding['asset_id']}"
        )
    if binding["dataset_sha256"] != expected_dataset_sha256:
        raise ValueError("dataset mismatch")

    parameter = root / "params" / "p1a_runtime.json"
    calibrator = root / "calibration" / "p1a_c_calibrator.json"
    if canonical_text_sha256(parameter) != binding["parameter_sha256"]:
        raise ValueError("parameter hash mismatch")
    if canonical_text_sha256(calibrator) != binding["calibration_sha256"]:
        raise ValueError("calibration hash mismatch")

    runtime = json.loads(parameter.read_text())
    if runtime["asset"] != binding["asset_id"]:
        raise ValueError("runtime asset does not match binding")
    if runtime["model_version"] != binding["model_version"]:
        raise ValueError("runtime model version does not match binding")

    embedded = root / "code" / "src" / "valtide_quant_service" / "model_artifacts"
    if parameter.read_bytes() != (embedded / "p1a_runtime.json").read_bytes():
        raise ValueError("embedded parameter artifact differs from canonical copy")
    if calibrator.read_bytes() != (embedded / "p1a_c_calibrator.json").read_bytes():
        raise ValueError("embedded calibration artifact differs from canonical copy")
    return binding


def main() -> None:
    binding = json.loads((ROOT / "metadata" / "runtime_binding.json").read_text())
    parser = argparse.ArgumentParser(description="Verify the frozen P1a-C runtime bundle")
    parser.add_argument("--asset", default=binding["asset_id"])
    parser.add_argument("--dataset-sha256", default=binding["dataset_sha256"])
    args = parser.parse_args()
    validated = validate_runtime_binding(args.asset, args.dataset_sha256)
    print(
        "verified "
        f"{validated['deployment_model_id']} {validated['model_version']} "
        f"for {validated['asset_id']} dataset {validated['dataset_sha256']}"
    )


if __name__ == "__main__":
    main()
