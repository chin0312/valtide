from __future__ import annotations

import csv
import argparse
import io
import json
from pathlib import Path


RESEARCH = Path(__file__).resolve().parents[1]
BENCHMARK = RESEARCH / "benchmarks" / "p1ac_vs_rawc"
CHALLENGER = RESEARCH / "challenger" / "results" / "cross_asset_report.json"
OUT_CSV = RESEARCH / "benchmarks" / "five_asset_metrics.csv"
OUT_JSON = RESEARCH / "benchmarks" / "RESEARCH_METRICS.json"
OUT_MD = RESEARCH / "benchmarks" / "RESEARCH_METRICS.md"


def load_metrics() -> list[dict]:
    challenger = json.loads(CHALLENGER.read_text())
    challenger_by_asset = {row["asset"].lower(): row for row in challenger["per_asset"]}
    rows = []
    for report_path in sorted(BENCHMARK.glob("*/p1ac_vs_rawc_report.json")):
        report = json.loads(report_path.read_text())
        asset = report["asset_id"]
        point = report["point_estimate_comparison"][0]
        p1ac, rawc = report["primary_interval_comparison"]
        if not p1ac["candidate"].startswith("P1a-C"):
            p1ac, rawc = rawc, p1ac
        tail = challenger_by_asset[asset.lower()]
        rows.append(
            {
                "asset": asset,
                "dataset_sha256": report["dataset_sha256"],
                "raw_mae_bps": point["Raw_xStock_MAE_bps"],
                "p1a_mae_bps": point["P1a_MAE_bps"],
                "raw_rmse_bps": point["Raw_xStock_RMSE_bps"],
                "p1a_rmse_bps": point["P1a_RMSE_bps"],
                "p1ac_coverage": p1ac["coverage"],
                "p1ac_width_bps": p1ac["mean_width_bps"],
                "p1ac_interval_score_bps": p1ac["mean_interval_score_bps"],
                "rawc_coverage": rawc["coverage"],
                "rawc_width_bps": rawc["mean_width_bps"],
                "rawc_interval_score_bps": rawc["mean_interval_score_bps"],
                "review_to_support_raw_error_ratio": tail[
                    "review_to_support_raw_error_ratio"
                ],
                "tail_auroc": tail["test_relative_tail_auroc"],
                "tail_average_precision": tail["test_relative_tail_average_precision"],
            }
        )
    return rows


def render_outputs() -> dict[Path, bytes]:
    rows = load_metrics()
    json_bytes = (json.dumps({"assets": rows}, indent=2) + "\n").encode("utf-8")
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    lines = [
        "# Generated research metrics",
        "",
        "Generated from the checked-in JSON result reports; do not edit manually.",
        "",
        "| Asset | Raw MAE | P1a MAE | P1a-C score | Raw-C score | REVIEW/SUPPORT raw error |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['asset']} | {row['raw_mae_bps']:.2f} | {row['p1a_mae_bps']:.2f} | "
            f"{row['p1ac_interval_score_bps']:.1f} | {row['rawc_interval_score_bps']:.1f} | "
            f"{row['review_to_support_raw_error_ratio']:.1f}x |"
        )
    return {
        OUT_CSV: csv_buffer.getvalue().encode("utf-8"),
        OUT_JSON: json_bytes,
        OUT_MD: ("\n".join(lines) + "\n").encode("utf-8"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate or verify compact research metrics"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated metrics match checked-in source result reports without writing files",
    )
    args = parser.parse_args()
    outputs = render_outputs()
    if args.check:
        mismatches = [
            str(path.relative_to(RESEARCH))
            for path, expected in outputs.items()
            if not path.exists() or path.read_bytes() != expected
        ]
        if mismatches:
            raise SystemExit(
                "generated research metrics are stale: " + ", ".join(mismatches)
            )
        print("generated research metrics match checked-in result reports")
        return
    for path, contents in outputs.items():
        path.write_bytes(contents)
    print(f"wrote {OUT_CSV}, {OUT_JSON}, and {OUT_MD}")


if __name__ == "__main__":
    main()
