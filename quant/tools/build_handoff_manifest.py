from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

QUANT = Path(__file__).resolve().parents[1]
REPOSITORY = QUANT.parent
OUT = QUANT / "HANDOFF_MANIFEST.json"


VERDICTS = [
    {
        "candidate": "Raw xStock baseline",
        "verdict": "DEPLOYMENT_CANDIDATE",
        "differentiation": "NEITHER",
    },
    {
        "candidate": "P1a",
        "verdict": "DEPLOYMENT_CANDIDATE",
        "differentiation": "REFERENCE_RELIABILITY",
    },
    {
        "candidate": "P1a-C",
        "verdict": "DEPLOYMENT_CANDIDATE",
        "differentiation": "REFERENCE_RELIABILITY",
    },
    {
        "candidate": "Raw-xStock-C",
        "verdict": "RESEARCH_ONLY",
        "differentiation": "NEITHER",
    },
    {
        "candidate": "Challenger tail detector",
        "verdict": "RESEARCH_ONLY",
        "differentiation": "REFERENCE_RELIABILITY",
    },
    {
        "candidate": "Lag-vs-dislocation gate",
        "verdict": "REJECTED",
        "differentiation": "REFERENCE_RELIABILITY",
    },
    {
        "candidate": "P1m momentum model",
        "verdict": "REJECTED",
        "differentiation": "PRICE_CORRECTION",
    },
    {
        "candidate": "P1m-C",
        "verdict": "REJECTED",
        "differentiation": "PRICE_CORRECTION",
    },
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(prefix: str) -> list[dict]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", f"quant/{prefix}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    paths = [REPOSITORY / item.decode() for item in tracked if item]
    return [
        {
            "path": path.relative_to(QUANT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(paths, key=lambda item: item.relative_to(QUANT).as_posix())
        if path.is_file()
        and path != OUT
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]


def render_manifest() -> bytes:
    datasets = json.loads(
        (QUANT / "data_manifest" / "datasets_manifest.json").read_text()
    )
    manifest = {
        "schema_version": 1,
        "handoff_version": "1.0.0",
        "generated_date": "2026-10-05",
        "runtime_scope": "NVDAx P1a-C challenger and calibrated uncertainty only",
        "runtime_artifacts": records("runtime"),
        "research_artifacts": records("research"),
        "rejected_artifacts": [row for row in records("research/rejected_experiments")],
        "raw_data_manifest_files": records("data_manifest"),
        "model_verdicts": VERDICTS,
        "model_versions": {"P1a-C": "0.2.0", "handoff": "1.0.0"},
        "dataset_hashes": {row["asset_id"]: row["dataset_sha256"] for row in datasets},
        "notes": [
            "The current test periods have been inspected repeatedly and are development evidence.",
            "Raw/canonical datasets are excluded from Git; storage locations remain explicit placeholders.",
            "Original source/result files were not deleted.",
            "Manifest file records cover Git-tracked handoff files only; rejected artifacts may also be referenced in research_artifacts.",
        ],
    }
    return (json.dumps(manifest, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build or check the quant handoff manifest"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed manifest differs from a fresh deterministic rendering",
    )
    args = parser.parse_args()
    rendered = render_manifest()
    if args.check:
        if not OUT.exists() or OUT.read_bytes() != rendered:
            raise SystemExit(
                "HANDOFF_MANIFEST.json is not current; run "
                "python quant/tools/build_handoff_manifest.py"
            )
        print("HANDOFF_MANIFEST.json matches deterministic tracked-file rendering")
        return
    OUT.write_bytes(rendered)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
