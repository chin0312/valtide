from __future__ import annotations

import hashlib
import json
from pathlib import Path


QUANT = Path(__file__).resolve().parents[1]
OUT = QUANT / "HANDOFF_MANIFEST.json"


VERDICTS = [
    {"candidate": "Raw xStock baseline", "verdict": "DEPLOYMENT_CANDIDATE", "differentiation": "NEITHER"},
    {"candidate": "P1a", "verdict": "DEPLOYMENT_CANDIDATE", "differentiation": "REFERENCE_RELIABILITY"},
    {"candidate": "P1a-C", "verdict": "DEPLOYMENT_CANDIDATE", "differentiation": "REFERENCE_RELIABILITY"},
    {"candidate": "Raw-xStock-C", "verdict": "RESEARCH_ONLY", "differentiation": "NEITHER"},
    {"candidate": "Challenger tail detector", "verdict": "RESEARCH_ONLY", "differentiation": "REFERENCE_RELIABILITY"},
    {"candidate": "Lag-vs-dislocation gate", "verdict": "REJECTED", "differentiation": "REFERENCE_RELIABILITY"},
    {"candidate": "P1m momentum model", "verdict": "REJECTED", "differentiation": "PRICE_CORRECTION"},
    {"candidate": "P1m-C", "verdict": "REJECTED", "differentiation": "PRICE_CORRECTION"},
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(prefix: str) -> list[dict]:
    root = QUANT / prefix
    return [
        {
            "path": path.relative_to(QUANT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != OUT and "__pycache__" not in path.parts
    ]


def main() -> None:
    datasets = json.loads((QUANT / "data_manifest" / "datasets_manifest.json").read_text())
    manifest = {
        "schema_version": 1,
        "handoff_version": "1.0.0",
        "generated_date": "2026-10-05",
        "runtime_scope": "NVDAx P1a-C challenger and calibrated uncertainty only",
        "runtime_artifacts": records("runtime"),
        "research_artifacts": records("research"),
        "rejected_artifacts": [
            row for row in records("research/rejected_experiments")
        ],
        "raw_data_manifest_files": records("data_manifest"),
        "model_verdicts": VERDICTS,
        "model_versions": {"P1a-C": "0.2.0", "handoff": "1.0.0"},
        "dataset_hashes": {
            row["asset_id"]: row["dataset_sha256"] for row in datasets
        },
        "notes": [
            "The current test periods have been inspected repeatedly and are development evidence.",
            "Raw/canonical datasets are excluded from Git; storage locations remain explicit placeholders.",
            "Original source/result files were not deleted.",
        ],
    }
    OUT.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
