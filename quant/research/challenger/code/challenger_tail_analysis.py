#!/usr/bin/env python3
"""
Valtide challenger-tail analysis.

Purpose
-------
Test the challenger-model hypothesis directly:
    When P1a materially disagrees with raw xStock, does that disagreement
    identify observations where the raw xStock is unusually far from the
    hidden contemporaneous underlying price?

This script DOES NOT refit P1a and DOES NOT call any market-data API.
It consumes the leakage-safe outputs already produced by run_p1ac_vs_rawc.R:
  - crossfit_scores.csv            (OOF training/calibration observations)
  - test_primary_intervals.csv     (untouched chronological test observations)

The hidden underlying price is used only AFTER scores/statuses are formed,
for evaluation of actual raw-xStock error.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


def finite(x: float) -> bool:
    return isinstance(x, float) and math.isfinite(x)


def as_float(value) -> float:
    if value is None:
        return float("nan")
    s = str(value).strip()
    if not s or s.upper() in {"NA", "NAN", "NULL", "NONE"}:
        return float("nan")
    try:
        x = float(s)
    except ValueError:
        return float("nan")
    return x if math.isfinite(x) else float("nan")


def quantile(values: Sequence[float], p: float) -> float:
    xs = sorted(x for x in values if finite(x))
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    if p <= 0:
        return xs[0]
    if p >= 1:
        return xs[-1]
    # R type=7 / NumPy-style linear interpolation.
    h = (len(xs) - 1) * p
    lo = int(math.floor(h))
    hi = int(math.ceil(h))
    if lo == hi:
        return xs[lo]
    w = h - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def mean(values: Sequence[float]) -> float:
    xs = [x for x in values if finite(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def rmse(values: Sequence[float]) -> float:
    xs = [x for x in values if finite(x)]
    return math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else float("nan")


def rate(values: Sequence[bool]) -> float:
    return sum(1 for x in values if x) / len(values) if values else float("nan")


def average_ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        v = values[order[i]]
        while j < len(order) and values[order[j]] == v:
            j += 1
        # 1-based average rank.
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    pairs = [(a, b) for a, b in zip(x, y) if finite(a) and finite(b)]
    if len(pairs) < 2:
        return float("nan")
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = mean(xs), mean(ys)
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx <= 0 or vy <= 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in pairs) / math.sqrt(vx * vy)


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    pairs = [(a, b) for a, b in zip(x, y) if finite(a) and finite(b)]
    if len(pairs) < 2:
        return float("nan")
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    return pearson(average_ranks(xs), average_ranks(ys))


def auroc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    pairs = [(s, bool(y)) for s, y in zip(scores, labels) if finite(s)]
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    vals = [s for s, _ in pairs]
    ranks = average_ranks(vals)
    rank_sum_pos = sum(r for r, (_, y) in zip(ranks, pairs) if y)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def average_precision(scores: Sequence[float], labels: Sequence[bool]) -> float:
    pairs = sorted(
        [(s, bool(y)) for s, y in zip(scores, labels) if finite(s)],
        key=lambda z: z[0],
        reverse=True,
    )
    total_pos = sum(1 for _, y in pairs if y)
    if total_pos == 0:
        return float("nan")
    tp = 0
    ap_sum = 0.0
    for i, (_, y) in enumerate(pairs, start=1):
        if y:
            tp += 1
            ap_sum += tp / i
    return ap_sum / total_pos


def confusion(flagged: Sequence[bool], event: Sequence[bool]) -> Dict[str, float]:
    tp = sum(1 for f, e in zip(flagged, event) if f and e)
    fp = sum(1 for f, e in zip(flagged, event) if f and not e)
    fn = sum(1 for f, e in zip(flagged, event) if not f and e)
    tn = sum(1 for f, e in zip(flagged, event) if not f and not e)
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    fpr = fp / (fp + tn) if fp + tn else float("nan")
    specificity = tn / (tn + fp) if tn + fp else float("nan")
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "false_positive_rate": fpr,
        "specificity": specificity,
    }


def read_rows(path: Path, require_score_eligible: bool = False) -> List[dict]:
    out = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "timestamp_utc",
            "session_state",
            "nvda_log_price",
            "nvdax_log_price",
            "reference_hidden_mean",
            "reference_predictive_sd",
            "nvdax_innovation_z",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"{path}: missing required columns: {sorted(missing)}")
        for r in reader:
            if require_score_eligible:
                v = str(r.get("score_eligible", "TRUE")).strip().upper()
                if v not in {"TRUE", "T", "1"}:
                    continue
            u = as_float(r["nvda_log_price"])
            x = as_float(r["nvdax_log_price"])
            p = as_float(r["reference_hidden_mean"])
            sd = as_float(r["reference_predictive_sd"])
            iz = as_float(r["nvdax_innovation_z"])
            if not (finite(u) and finite(x) and finite(p)):
                continue
            raw_err = abs(x - u) * 10000.0
            p1a_err = abs(p - u) * 10000.0
            disagreement = abs(x - p) * 10000.0
            disagreement_z = abs(x - p) / sd if finite(sd) and sd > 0 else float("nan")
            innovation_abs_z = abs(iz) if finite(iz) else float("nan")
            p1a_step = p - x
            truth_step = u - x
            direction_toward_truth = (p1a_step * truth_step) > 0 if p1a_step != 0 and truth_step != 0 else False
            out.append({
                "timestamp_utc": r["timestamp_utc"],
                "session_state": r.get("session_state", ""),
                "underlying_log": u,
                "xstock_log": x,
                "p1a_log": p,
                "raw_error_bps": raw_err,
                "p1a_error_bps": p1a_err,
                "improvement_bps": raw_err - p1a_err,
                "p1a_better": p1a_err < raw_err,
                "direction_toward_truth": direction_toward_truth,
                "disagreement_bps": disagreement,
                "disagreement_z": disagreement_z,
                "innovation_abs_z": innovation_abs_z,
            })
    return out


def score_metrics(rows: List[dict], score_name: str, event_threshold: float) -> dict:
    scores = [r[score_name] for r in rows]
    event = [r["raw_error_bps"] >= event_threshold for r in rows]
    return {
        "score": score_name,
        "event_threshold_bps": event_threshold,
        "event_prevalence": rate(event),
        "auroc": auroc(scores, event),
        "average_precision": average_precision(scores, event),
        "spearman_score_vs_raw_error": spearman(scores, [r["raw_error_bps"] for r in rows]),
    }


def fmt(x):
    if isinstance(x, float):
        if math.isnan(x):
            return ""
        return f"{x:.10g}"
    return x


def write_csv(path: Path, rows: List[dict], fieldnames: Sequence[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        seen = set()
        for r in rows:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in fieldnames})


def analyze_asset(asset: str, root: Path, out_root: Path, relative_tail_q: float, fixed_tails: List[float]) -> dict:
    base = root / asset / "p1a_c"
    cross_path = base / "crossfit_scores.csv"
    test_path = base / "test_primary_intervals.csv"
    if not cross_path.exists() or not test_path.exists():
        raise FileNotFoundError(
            f"{asset}: expected {cross_path} and {test_path}. "
            "Run the P1a-C vs Raw-C experiment first."
        )

    train = read_rows(cross_path, require_score_eligible=True)
    test = read_rows(test_path, require_score_eligible=False)
    if len(train) < 100 or len(test) < 20:
        raise RuntimeError(f"{asset}: insufficient labeled rows: crossfit={len(train)} test={len(test)}")

    out = out_root / asset
    out.mkdir(parents=True, exist_ok=True)

    train_raw = [r["raw_error_bps"] for r in train]
    relative_tail_bps = quantile(train_raw, relative_tail_q)

    candidates = ["disagreement_bps", "disagreement_z", "innovation_abs_z"]
    candidate_rows = []
    for s in candidates:
        m = score_metrics(train, s, relative_tail_bps)
        m["asset"] = asset
        m["sample"] = "crossfit_oof_train"
        candidate_rows.append(m)

    # Select on OOF training only. AP is appropriate because the tail event is rare.
    valid_candidates = [r for r in candidate_rows if finite(r["average_precision"])]
    if not valid_candidates:
        raise RuntimeError(f"{asset}: no usable challenger score candidate")
    selected = max(valid_candidates, key=lambda r: (r["average_precision"], r["auroc"] if finite(r["auroc"]) else -1))
    primary = selected["score"]

    train_scores = [r[primary] for r in train if finite(r[primary])]
    q80 = quantile(train_scores, 0.80)
    q90 = quantile(train_scores, 0.90)
    q95 = quantile(train_scores, 0.95)
    q99 = quantile(train_scores, 0.99)

    for r in test:
        s = r[primary]
        if not finite(s):
            status = "UNAVAILABLE"
        elif s >= q95:
            status = "REVIEW"
        elif s >= q80:
            status = "WATCH"
        else:
            status = "SUPPORT"
        r["challenger_score_name"] = primary
        r["challenger_score"] = s
        r["challenge_status"] = status
        r["relative_tail_event"] = r["raw_error_bps"] >= relative_tail_bps
        for bps in fixed_tails:
            r[f"tail_{int(bps)}bps"] = r["raw_error_bps"] >= bps

    # Candidate scores on untouched test are diagnostic only; the selected score was frozen from OOF training.
    for s in candidates:
        m = score_metrics(test, s, relative_tail_bps)
        m["asset"] = asset
        m["sample"] = "untouched_test_diagnostic"
        candidate_rows.append(m)
    write_csv(out / "candidate_score_metrics.csv", candidate_rows)

    event_defs = [(f"relative_q{int(relative_tail_q*100)}", relative_tail_bps)] + [
        (f"fixed_{int(x)}bps", x) for x in fixed_tails
    ]

    detection_rows = []
    scores_test = [r[primary] for r in test]
    for event_name, threshold in event_defs:
        event = [r["raw_error_bps"] >= threshold for r in test]
        for flag_name, flags in [
            ("REVIEW", [r["challenge_status"] == "REVIEW" for r in test]),
            ("WATCH_OR_REVIEW", [r["challenge_status"] in {"WATCH", "REVIEW"} for r in test]),
        ]:
            c = confusion(flags, event)
            detection_rows.append({
                "asset": asset,
                "event": event_name,
                "event_threshold_bps": threshold,
                "event_prevalence": rate(event),
                "flag": flag_name,
                "flag_rate": rate(flags),
                "auroc_primary_score": auroc(scores_test, event),
                "average_precision_primary_score": average_precision(scores_test, event),
                **c,
            })
    write_csv(out / "detection_metrics.csv", detection_rows)

    status_rows = []
    for status in ["SUPPORT", "WATCH", "REVIEW"]:
        rr = [r for r in test if r["challenge_status"] == status]
        if not rr:
            continue
        row = {
            "asset": asset,
            "status": status,
            "n": len(rr),
            "share": len(rr) / len(test),
            "raw_mae_bps": mean([r["raw_error_bps"] for r in rr]),
            "raw_median_error_bps": quantile([r["raw_error_bps"] for r in rr], 0.5),
            "raw_p95_error_bps": quantile([r["raw_error_bps"] for r in rr], 0.95),
            "p1a_mae_bps": mean([r["p1a_error_bps"] for r in rr]),
            "p1a_median_error_bps": quantile([r["p1a_error_bps"] for r in rr], 0.5),
            "p1a_p95_error_bps": quantile([r["p1a_error_bps"] for r in rr], 0.95),
            "mean_tail_reduction_bps": mean([r["improvement_bps"] for r in rr]),
            "p1a_better_rate": rate([r["p1a_better"] for r in rr]),
            "p1a_moves_toward_truth_rate": rate([r["direction_toward_truth"] for r in rr]),
            f"relative_q{int(relative_tail_q*100)}_event_rate": rate([r["relative_tail_event"] for r in rr]),
        }
        for bps in fixed_tails:
            row[f"tail_{int(bps)}bps_event_rate"] = rate([r[f"tail_{int(bps)}bps"] for r in rr])
        status_rows.append(row)
    write_csv(out / "status_error_profile.csv", status_rows)

    # Tail-error reduction conditional on actual hidden-reference tail events.
    tail_rows = []
    for event_name, threshold in event_defs:
        rr = [r for r in test if r["raw_error_bps"] >= threshold]
        if not rr:
            continue
        tail_rows.append({
            "asset": asset,
            "event": event_name,
            "threshold_bps": threshold,
            "n": len(rr),
            "raw_mae_bps": mean([r["raw_error_bps"] for r in rr]),
            "p1a_mae_bps": mean([r["p1a_error_bps"] for r in rr]),
            "mean_tail_reduction_bps": mean([r["improvement_bps"] for r in rr]),
            "p1a_better_rate": rate([r["p1a_better"] for r in rr]),
            "p1a_moves_toward_truth_rate": rate([r["direction_toward_truth"] for r in rr]),
            "review_capture_rate": rate([r["challenge_status"] == "REVIEW" for r in rr]),
            "watch_or_review_capture_rate": rate([r["challenge_status"] in {"WATCH", "REVIEW"} for r in rr]),
        })
    write_csv(out / "tail_reduction_metrics.csv", tail_rows)

    # Threshold-based top-score diagnostics, thresholds frozen from OOF training.
    top_rows = []
    for label, threshold in [("top20", q80), ("top10", q90), ("top5", q95), ("top1", q99)]:
        rr = [r for r in test if finite(r[primary]) and r[primary] >= threshold]
        if not rr:
            continue
        tail_event = [r["raw_error_bps"] >= relative_tail_bps for r in rr]
        top_rows.append({
            "asset": asset,
            "score": primary,
            "bucket": label,
            "train_score_threshold": threshold,
            "n": len(rr),
            "share_test": len(rr) / len(test),
            "raw_mae_bps": mean([r["raw_error_bps"] for r in rr]),
            "p1a_mae_bps": mean([r["p1a_error_bps"] for r in rr]),
            "mean_tail_reduction_bps": mean([r["improvement_bps"] for r in rr]),
            "p1a_better_rate": rate([r["p1a_better"] for r in rr]),
            "relative_tail_precision": rate(tail_event),
        })
    write_csv(out / "top_score_metrics.csv", top_rows)

    # Row-level audit file. The benchmark columns are clearly separated from ex-ante scores/status.
    row_fields = [
        "timestamp_utc", "session_state",
        "challenger_score_name", "challenger_score", "challenge_status",
        "disagreement_bps", "disagreement_z", "innovation_abs_z",
        "raw_error_bps", "p1a_error_bps", "improvement_bps",
        "p1a_better", "direction_toward_truth", "relative_tail_event",
    ] + [f"tail_{int(x)}bps" for x in fixed_tails]
    write_csv(out / "test_challenger_scored_rows.csv", test, row_fields)

    overall = {
        "asset": asset,
        "crossfit_rows": len(train),
        "test_rows": len(test),
        "selected_score": primary,
        "selection_rule": "highest average precision for OOF-train raw-xStock relative-q95 tail event; tie-break AUROC",
        "relative_tail_quantile": relative_tail_q,
        "relative_tail_threshold_bps_from_crossfit": relative_tail_bps,
        "score_q80_from_crossfit": q80,
        "score_q90_from_crossfit": q90,
        "score_q95_from_crossfit": q95,
        "score_q99_from_crossfit": q99,
        "test_raw_mae_bps": mean([r["raw_error_bps"] for r in test]),
        "test_raw_rmse_bps": rmse([r["raw_error_bps"] for r in test]),
        "test_p1a_mae_bps": mean([r["p1a_error_bps"] for r in test]),
        "test_p1a_rmse_bps": rmse([r["p1a_error_bps"] for r in test]),
        "test_p1a_better_rate": rate([r["p1a_better"] for r in test]),
        "test_score_raw_error_spearman": spearman(
            [r[primary] for r in test], [r["raw_error_bps"] for r in test]
        ),
    }
    rel_event = [r["raw_error_bps"] >= relative_tail_bps for r in test]
    overall["test_relative_tail_prevalence"] = rate(rel_event)
    overall["test_relative_tail_auroc"] = auroc([r[primary] for r in test], rel_event)
    overall["test_relative_tail_average_precision"] = average_precision([r[primary] for r in test], rel_event)

    review = [r for r in test if r["challenge_status"] == "REVIEW"]
    support = [r for r in test if r["challenge_status"] == "SUPPORT"]
    overall["review_n"] = len(review)
    overall["review_raw_mae_bps"] = mean([r["raw_error_bps"] for r in review])
    overall["review_p1a_mae_bps"] = mean([r["p1a_error_bps"] for r in review])
    overall["review_mean_tail_reduction_bps"] = mean([r["improvement_bps"] for r in review])
    overall["review_p1a_better_rate"] = rate([r["p1a_better"] for r in review])
    overall["support_n"] = len(support)
    overall["support_raw_mae_bps"] = mean([r["raw_error_bps"] for r in support])
    overall["review_to_support_raw_error_ratio"] = (
        overall["review_raw_mae_bps"] / overall["support_raw_mae_bps"]
        if finite(overall["review_raw_mae_bps"]) and finite(overall["support_raw_mae_bps"]) and overall["support_raw_mae_bps"] > 0
        else float("nan")
    )

    with (out / "challenger_tail_report.json").open("w", encoding="utf-8") as f:
        json.dump(json_safe(overall), f, indent=2)

    return overall


def json_safe(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    return obj


def main():
    ap = argparse.ArgumentParser(description="Evaluate Valtide as an ex-ante challenger/tail-risk detector.")
    ap.add_argument("--outputs-root", default="outputs", help="Root containing <asset>/p1a_c outputs")
    ap.add_argument("--assets", default="nvdax,spyx,qqqx,tslax,aaplx", help="Comma-separated asset keys")
    ap.add_argument("--out", default="outputs/challenger_tail", help="Output directory")
    ap.add_argument("--relative-tail-q", type=float, default=0.95, help="OOF raw-error quantile defining asset-relative tail event")
    ap.add_argument("--fixed-tail-bps", default="25,50", help="Comma-separated fixed raw-error tail thresholds in bps")
    args = ap.parse_args()

    if not (0.5 < args.relative_tail_q < 1.0):
        raise SystemExit("--relative-tail-q must be between 0.5 and 1")

    assets = [x.strip().lower() for x in args.assets.split(",") if x.strip()]
    fixed = [float(x.strip()) for x in args.fixed_tail_bps.split(",") if x.strip()]
    root = Path(os.path.expanduser(args.outputs_root)).resolve()
    out_root = Path(os.path.expanduser(args.out)).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    summaries = []
    failures = []
    for asset in assets:
        print(f"\n=== {asset.upper()} challenger-tail analysis ===", flush=True)
        try:
            s = analyze_asset(asset, root, out_root, args.relative_tail_q, fixed)
            summaries.append(s)
            print(
                f"selected={s['selected_score']} | raw MAE={s['test_raw_mae_bps']:.2f} bps | "
                f"REVIEW raw MAE={s['review_raw_mae_bps']:.2f} bps | "
                f"tail AP={s['test_relative_tail_average_precision']:.3f}",
                flush=True,
            )
        except Exception as e:
            failures.append({"asset": asset, "error": str(e)})
            print(f"ERROR: {asset}: {e}", flush=True)

    if summaries:
        write_csv(out_root / "cross_asset_summary.csv", summaries)
        aggregate = {
            "assets_completed": len(summaries),
            "assets_failed": len(failures),
            "mean_test_raw_mae_bps": mean([s["test_raw_mae_bps"] for s in summaries]),
            "mean_test_p1a_mae_bps": mean([s["test_p1a_mae_bps"] for s in summaries]),
            "mean_review_to_support_raw_error_ratio": mean([s["review_to_support_raw_error_ratio"] for s in summaries]),
            "mean_tail_auroc": mean([s["test_relative_tail_auroc"] for s in summaries]),
            "mean_tail_average_precision": mean([s["test_relative_tail_average_precision"] for s in summaries]),
            "per_asset": summaries,
            "failures": failures,
        }
        with (out_root / "cross_asset_report.json").open("w", encoding="utf-8") as f:
            json.dump(json_safe(aggregate), f, indent=2)

    if failures:
        with (out_root / "failures.json").open("w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)
        raise SystemExit(f"Completed with {len(failures)} failure(s); see {out_root / 'failures.json'}")

    print(f"\nCHALLENGER-TAIL ANALYSIS COMPLETE: {out_root}", flush=True)


if __name__ == "__main__":
    main()
