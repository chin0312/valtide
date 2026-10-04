#!/usr/bin/env python3
"""
Valtide failure-mechanism diagnostics
=====================================

Purpose
-------
Diagnose WHY P1a loses when it strongly disagrees with xStock, with special
attention to NVDAx and TSLAx and SPYx/QQQx/AAPLx as controls.

This script does NOT train a new model. It analyzes the already-frozen
P1a/challenger outputs using seven diagnostic tests:

1. Momentum/alignment
2. Volatility shock
3. Persistence vs reversion after disagreement
4. Session/regime
5. Direction asymmetry
6. Episode-level behavior
7. Temporal stability / regime drift

Future prices are used ONLY in retrospective diagnostic Test 3 and episode
outcomes. They are never proposed as live model inputs.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

BPS = 10000.0
HORIZONS = [5, 15, 30, 60]
EPS = 1e-12


def finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def fnum(v) -> float:
    if v is None:
        return float("nan")
    s = str(v).strip()
    if not s or s.upper() in {"NA", "NAN", "NULL", "NONE"}:
        return float("nan")
    try:
        x = float(s)
        return x if math.isfinite(x) else float("nan")
    except Exception:
        return float("nan")


def bval(v) -> bool:
    return str(v).strip().lower() in {"true", "t", "1", "yes", "y"}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def month_key(s: str) -> str:
    return s[:7]


def sign(x: float) -> float:
    if not finite(x) or abs(x) < EPS:
        return 0.0
    return 1.0 if x > 0 else -1.0


def mean(xs: Iterable[float]) -> float:
    v = [float(x) for x in xs if finite(x)]
    return sum(v) / len(v) if v else float("nan")


def med(xs: Iterable[float]) -> float:
    v = [float(x) for x in xs if finite(x)]
    return median(v) if v else float("nan")


def quantile(xs: Iterable[float], p: float) -> float:
    v = sorted(float(x) for x in xs if finite(x))
    if not v:
        return float("nan")
    if len(v) == 1:
        return v[0]
    h = (len(v) - 1) * p
    lo = int(math.floor(h))
    hi = int(math.ceil(h))
    if lo == hi:
        return v[lo]
    w = h - lo
    return v[lo] * (1.0 - w) + v[hi] * w


def rmse(xs: Iterable[float]) -> float:
    v = [float(x) for x in xs if finite(x)]
    return math.sqrt(sum(x*x for x in v) / len(v)) if v else float("nan")


def mode_str(xs: Iterable[str]) -> str:
    vals = [x for x in xs if x]
    if not vals:
        return ""
    return Counter(vals).most_common(1)[0][0]


def read_csv(path: Path) -> List[dict]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[dict], fieldnames: Optional[Sequence[str]] = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen = set()
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    fieldnames.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            out = {}
            for k in fieldnames:
                v = r.get(k, "")
                if isinstance(v, float) and not math.isfinite(v):
                    v = ""
                out[k] = v
            w.writerow(out)


def basic_metrics(rows: List[dict]) -> dict:
    if not rows:
        return {
            "n": 0,
            "raw_mae_bps": float("nan"),
            "p1a_mae_bps": float("nan"),
            "mean_improvement_bps": float("nan"),
            "p1a_better_rate": float("nan"),
            "true_tail_rate": float("nan"),
            "mean_disagreement_bps": float("nan"),
        }
    return {
        "n": len(rows),
        "raw_mae_bps": mean(r["raw_error_bps"] for r in rows),
        "p1a_mae_bps": mean(r["p1a_error_bps"] for r in rows),
        "mean_improvement_bps": mean(r["improvement_bps"] for r in rows),
        "p1a_better_rate": mean(r["p1a_better"] for r in rows),
        "true_tail_rate": mean(1.0 if r["true_tail_event"] else 0.0 for r in rows),
        "mean_disagreement_bps": mean(r["disagreement_bps"] for r in rows),
    }


def selected_score(row: dict, score_name: str) -> float:
    if score_name == "disagreement_bps":
        return abs(row["x_log"] - row["p1a_log"]) * BPS
    if score_name == "disagreement_z":
        sd = row["predictive_sd"]
        return abs(row["x_log"] - row["p1a_log"]) / sd if finite(sd) and sd > 0 else float("nan")
    if score_name == "innovation_abs_z":
        return abs(row["innovation_z"]) if finite(row["innovation_z"]) else float("nan")
    raise RuntimeError(f"Unknown selected_score={score_name}")


def load_primary(path: Path, asset: str) -> List[dict]:
    raw = read_csv(path)
    fields = list(raw[0].keys()) if raw else []
    log_cols = [c for c in fields if c.endswith("_log_price")]
    x_candidates = [c for c in log_cols if c[:-10].lower().endswith("x")]
    u_candidates = [c for c in log_cols if c not in x_candidates]
    innovation_cols = [c for c in fields if c.endswith("_innovation_z")]
    minutes_cols = [c for c in fields if c.startswith("minutes_since_last_")]

    # The current R pipeline retains legacy generic column names
    # (nvda_log_price / nvdax_log_price) even for non-NVDA assets.
    # Therefore infer roles from schema instead of asset name.
    if len(x_candidates) != 1 or len(u_candidates) != 1 or len(innovation_cols) != 1:
        raise RuntimeError(
            f"{path}: could not infer underlying/xStock columns. "
            f"log_cols={log_cols}, innovation_cols={innovation_cols}"
        )
    ucol = u_candidates[0]
    xcol = x_candidates[0]
    izcol = innovation_cols[0]
    minscol = minutes_cols[0] if len(minutes_cols) == 1 else None

    required = {
        "timestamp_utc", "session_state", ucol, xcol,
        "reference_hidden_mean", "reference_predictive_sd", izcol,
    }
    missing = required.difference(fields)
    if missing:
        raise RuntimeError(f"{path}: missing columns {sorted(missing)}")

    rows = []
    for r in raw:
        u = fnum(r.get(ucol))
        x = fnum(r.get(xcol))
        p = fnum(r.get("reference_hidden_mean"))
        sd = fnum(r.get("reference_predictive_sd"))
        iz = fnum(r.get(izcol))
        if not (finite(x) and finite(p)):
            continue
        raw_err = abs(x-u)*BPS if finite(u) else float("nan")
        p1_err = abs(p-u)*BPS if finite(u) else float("nan")
        rows.append({
            "timestamp_utc": r["timestamp_utc"],
            "ts": parse_ts(r["timestamp_utc"]),
            "session_state": str(r.get("session_state","")).strip().lower(),
            "u_log": u,
            "x_log": x,
            "p1a_log": p,
            "predictive_sd": sd,
            "innovation_z": iz,
            "minutes_since_last_underlying": fnum(r.get(minscol)) if minscol else float("nan"),
            "raw_error_bps": raw_err,
            "p1a_error_bps": p1_err,
            "improvement_bps": raw_err-p1_err if finite(raw_err) and finite(p1_err) else float("nan"),
            "p1a_better": 1 if finite(raw_err) and finite(p1_err) and p1_err < raw_err else 0,
        })
    rows.sort(key=lambda r: r["ts"])
    return rows


def load_crossfit(path: Path, asset: str, report: dict) -> List[dict]:
    rows = load_primary(path, asset)
    score_name = report["selected_score"]
    q80 = float(report["score_q80_from_crossfit"])
    q90 = float(report["score_q90_from_crossfit"])
    tail = float(report["relative_tail_threshold_bps_from_crossfit"])
    out = []
    for r in rows:
        if not (finite(r["raw_error_bps"]) and finite(r["p1a_error_bps"])):
            continue
        sc = selected_score(r, score_name)
        r = dict(r)
        signed_d_bps = (r["x_log"] - r["p1a_log"]) * BPS
        r["signed_disagreement_bps"] = signed_d_bps
        r["disagreement_bps"] = abs(signed_d_bps)
        r["signed_disagreement_z"] = (
            (r["x_log"] - r["p1a_log"]) / r["predictive_sd"]
            if finite(r["predictive_sd"]) and r["predictive_sd"] > 0
            else float("nan")
        )
        r["innovation_abs_z"] = abs(r["innovation_z"]) if finite(r["innovation_z"]) else float("nan")
        r["pred_sd_bps"] = r["predictive_sd"] * BPS if finite(r["predictive_sd"]) else float("nan")
        r["base_score"] = sc
        r["base_watch_or_review"] = finite(sc) and sc >= q80
        r["base_review"] = finite(sc) and sc >= q90
        r["true_tail_event"] = r["raw_error_bps"] >= tail
        out.append(r)
    return out


def merge_test(primary: List[dict], gate_path: Path) -> List[dict]:
    gate_rows = {r["timestamp_utc"]: r for r in read_csv(gate_path)}
    out = []
    for r in primary:
        if not (finite(r["raw_error_bps"]) and finite(r["p1a_error_bps"])):
            continue
        g = gate_rows.get(r["timestamp_utc"])
        if g is None:
            continue
        z = dict(r)
        z.update({
            "base_score": fnum(g.get("base_score")),
            "base_review": bval(g.get("base_review")),
            "base_watch_or_review": str(g.get("gated_status","")).strip().upper() in {"WATCH","REVIEW"} or bval(g.get("base_review")),
            "gated_review": bval(g.get("gated_review")),
            "gated_status": str(g.get("gated_status","")).strip().upper(),
            "true_tail_event": bval(g.get("true_tail_event")),
            "signed_disagreement_bps": fnum(g.get("signed_disagreement_bps")),
            "disagreement_bps": fnum(g.get("disagreement_bps")),
            "signed_disagreement_z": fnum(g.get("signed_disagreement_z")),
            "innovation_abs_z": fnum(g.get("innovation_abs_z")),
            "pred_sd_bps": fnum(g.get("pred_sd_bps")),
            "xret_1_bps": fnum(g.get("xret_1_bps")),
            "xret_3_bps": fnum(g.get("xret_3_bps")),
            "xret_6_bps": fnum(g.get("xret_6_bps")),
            "p1aret_1_bps": fnum(g.get("p1aret_1_bps")),
            "p1aret_3_bps": fnum(g.get("p1aret_3_bps")),
            "dchg_1_bps": fnum(g.get("dchg_1_bps")),
            "dchg_3_bps": fnum(g.get("dchg_3_bps")),
            "xvol_6_bps": fnum(g.get("xvol_6_bps")),
            "lag_alignment_1": fnum(g.get("lag_alignment_1")),
            "lag_alignment_3": fnum(g.get("lag_alignment_3")),
            "gate_probability_p1a_better": fnum(g.get("gate_probability_p1a_better")),
        })
        out.append(z)
    out.sort(key=lambda r: r["ts"])
    return out


def qbucket(x: float, cuts: Sequence[float]) -> str:
    if not finite(x):
        return "missing"
    if x <= cuts[0]:
        return "Q1_low"
    if x <= cuts[1]:
        return "Q2"
    if x <= cuts[2]:
        return "Q3"
    return "Q4_high"


def alignment_label(r: dict) -> str:
    a = r["lag_alignment_3"]
    if not finite(a):
        return "missing"
    if a > 0:
        return "aligned"
    if a < 0:
        return "opposed"
    return "flat"


def direction_label(r: dict) -> str:
    d = r["signed_disagreement_bps"]
    if not finite(d):
        return "missing"
    if d > 0:
        return "xstock_above_p1a"
    if d < 0:
        return "xstock_below_p1a"
    return "equal"


def group_metrics(asset: str, test_name: str, group: str, rows: List[dict]) -> dict:
    return {"asset": asset, "test": test_name, "group": group, **basic_metrics(rows)}


def momentum_alignment_test(asset: str, review: List[dict]) -> Tuple[List[dict], dict]:
    vals = [abs(r["xret_3_bps"]) for r in review if finite(r["xret_3_bps"])]
    cuts = [quantile(vals, .25), quantile(vals, .50), quantile(vals, .75)]
    groups = {}
    for r in review:
        mb = qbucket(abs(r["xret_3_bps"]) if finite(r["xret_3_bps"]) else float("nan"), cuts)
        al = alignment_label(r)
        groups.setdefault((mb, al), []).append(r)
    rows = []
    for (mb, al), rr in sorted(groups.items()):
        rec = group_metrics(asset, "momentum_alignment", f"{mb}|{al}", rr)
        rec["momentum_bucket"] = mb
        rec["alignment"] = al
        rec["mean_abs_xret_3_bps"] = mean(abs(r["xret_3_bps"]) for r in rr)
        rows.append(rec)
    return rows, {"q25": cuts[0], "q50": cuts[1], "q75": cuts[2]}


def volatility_test(asset: str, review: List[dict]) -> Tuple[List[dict], dict]:
    vals = [r["xvol_6_bps"] for r in review if finite(r["xvol_6_bps"])]
    cuts = [quantile(vals, .25), quantile(vals, .50), quantile(vals, .75)]
    groups = {}
    for r in review:
        vb = qbucket(r["xvol_6_bps"], cuts)
        groups.setdefault(vb, []).append(r)
    rows = []
    for vb, rr in sorted(groups.items()):
        rec = group_metrics(asset, "volatility", vb, rr)
        rec["volatility_bucket"] = vb
        rec["mean_xvol_6_bps"] = mean(r["xvol_6_bps"] for r in rr)
        rows.append(rec)
    return rows, {"q25": cuts[0], "q50": cuts[1], "q75": cuts[2]}


def forward_resolution(asset: str, test_rows: List[dict]) -> Tuple[List[dict], List[dict]]:
    review = [r for r in test_rows if r["base_review"]]
    by_ts = {r["ts"]: r for r in test_rows}
    detail = []

    for r in review:
        d0 = r["x_log"] - r["p1a_log"]
        s = sign(d0)
        if s == 0:
            continue
        for h in HORIZONS:
            fut = by_ts.get(r["ts"] + timedelta(minutes=h))
            if fut is None:
                continue
            if not all(finite(fut[k]) for k in ["x_log","p1a_log","u_log"]):
                continue
            dh = fut["x_log"] - fut["p1a_log"]
            p1a_catchup = s * (fut["p1a_log"] - r["p1a_log"]) * BPS
            x_reversion = -s * (fut["x_log"] - r["x_log"]) * BPS
            underlying_follow = (
                s * (fut["u_log"] - r["u_log"]) * BPS
                if finite(r["u_log"]) else float("nan")
            )
            gap0 = abs(d0) * BPS
            gaph = abs(dh) * BPS
            shrink = gaph < gap0

            if shrink:
                if p1a_catchup > x_reversion and p1a_catchup > 0:
                    cls = "p1a_catchup"
                elif x_reversion > p1a_catchup and x_reversion > 0:
                    cls = "xstock_reversion"
                else:
                    cls = "mixed_convergence"
            else:
                cls = "persistent_or_wider"

            x0_to_future_u = abs(r["x_log"] - fut["u_log"]) * BPS
            p0_to_future_u = abs(r["p1a_log"] - fut["u_log"]) * BPS

            detail.append({
                "asset": asset,
                "timestamp_utc": r["timestamp_utc"],
                "horizon_min": h,
                "session_state": r["session_state"],
                "current_p1a_better": r["p1a_better"],
                "current_raw_error_bps": r["raw_error_bps"],
                "current_p1a_error_bps": r["p1a_error_bps"],
                "signed_disagreement_bps": r["signed_disagreement_bps"],
                "xret_3_bps": r["xret_3_bps"],
                "xvol_6_bps": r["xvol_6_bps"],
                "gap_initial_bps": gap0,
                "gap_future_bps": gaph,
                "gap_shrunk": 1 if shrink else 0,
                "p1a_catchup_bps": p1a_catchup,
                "xstock_reversion_bps": x_reversion,
                "underlying_follow_xstock_direction_bps": underlying_follow,
                "current_xstock_closer_to_future_underlying": 1 if x0_to_future_u < p0_to_future_u else 0,
                "resolution_class": cls,
            })

    summary = []
    for h in HORIZONS:
        rr = [r for r in detail if r["horizon_min"] == h]
        if not rr:
            continue
        counts = Counter(r["resolution_class"] for r in rr)
        summary.append({
            "asset": asset,
            "horizon_min": h,
            "n": len(rr),
            "gap_shrink_rate": mean(r["gap_shrunk"] for r in rr),
            "mean_p1a_catchup_bps": mean(r["p1a_catchup_bps"] for r in rr),
            "mean_xstock_reversion_bps": mean(r["xstock_reversion_bps"] for r in rr),
            "mean_underlying_follow_xstock_direction_bps": mean(r["underlying_follow_xstock_direction_bps"] for r in rr),
            "current_xstock_closer_to_future_underlying_rate": mean(r["current_xstock_closer_to_future_underlying"] for r in rr),
            "p1a_catchup_rate": counts["p1a_catchup"] / len(rr),
            "xstock_reversion_rate": counts["xstock_reversion"] / len(rr),
            "mixed_convergence_rate": counts["mixed_convergence"] / len(rr),
            "persistent_or_wider_rate": counts["persistent_or_wider"] / len(rr),
        })
    return detail, summary


def categorical_breakdown(asset: str, name: str, review: List[dict], keyfunc) -> List[dict]:
    groups = {}
    for r in review:
        k = keyfunc(r)
        groups.setdefault(k, []).append(r)
    return [group_metrics(asset, name, str(k), rr) for k, rr in sorted(groups.items(), key=lambda z: str(z[0]))]


def episodes(asset: str, review: List[dict], forward_detail: List[dict]) -> Tuple[List[dict], List[dict]]:
    if not review:
        return [], []
    review = sorted(review, key=lambda r: r["ts"])
    eps = []
    cur = [review[0]]
    for r in review[1:]:
        gap = (r["ts"] - cur[-1]["ts"]).total_seconds() / 60.0
        if gap <= 10:
            cur.append(r)
        else:
            eps.append(cur)
            cur = [r]
    eps.append(cur)

    fwd30 = {(r["timestamp_utc"], r["horizon_min"]): r for r in forward_detail if r["horizon_min"] == 30}

    rows = []
    for i, ep in enumerate(eps, start=1):
        peak = max(ep, key=lambda r: r["disagreement_bps"] if finite(r["disagreement_bps"]) else -1)
        f30 = fwd30.get((peak["timestamp_utc"], 30))
        rows.append({
            "asset": asset,
            "episode_id": f"{asset}_E{i:04d}",
            "start_utc": ep[0]["timestamp_utc"],
            "end_utc": ep[-1]["timestamp_utc"],
            "duration_min": int((ep[-1]["ts"] - ep[0]["ts"]).total_seconds()/60.0) + 5,
            "rows": len(ep),
            "dominant_session": mode_str(r["session_state"] for r in ep),
            "peak_direction": direction_label(peak),
            "max_disagreement_bps": max(r["disagreement_bps"] for r in ep if finite(r["disagreement_bps"])),
            "mean_raw_error_bps": mean(r["raw_error_bps"] for r in ep),
            "max_raw_error_bps": max(r["raw_error_bps"] for r in ep),
            "mean_p1a_error_bps": mean(r["p1a_error_bps"] for r in ep),
            "mean_improvement_bps": mean(r["improvement_bps"] for r in ep),
            "p1a_better_rate": mean(r["p1a_better"] for r in ep),
            "any_true_tail": 1 if any(r["true_tail_event"] for r in ep) else 0,
            "mean_abs_xret_3_bps": mean(abs(r["xret_3_bps"]) for r in ep),
            "mean_xvol_6_bps": mean(r["xvol_6_bps"] for r in ep),
            "peak_30m_resolution": f30["resolution_class"] if f30 else "",
            "peak_30m_underlying_follow_bps": f30["underlying_follow_xstock_direction_bps"] if f30 else float("nan"),
        })

    summary = [{
        "asset": asset,
        "episodes": len(rows),
        "median_duration_min": med(r["duration_min"] for r in rows),
        "median_rows": med(r["rows"] for r in rows),
        "episodes_with_true_tail_rate": mean(r["any_true_tail"] for r in rows),
        "episode_mean_p1a_better_rate": mean(r["p1a_better_rate"] for r in rows),
        "episode_mean_raw_error_bps": mean(r["mean_raw_error_bps"] for r in rows),
        "episode_mean_p1a_error_bps": mean(r["mean_p1a_error_bps"] for r in rows),
    }]
    return rows, summary


def temporal_monthly(asset: str, crossfit: List[dict], test: List[dict]) -> List[dict]:
    rows = []
    for phase, data in [("crossfit", crossfit), ("test", test)]:
        months = sorted(set(month_key(r["timestamp_utc"]) for r in data))
        for m in months:
            md = [r for r in data if month_key(r["timestamp_utc"]) == m]
            for zone, rr in [
                ("all", md),
                ("watch_or_review", [r for r in md if r["base_watch_or_review"]]),
                ("review", [r for r in md if r["base_review"]]),
            ]:
                if not rr:
                    continue
                rec = {"asset": asset, "phase": phase, "month": m, "zone": zone, **basic_metrics(rr)}
                rows.append(rec)
    return rows


def temporal_blocks(asset: str, crossfit: List[dict], test: List[dict], nblocks: int = 4) -> List[dict]:
    rows = []
    for phase, data in [("crossfit", crossfit), ("test", test)]:
        data = sorted(data, key=lambda r: r["ts"])
        if not data:
            continue
        n = len(data)
        for b in range(nblocks):
            lo = int(n * b / nblocks)
            hi = int(n * (b + 1) / nblocks)
            block = data[lo:hi]
            if not block:
                continue
            for zone, rr in [
                ("all", block),
                ("watch_or_review", [r for r in block if r["base_watch_or_review"]]),
                ("review", [r for r in block if r["base_review"]]),
            ]:
                if not rr:
                    continue
                rows.append({
                    "asset": asset,
                    "phase": phase,
                    "block": b + 1,
                    "zone": zone,
                    "start_utc": block[0]["timestamp_utc"],
                    "end_utc": block[-1]["timestamp_utc"],
                    **basic_metrics(rr),
                })
    return rows


def association_table(asset: str, review: List[dict]) -> List[dict]:
    features = [
        "signed_disagreement_bps",
        "disagreement_bps",
        "signed_disagreement_z",
        "innovation_abs_z",
        "pred_sd_bps",
        "xret_1_bps",
        "xret_3_bps",
        "xret_6_bps",
        "xvol_6_bps",
        "dchg_1_bps",
        "dchg_3_bps",
        "lag_alignment_3",
    ]
    rows = []
    for feature in features:
        win = [r[feature] for r in review if r["p1a_better"] == 1 and finite(r[feature])]
        lose = [r[feature] for r in review if r["p1a_better"] == 0 and finite(r[feature])]
        rows.append({
            "asset": asset,
            "feature": feature,
            "p1a_better_n": len(win),
            "p1a_worse_n": len(lose),
            "p1a_better_mean": mean(win),
            "p1a_worse_mean": mean(lose),
            "mean_difference_better_minus_worse": mean(win) - mean(lose) if win and lose else float("nan"),
            "p1a_better_median": med(win),
            "p1a_worse_median": med(lose),
        })
    return rows


def example_rows(asset: str, review: List[dict], forward_detail: List[dict], protective: bool, n: int = 30) -> List[dict]:
    f30 = {(r["timestamp_utc"], r["horizon_min"]): r for r in forward_detail if r["horizon_min"] == 30}
    if protective:
        ordered = sorted(review, key=lambda r: r["improvement_bps"], reverse=True)
    else:
        ordered = sorted(review, key=lambda r: r["improvement_bps"])
    out = []
    for r in ordered[:n]:
        fr = f30.get((r["timestamp_utc"], 30))
        out.append({
            "asset": asset,
            "timestamp_utc": r["timestamp_utc"],
            "session_state": r["session_state"],
            "raw_error_bps": r["raw_error_bps"],
            "p1a_error_bps": r["p1a_error_bps"],
            "improvement_bps": r["improvement_bps"],
            "signed_disagreement_bps": r["signed_disagreement_bps"],
            "xret_1_bps": r["xret_1_bps"],
            "xret_3_bps": r["xret_3_bps"],
            "xret_6_bps": r["xret_6_bps"],
            "xvol_6_bps": r["xvol_6_bps"],
            "lag_alignment_3": r["lag_alignment_3"],
            "innovation_abs_z": r["innovation_abs_z"],
            "future_30m_resolution": fr["resolution_class"] if fr else "",
            "future_30m_underlying_follow_bps": fr["underlying_follow_xstock_direction_bps"] if fr else float("nan"),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--p1ac-dir", required=True)
    ap.add_argument("--challenger-report", required=True)
    ap.add_argument("--gate-dir", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    asset = args.asset.lower()
    p1 = Path(args.p1ac_dir)
    gate = Path(args.gate_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    report = json.loads(Path(args.challenger_report).read_text(encoding="utf-8"))

    primary = load_primary(p1 / "test_primary_intervals.csv", asset)
    test = merge_test(primary, gate / "test_gate_scored_rows.csv")
    crossfit = load_crossfit(p1 / "crossfit_scores.csv", asset, report)

    review = [r for r in test if r["base_review"]]
    support = [r for r in test if not r["base_watch_or_review"]]
    watch = [r for r in test if r["base_watch_or_review"] and not r["base_review"]]

    mom_rows, mom_cuts = momentum_alignment_test(asset, review)
    vol_rows, vol_cuts = volatility_test(asset, review)
    fwd_detail, fwd_summary = forward_resolution(asset, test)
    session_rows = categorical_breakdown(asset, "session", review, lambda r: r["session_state"])
    direction_rows = categorical_breakdown(asset, "direction", review, direction_label)
    ep_rows, ep_summary = episodes(asset, review, fwd_detail)
    monthly_rows = temporal_monthly(asset, crossfit, test)
    block_rows = temporal_blocks(asset, crossfit, test)
    assoc_rows = association_table(asset, review)
    false_examples = example_rows(asset, review, fwd_detail, protective=False)
    protective_examples = example_rows(asset, review, fwd_detail, protective=True)

    overall = {
        "asset": asset,
        "selected_challenger_score": report["selected_score"],
        "review_threshold_q90": report["score_q90_from_crossfit"],
        "tail_threshold_bps": report["relative_tail_threshold_bps_from_crossfit"],
        "test_rows": len(test),
        **{f"support_{k}": v for k,v in basic_metrics(support).items()},
        **{f"watch_{k}": v for k,v in basic_metrics(watch).items()},
        **{f"review_{k}": v for k,v in basic_metrics(review).items()},
        "momentum_abs_xret3_q25_bps": mom_cuts["q25"],
        "momentum_abs_xret3_q50_bps": mom_cuts["q50"],
        "momentum_abs_xret3_q75_bps": mom_cuts["q75"],
        "volatility_q25_bps": vol_cuts["q25"],
        "volatility_q50_bps": vol_cuts["q50"],
        "volatility_q75_bps": vol_cuts["q75"],
        "episodes": len(ep_rows),
    }

    write_csv(out / "diagnostic_summary.csv", [overall])
    write_csv(out / "01_momentum_alignment.csv", mom_rows)
    write_csv(out / "02_volatility_buckets.csv", vol_rows)
    write_csv(out / "03_forward_resolution_detail.csv", fwd_detail)
    write_csv(out / "03_forward_resolution_summary.csv", fwd_summary)
    write_csv(out / "04_session_breakdown.csv", session_rows)
    write_csv(out / "05_direction_asymmetry.csv", direction_rows)
    write_csv(out / "06_review_episodes.csv", ep_rows)
    write_csv(out / "06_episode_summary.csv", ep_summary)
    write_csv(out / "07_temporal_monthly.csv", monthly_rows)
    write_csv(out / "07_temporal_blocks.csv", block_rows)
    write_csv(out / "feature_outcome_associations.csv", assoc_rows)
    write_csv(out / "largest_false_challenges.csv", false_examples)
    write_csv(out / "largest_protective_challenges.csv", protective_examples)

    js = {
        "asset": asset,
        "purpose": "diagnose P1a lag versus xStock dislocation before training another gate",
        "important_note": (
            "Future prices in forward-resolution outputs are retrospective diagnostics only. "
            "They must not be used as live model features."
        ),
        "overall": overall,
        "momentum_quantile_cuts_bps": mom_cuts,
        "volatility_quantile_cuts_bps": vol_cuts,
        "forward_resolution_summary": fwd_summary,
        "episode_summary": ep_summary,
    }
    (out / "diagnostic_report.json").write_text(json.dumps(js, indent=2), encoding="utf-8")

    print(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
