"""Create a canonical X Layer three-asset manifest from verified receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from valtide_api.xlayer_manifest import build_multi_asset_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=REPO_ROOT / "deployments" / "xlayer-testnet.json",
        help="current manifest containing the verified legacy NVDA binding",
    )
    parser.add_argument("--receipt", type=Path, required=True, help="verified receipt JSON")
    parser.add_argument("--output", type=Path, required=True, help="new manifest output path")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        parser.error("output exists; pass --force to replace it")
    try:
        base = json.loads(args.base.read_text(encoding="utf-8"))
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        manifest = build_multi_asset_manifest(base, receipt)
        args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"canonical three-asset manifest written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
