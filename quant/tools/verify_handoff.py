from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

from build_handoff_manifest import OUT, QUANT, REPOSITORY, render_manifest


REFERENCE_SECTIONS = (
    "runtime_artifacts",
    "research_artifacts",
    "rejected_artifacts",
    "raw_data_manifest_files",
)
EXPECTED_ASSETS = {"AAPLX", "NVDAX", "QQQX", "SPYX", "TSLAX"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_int(value: object, field: str, asset: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{asset}: {field} is not an integer") from exc


def tracked_quant_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "quant"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    return {part.decode() for part in result.stdout.split(b"\0") if part}


def verify_source_exclusions() -> None:
    forbidden_tokens = (
        "canonical_panel_5m.csv",
        "/data/raw/",
        "/data/processed/",
        "/exports/",
        "/okx_http_raw/",
        "/.renviron",
        "/.env",
    )
    forbidden_suffixes = (".rds", ".pkl", ".joblib", ".tar.gz", ".zip")
    forbidden = [
        path
        for path in tracked_quant_paths()
        if any(token in path.lower() for token in forbidden_tokens)
        or path.lower().endswith(forbidden_suffixes)
    ]
    require(
        not forbidden, f"raw/local-only material is tracked under quant/: {forbidden}"
    )


def verify_manifest_files(manifest: dict) -> tuple[int, int]:
    references: dict[str, list[str]] = defaultdict(list)
    for section in REFERENCE_SECTIONS:
        records = manifest.get(section)
        require(isinstance(records, list), f"{section} must be a list")
        section_paths: set[str] = set()
        for record in records:
            relative = record.get("path")
            require(isinstance(relative, str), f"{section} record has no path")
            pure = PurePosixPath(relative)
            require(
                not pure.is_absolute()
                and ".." not in pure.parts
                and "\\" not in relative,
                f"unsafe manifest path: {relative}",
            )
            require(
                relative not in section_paths,
                f"duplicate path within {section}: {relative}",
            )
            section_paths.add(relative)
            path = QUANT / relative
            require(
                path.resolve().is_relative_to(QUANT.resolve()),
                f"path escapes quant/: {relative}",
            )
            require(path.is_file(), f"manifest file missing: {relative}")
            require(
                path.stat().st_size == record.get("bytes"),
                f"byte-count mismatch: {relative}",
            )
            require(
                sha256(path) == record.get("sha256"), f"SHA-256 mismatch: {relative}"
            )
            references[relative].append(section)

    for path, sections in references.items():
        if len(sections) > 1:
            require(
                set(sections) == {"research_artifacts", "rejected_artifacts"},
                f"unexpected repeated manifest reference for {path}: {sections}",
            )
    return len(set(references)), sum(map(len, references.values()))


def verify_dataset_identity(manifest: dict) -> int:
    json_path = QUANT / "data_manifest" / "datasets_manifest.json"
    csv_path = QUANT / "data_manifest" / "datasets_manifest.csv"
    json_rows = json.loads(json_path.read_text())
    with csv_path.open(newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    by_asset = {str(row["asset_id"]).upper(): row for row in json_rows}
    csv_by_asset = {str(row["asset_id"]).upper(): row for row in csv_rows}
    require(set(by_asset) == EXPECTED_ASSETS, "JSON dataset manifest asset set changed")
    require(
        set(csv_by_asset) == EXPECTED_ASSETS, "CSV dataset manifest asset set changed"
    )

    inventory_hashes: dict[str, str] = {}
    for asset_key, row in by_asset.items():
        asset = str(row["asset_id"])
        slug = asset.lower()
        csv_row = csv_by_asset[asset_key]
        for field in (
            "xstock_symbol",
            "underlying_symbol",
            "chain_index",
            "token_address",
            "start_timestamp",
            "end_timestamp",
            "row_count_5m",
            "underlying_observation_count",
            "token_observation_count",
            "overlap_count",
            "token_only_count",
            "weekend_token_observation_count",
            "dataset_sha256",
            "canonical_file_sha256",
            "metadata_sha256",
            "storage_location",
        ):
            require(
                str(row[field]) == str(csv_row[field]),
                f"{asset}: JSON/CSV mismatch in {field}",
            )

        require(
            row["xstock_symbol"].upper() == asset_key,
            f"{asset}: xStock identity mismatch",
        )
        require(
            as_int(row["chain_index"], "chain_index", asset) == 501,
            f"{asset}: expected Solana chainIndex 501",
        )
        require(row["chain_name"] == "Solana", f"{asset}: chain name is not Solana")
        require(bool(row["token_address"]), f"{asset}: token address is empty")
        require(
            row["dataset_sha256"] == row["canonical_file_sha256"],
            f"{asset}: dataset/canonical hashes differ",
        )
        require(
            str(row["storage_location"]).startswith("TBD_SHARED_STORAGE/"),
            f"{asset}: unexpected storage URI",
        )

        metadata_path = (
            QUANT / "data_manifest" / "asset_metadata" / slug / "asset_metadata.json"
        )
        metadata = json.loads(metadata_path.read_text())
        require(
            str(metadata["asset_id"]).upper() == asset_key,
            f"{asset}: asset metadata identity mismatch",
        )
        require(
            str(metadata["xstock_symbol"]).upper() == asset_key,
            f"{asset}: metadata xStock symbol mismatch",
        )
        require(
            str(metadata["underlying_symbol"]).upper()
            == str(row["underlying_symbol"]).upper(),
            f"{asset}: underlying mismatch",
        )
        require(
            metadata["xstock_network"] == "Solana",
            f"{asset}: metadata network mismatch",
        )
        require(
            metadata["data_start_utc"] == row["start_timestamp"],
            f"{asset}: start timestamp mismatch",
        )
        require(
            metadata["data_end_utc"] == row["end_timestamp"],
            f"{asset}: end timestamp mismatch",
        )
        require(
            as_int(metadata["rows"], "rows", asset)
            == as_int(row["row_count_5m"], "row_count_5m", asset),
            f"{asset}: row count mismatch",
        )
        require(
            as_int(metadata["overlap_rows"], "overlap_rows", asset)
            == as_int(row["overlap_count"], "overlap_count", asset),
            f"{asset}: overlap count mismatch",
        )
        deployment = metadata.get("okx_deployment") or {}
        require(
            as_int(deployment.get("chainIndex"), "metadata chainIndex", asset) == 501,
            f"{asset}: metadata chainIndex mismatch",
        )
        require(
            deployment.get("tokenContractAddress") == row["token_address"],
            f"{asset}: metadata token address mismatch",
        )
        require(
            deployment.get("selectedNetwork") == "Solana",
            f"{asset}: selected network mismatch",
        )
        require(
            metadata["dataset_sha256"] == row["dataset_sha256"],
            f"{asset}: metadata dataset hash mismatch",
        )
        require(
            sha256(metadata_path) == row["metadata_sha256"],
            f"{asset}: metadata file SHA-256 mismatch",
        )

        sidecar = metadata_path.with_name("dataset.sha256").read_text().strip()
        require(
            sidecar == row["dataset_sha256"],
            f"{asset}: dataset.sha256 sidecar mismatch",
        )
        audit_path = metadata_path.with_name("data_audit.csv")
        with audit_path.open(newline="") as handle:
            audit = {
                entry["metric"]: entry["value"] for entry in csv.DictReader(handle)
            }
        audit_fields = {
            "rows_5m": "row_count_5m",
            "underlying_observations": "underlying_observation_count",
            "token_observations": "token_observation_count",
            "overlap_observations": "overlap_count",
            "token_only_observations": "token_only_count",
            "weekend_token_observations": "weekend_token_observation_count",
        }
        for audit_field, manifest_field in audit_fields.items():
            require(
                as_int(audit.get(audit_field), audit_field, asset)
                == as_int(row[manifest_field], manifest_field, asset),
                f"{asset}: data-audit mismatch in {audit_field}",
            )
        inventory_hashes[asset] = row["dataset_sha256"]

    require(
        manifest["dataset_hashes"] == inventory_hashes,
        "HANDOFF manifest dataset hashes differ from dataset inventory",
    )
    runtime_binding = json.loads(
        (QUANT / "runtime" / "p1ac" / "metadata" / "runtime_binding.json").read_text()
    )
    require(
        runtime_binding["dataset_sha256"] == inventory_hashes["NVDAx"],
        "NVDAx runtime binding differs from dataset inventory",
    )

    metrics_path = QUANT / "research" / "benchmarks" / "RESEARCH_METRICS.json"
    metrics = json.loads(metrics_path.read_text())["assets"]
    require(
        {row["asset"].upper() for row in metrics} == EXPECTED_ASSETS,
        "research metric asset set differs from dataset inventory",
    )
    for row in metrics:
        canonical_asset = by_asset[row["asset"].upper()]["asset_id"]
        require(
            row["dataset_sha256"] == inventory_hashes[canonical_asset],
            f"{row['asset']}: research metric dataset hash mismatch",
        )
    for report_path in sorted(
        (QUANT / "research" / "benchmarks" / "p1ac_vs_rawc").glob(
            "*/p1ac_vs_rawc_report.json"
        )
    ):
        report = json.loads(report_path.read_text())
        asset_key = report["asset_id"].upper()
        require(
            asset_key in by_asset, f"unexpected benchmark report asset: {asset_key}"
        )
        canonical_asset = by_asset[asset_key]["asset_id"]
        require(
            report["dataset_sha256"] == inventory_hashes[canonical_asset],
            f"{asset_key}: benchmark report dataset hash mismatch",
        )
    return len(inventory_hashes)


def main() -> None:
    first_render = render_manifest()
    second_render = render_manifest()
    require(first_render == second_render, "manifest rendering is not deterministic")
    require(
        OUT.read_bytes() == first_render,
        "HANDOFF_MANIFEST differs from deterministic Git-tracked rendering",
    )
    manifest = json.loads(OUT.read_text())
    unique_files, reference_count = verify_manifest_files(manifest)
    dataset_count = verify_dataset_identity(manifest)
    verify_source_exclusions()
    print(
        "handoff verified: "
        f"{unique_files} distinct files across {reference_count} manifest references; "
        f"{dataset_count} dataset identities consistent; "
        "canonical source-panel bytes are external and were not recomputed"
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(
            f"handoff verification failed: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        raise SystemExit(1) from exc
