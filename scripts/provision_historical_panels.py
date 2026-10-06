"""Verify and atomically provision an approved canonical panel without overwrite.

This utility does not fetch data. Run it in the target environment after the
source bytes have been transferred there, or use it locally to validate a
candidate before upload. The manifest binds asset, Solana deployment, sources,
reference identity, row window, and SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

resolve_asset_config = import_module("valtide_api.assets").resolve_asset_config
Settings = import_module("valtide_api.config").Settings
inspect_panel_readiness = import_module("valtide_api.panel").inspect_panel_readiness
resolve_quant_runtime = import_module("valtide_api.quant_runtime").resolve_quant_runtime

DEFAULT_MANIFEST = ROOT / "data" / "manifests" / "production_historical_panels.json"
_ASSETS = ("NVDAx", "SPYx", "QQQx", "AAPLx")


class PanelProvisioningError(ValueError):
    """Raised when a source panel cannot be safely installed."""


@dataclass(frozen=True)
class PanelVerification:
    asset: str
    sha256: str
    rows: int
    window_start_utc: str
    window_end_utc: str
    persistent_path: str


def load_manifest(path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PanelProvisioningError("panel manifest is unreadable") from exc
    if not isinstance(manifest, dict):
        raise PanelProvisioningError("panel manifest root must be an object")
    if manifest.get("manifest_version") != 1 or manifest.get("panel_schema") != "canonical":
        raise PanelProvisioningError("unsupported panel manifest version or schema")
    generation = manifest.get("generation")
    if not isinstance(generation, str) or not generation.isdecimal():
        raise PanelProvisioningError("panel manifest generation is invalid")
    assets = manifest.get("assets")
    if not isinstance(assets, dict) or tuple(assets) != _ASSETS:
        raise PanelProvisioningError("panel manifest asset set/order is invalid")
    for asset in _ASSETS:
        if not isinstance(assets[asset], dict):
            raise PanelProvisioningError(f"panel manifest entry is invalid for {asset}")
        expected_path = (
            Path("/data/historical/panels")
            / generation
            / f"{asset.lower()}_historical_5m.csv"
        )
        if assets[asset].get("persistent_path") != str(expected_path):
            raise PanelProvisioningError(f"manifest path is invalid for {asset}")
    return manifest


def _settings_for(expected: dict[str, Any]) -> Settings:
    # NVDA's legacy environment names remain the explicit offline pin boundary.
    # These public identities are verified against AssetConfig before scanning.
    return Settings(
        _env_file=None,
        okx_nvdax_chain_index=str(expected["chain_index"]),
        okx_nvdax_token_address=str(expected["token_address"]),
    )


def _validate_expected_identity(asset: str, expected: dict[str, Any]) -> None:
    try:
        config = resolve_asset_config(asset, _settings_for(expected))
    except (KeyError, TypeError, ValueError) as exc:
        raise PanelProvisioningError("asset configuration does not match manifest") from exc

    actual_identity = {
        "asset": config.asset,
        "token_source": config.token_source,
        "chain_index": config.okx_chain_index,
        "token_address": config.token_address,
        "underlying_source": config.underlying_source,
        "underlying_symbol": config.underlying_symbol,
        "reference_source": config.reference_under_test_source,
        "reference_instrument": config.reference_under_test_instrument,
        "reference_profile": config.reference_profile,
    }
    for field, value in actual_identity.items():
        if expected.get(field) != value:
            raise PanelProvisioningError(f"manifest {field} does not match registered asset")
    try:
        runtime = resolve_quant_runtime(config)
    except (KeyError, TypeError, ValueError) as exc:
        raise PanelProvisioningError("registered quant runtime is unavailable") from exc
    if expected.get("model_id") != runtime.model_id:
        raise PanelProvisioningError("manifest model_id does not match registered quant runtime")
    if expected.get("model_version") != runtime.model_version:
        raise PanelProvisioningError(
            "manifest model_version does not match registered quant runtime"
        )

    persistent_path = Path(str(expected.get("persistent_path", "")))
    if not persistent_path.is_absolute():
        raise PanelProvisioningError("manifest persistent path is invalid")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_panel(
    source: str | Path,
    *,
    asset: str,
    expected: dict[str, Any],
) -> PanelVerification:
    """Validate bytes and complete panel identity using the production loader."""
    if asset not in _ASSETS or expected.get("asset") != asset:
        raise PanelProvisioningError("requested asset does not match panel manifest")
    try:
        _validate_expected_identity(asset, expected)
    except KeyError as exc:
        raise PanelProvisioningError("panel manifest identity is incomplete") from exc
    path = Path(source).resolve(strict=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise PanelProvisioningError("source panel is missing or empty")

    expected_sha = str(expected.get("sha256", ""))
    if len(expected_sha) != 64 or any(ch not in "0123456789abcdef" for ch in expected_sha):
        raise PanelProvisioningError("manifest SHA-256 is invalid")
    digest = _sha256(path)
    if digest != expected_sha:
        raise PanelProvisioningError("source panel SHA-256 does not match manifest")

    readiness = inspect_panel_readiness(path, asset=asset, settings=_settings_for(expected))
    if not readiness.file_available or not readiness.canonical_identity_verified:
        raise PanelProvisioningError(
            f"source panel identity is invalid ({readiness.error_code or 'UNKNOWN'})"
        )
    if not readiness.replay_compatible or readiness.schema != "canonical":
        raise PanelProvisioningError(
            f"source panel is not canonical replay-ready ({readiness.error_code or 'UNKNOWN'})"
        )

    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError) as exc:
        raise PanelProvisioningError("source panel could not be parsed") from exc
    if not rows or len(rows) != expected.get("rows"):
        raise PanelProvisioningError("source panel row count does not match manifest")
    first = rows[0].get("timestamp_utc", "")
    last = rows[-1].get("timestamp_utc", "")
    if first != expected.get("window_start_utc") or last != expected.get("window_end_utc"):
        raise PanelProvisioningError("source panel time window does not match manifest")

    return PanelVerification(
        asset=asset,
        sha256=digest,
        rows=len(rows),
        window_start_utc=first,
        window_end_utc=last,
        persistent_path=str(expected["persistent_path"]),
    )


def provision_panel(
    source: str | Path,
    destination: str | Path,
    *,
    asset: str,
    expected: dict[str, Any],
) -> PanelVerification:
    """Install exact approved bytes atomically; refuse any different existing file."""
    source_path = Path(source).resolve(strict=True)
    destination_path = Path(destination)
    verification = verify_panel(source_path, asset=asset, expected=expected)
    if str(destination_path) != verification.persistent_path:
        raise PanelProvisioningError("destination does not match the manifest persistent path")

    if destination_path.exists():
        existing_sha = _sha256(destination_path)
        if existing_sha != verification.sha256:
            raise PanelProvisioningError(
                "destination already contains different bytes; refusing to overwrite"
            )
        verify_panel(destination_path, asset=asset, expected=expected)
        return verification

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination_path.name}.", suffix=".tmp",
            dir=destination_path.parent, delete=False,
        ) as staged:
            temp_path = Path(staged.name)
            with source_path.open("rb") as original:
                shutil.copyfileobj(original, staged, length=1024 * 1024)
            staged.flush()
            os.fsync(staged.fileno())

        verify_panel(temp_path, asset=asset, expected=expected)
        try:
            # A hard link gives create-if-absent semantics on the destination
            # filesystem, avoiding a race that could overwrite an existing file.
            os.link(temp_path, destination_path)
        except FileExistsError as exc:
            raise PanelProvisioningError(
                "destination appeared during provisioning; refusing to overwrite"
            ) from exc
        directory_fd = os.open(destination_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        verify_panel(destination_path, asset=asset, expected=expected)
        return verification
    except OSError as exc:
        raise PanelProvisioningError("atomic panel provisioning failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", required=True, choices=_ASSETS)
    parser.add_argument("--source", required=True, help="Transferred source panel on this host")
    parser.add_argument("--destination", help="Must equal the manifest /data path")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        expected = manifest["assets"][args.asset]
        destination = args.destination or expected["persistent_path"]
        result = provision_panel(args.source, destination, asset=args.asset, expected=expected)
    except (PanelProvisioningError, OSError) as exc:
        print(f"panel provisioning failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
