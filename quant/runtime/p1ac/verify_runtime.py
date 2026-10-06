from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]


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

    provenance = json.loads((root / "metadata" / "provenance.json").read_text())
    if provenance["deployment_model_id"] != binding["deployment_model_id"]:
        raise ValueError("provenance model ID does not match runtime binding")
    if provenance["model_version"] != binding["model_version"]:
        raise ValueError("provenance model version does not match runtime binding")
    if provenance["training_end_utc"] != binding["training_end_utc"]:
        raise ValueError("training chronology differs between provenance records")
    if (
        provenance["calibration_generated_at_utc"]
        != binding["calibration_generated_at_utc"]
    ):
        raise ValueError("calibration chronology differs between provenance records")
    training_end = dt.datetime.fromisoformat(
        binding["training_end_utc"].replace("Z", "+00:00")
    )
    calibration_time = dt.datetime.fromisoformat(
        binding["calibration_generated_at_utc"].replace(" UTC", "+00:00")
    )
    if calibration_time <= training_end:
        raise ValueError("calibration timestamp must be later than training end")
    if (
        provenance["artifact_sha256"].get("p1a_runtime.json")
        != binding["parameter_sha256"]
    ):
        raise ValueError("parameter hash differs between provenance records")
    if (
        provenance["artifact_sha256"].get("p1a_c_calibrator.json")
        != binding["calibration_sha256"]
    ):
        raise ValueError("calibration hash differs between provenance records")

    embedded = root / "code" / "src" / "valtide_quant_service" / "model_artifacts"
    if parameter.read_bytes() != (embedded / "p1a_runtime.json").read_bytes():
        raise ValueError("embedded parameter artifact differs from canonical copy")
    if calibrator.read_bytes() != (embedded / "p1a_c_calibrator.json").read_bytes():
        raise ValueError("embedded calibration artifact differs from canonical copy")

    production_package = (
        REPOSITORY / "valtide-quant-service-p1ac" / "src" / "valtide_quant_service"
    )
    snapshot_package = root / "code" / "src" / "valtide_quant_service"
    production_files = {
        path.relative_to(production_package).as_posix(): path
        for path in production_package.rglob("*")
        if path.is_file() and path.suffix == ".py" and "__pycache__" not in path.parts
    }
    snapshot_files = {
        path.relative_to(snapshot_package).as_posix(): path
        for path in snapshot_package.rglob("*")
        if path.is_file() and path.suffix == ".py" and "__pycache__" not in path.parts
    }
    if production_files.keys() != snapshot_files.keys():
        raise ValueError(
            "runtime Python source snapshot file set differs from production package"
        )
    for relative_path, production_path in production_files.items():
        if production_path.read_bytes() != snapshot_files[relative_path].read_bytes():
            raise ValueError(
                f"runtime source snapshot differs from production package: {relative_path}"
            )

    production_artifacts = REPOSITORY / "valtide-quant-service-p1ac" / "artifacts"
    if (
        parameter.read_bytes()
        != (production_artifacts / "p1a_runtime.json").read_bytes()
    ):
        raise ValueError("handoff parameters differ from production package artifact")
    if (
        calibrator.read_bytes()
        != (production_artifacts / "p1a_c_calibrator.json").read_bytes()
    ):
        raise ValueError("handoff calibrator differs from production package artifact")
    if (root / "metadata" / "provenance.json").read_bytes() != (
        production_artifacts / "provenance.json"
    ).read_bytes():
        raise ValueError("handoff provenance differs from production package metadata")
    return binding


def main() -> None:
    binding = json.loads((ROOT / "metadata" / "runtime_binding.json").read_text())
    parser = argparse.ArgumentParser(
        description="Verify the frozen P1a-C runtime bundle"
    )
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
