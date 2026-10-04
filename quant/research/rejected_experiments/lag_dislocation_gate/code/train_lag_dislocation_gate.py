#!/usr/bin/env python3
"""
Valtide lag-vs-dislocation gate trainer.

Goal
----
Train an asset-specific gate that answers:

    When P1a and xStock disagree, is P1a more likely to be the useful
    challenger, or is P1a simply lagging a genuine xStock move?

The gate is trained ONLY on leakage-safe P1a cross-fit rows. The current
underlying price is used only as the historical training label:
    y = 1 if P1a was closer to the hidden underlying than raw xStock.

At prediction time, the gate uses only quantities available at timestamp t:
P1a/xStock disagreement, P1a uncertainty/innovation, current/past xStock
movement, current/past P1a movement, and session.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import deque
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

EPS = 1e-10

FEATURES = [
    "signed_disagreement_bps",
    "disagreement_bps",
    "signed_disagreement_z",
    "innovation_z",
    "innovation_abs_z",
    "pred_sd_bps",
    "xret_1_bps",
    "xret_3_bps",
    "xret_6_bps",
    "p1aret_1_bps",
    "p1aret_3_bps",
    "dchg_1_bps",
    "dchg_3_bps",
    "xvol_6_bps",
    "lag_alignment_1",
    "lag_alignment_3",
    "session_premarket",
    "session_regular",
    "session_afterhours",
    "session_overnight",
    "session_closed",
]

LAMBDA_GRID = [0.1, 1.0, 10.0]


def finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def as_float(v) -> float:
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


def parse_ts(s: str):
    # ISO UTC timestamps sort lexicographically, but we need gap minutes.
    # Avoid datetime dependency quirks by using stdlib.
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sign(x: float) -> float:
    if not finite(x) or x == 0:
        return 0.0
    return 1.0 if x > 0 else -1.0


def mean(xs: Sequence[float]) -> float:
    vals = [float(x) for x in xs if finite(x)]
    return sum(vals) / len(vals) if vals else float("nan")


def stdev(xs: Sequence[float]) -> float:
    vals = [float(x) for x in xs if finite(x)]
    if len(vals) < 2:
        return float("nan")
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def quantile(xs: Sequence[float], p: float) -> float:
    vals = sorted(float(x) for x in xs if finite(x))
    if not vals:
        return float("nan")
    if len(vals) == 1:
        return vals[0]
    h = (len(vals) - 1) * p
    lo = int(math.floor(h))
    hi = int(math.ceil(h))
    if lo == hi:
        return vals[lo]
    w = h - lo
    return vals[lo] * (1 - w) + vals[hi] * w


def sigmoid(z: float) -> float:
    if z >= 0:
        e = math.exp(-min(z, 60.0))
        return 1.0 / (1.0 + e)
    e = math.exp(max(z, -60.0))
    return e / (1.0 + e)


def average_ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        v = values[order[i]]
        while j < len(order) and values[order[j]] == v:
            j += 1
        avg = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    return ranks


def auroc(scores: Sequence[float], labels: Sequence[int]) -> float:
    pairs = [(float(s), int(y)) for s, y in zip(scores, labels) if finite(s)]
    pos = sum(y for _, y in pairs)
    neg = len(pairs) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    ranks = average_ranks([s for s, _ in pairs])
    rpos = sum(r for r, (_, y) in zip(ranks, pairs) if y == 1)
    return (rpos - pos * (pos + 1) / 2.0) / (pos * neg)


def average_precision(scores: Sequence[float], labels: Sequence[int]) -> float:
    pairs = sorted(
        [(float(s), int(y)) for s, y in zip(scores, labels) if finite(s)],
        key=lambda z: z[0],
        reverse=True,
    )
    total_pos = sum(y for _, y in pairs)
    if total_pos == 0:
        return float("nan")
    tp = 0
    acc = 0.0
    for i, (_, y) in enumerate(pairs, start=1):
        if y:
            tp += 1
            acc += tp / i
    return acc / total_pos


def confusion(flagged: Sequence[bool], event: Sequence[bool]) -> Dict[str, float]:
    tp = sum(1 for f, e in zip(flagged, event) if f and e)
    fp = sum(1 for f, e in zip(flagged, event) if f and not e)
    fn = sum(1 for f, e in zip(flagged, event) if (not f) and e)
    tn = sum(1 for f, e in zip(flagged, event) if (not f) and (not e))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "false_positive_rate": fp / (fp + tn) if fp + tn else float("nan"),
    }


def read_and_engineer(path: Path, require_score_eligible: bool) -> List[dict]:
    rows_raw = []
    with path.open("r", newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        required = {
            "timestamp_utc",
            "session_state",
            "nvda_log_price",
            "nvdax_log_price",
            "reference_hidden_mean",
            "reference_predictive_sd",
            "nvdax_innovation_z",
        }
        missing = required.difference(rd.fieldnames or [])
        if missing:
            raise RuntimeError(f"{path}: missing required columns {sorted(missing)}")
        for r in rd:
            if require_score_eligible:
                v = str(r.get("score_eligible", "TRUE")).strip().upper()
                if v not in {"TRUE", "T", "1"}:
                    continue
            rows_raw.append(r)

    rows_raw.sort(key=lambda r: r["timestamp_utc"])
    out = []
    hist = deque(maxlen=32)
    ret_hist = deque(maxlen=12)
    prev_ts = None

    for r in rows_raw:
        ts = parse_ts(r["timestamp_utc"])
        if prev_ts is None or (ts - prev_ts).total_seconds() <= 0 or (ts - prev_ts).total_seconds() > 600:
            hist.clear()
            ret_hist.clear()
        prev_ts = ts

        u = as_float(r.get("nvda_log_price"))
        x = as_float(r.get("nvdax_log_price"))
        p = as_float(r.get("reference_hidden_mean"))
        sd = as_float(r.get("reference_predictive_sd"))
        iz = as_float(r.get("nvdax_innovation_z"))
        mins = as_float(r.get("minutes_since_last_nvda"))

        if not (finite(x) and finite(p)):
            # Cannot form gate features; preserve timing reset behavior only.
            continue

        signed_d = (x - p) * 10000.0
        abs_d = abs(signed_d)
        dz = (x - p) / sd if finite(sd) and sd > 0 else float("nan")
        pred_sd_bps = sd * 10000.0 if finite(sd) else float("nan")

        def lag_val(k: int, key: str) -> float:
            if len(hist) < k:
                return float("nan")
            return hist[-k][key]

        xret1 = (x - lag_val(1, "x")) * 10000.0 if len(hist) >= 1 else float("nan")
        xret3 = (x - lag_val(3, "x")) * 10000.0 if len(hist) >= 3 else float("nan")
        xret6 = (x - lag_val(6, "x")) * 10000.0 if len(hist) >= 6 else float("nan")
        p1ret1 = (p - lag_val(1, "p")) * 10000.0 if len(hist) >= 1 else float("nan")
        p1ret3 = (p - lag_val(3, "p")) * 10000.0 if len(hist) >= 3 else float("nan")
        dchg1 = signed_d - lag_val(1, "d") if len(hist) >= 1 else float("nan")
        dchg3 = signed_d - lag_val(3, "d") if len(hist) >= 3 else float("nan")

        if finite(xret1):
            ret_hist.append(xret1)
        xvol6 = stdev(list(ret_hist)[-6:]) if len(ret_hist) >= 2 else float("nan")

        sess = str(r.get("session_state", "")).strip().lower()
        feat = {
            "signed_disagreement_bps": signed_d,
            "disagreement_bps": abs_d,
            "signed_disagreement_z": dz,
            "innovation_z": iz,
            "innovation_abs_z": abs(iz) if finite(iz) else float("nan"),
            "pred_sd_bps": pred_sd_bps,
            "xret_1_bps": xret1,
            "xret_3_bps": xret3,
            "xret_6_bps": xret6,
            "p1aret_1_bps": p1ret1,
            "p1aret_3_bps": p1ret3,
            "dchg_1_bps": dchg1,
            "dchg_3_bps": dchg3,
            "xvol_6_bps": xvol6,
            "lag_alignment_1": sign(signed_d) * sign(xret1),
            "lag_alignment_3": sign(signed_d) * sign(xret3),
            "session_premarket": 1.0 if sess == "premarket" else 0.0,
            "session_regular": 1.0 if sess == "regular" else 0.0,
            "session_afterhours": 1.0 if sess == "afterhours" else 0.0,
            "session_overnight": 1.0 if sess == "overnight" else 0.0,
            "session_closed": 1.0 if sess == "closed" else 0.0,
        }

        raw_err = abs(x - u) * 10000.0 if finite(u) else float("nan")
        p1a_err = abs(p - u) * 10000.0 if finite(u) else float("nan")

        out.append({
            "timestamp_utc": r["timestamp_utc"],
            "session_state": sess,
            "underlying_log": u,
            "xstock_log": x,
            "p1a_log": p,
            "raw_error_bps": raw_err,
            "p1a_error_bps": p1a_err,
            "improvement_bps": raw_err - p1a_err if finite(raw_err) and finite(p1a_err) else float("nan"),
            "p1a_better": 1 if finite(raw_err) and finite(p1a_err) and p1a_err < raw_err else 0,
            "minutes_since_last_underlying": mins,
            **feat,
        })

        hist.append({"x": x, "p": p, "d": signed_d})

    return out


def score_value(row: dict, score_name: str) -> float:
    if score_name == "disagreement_bps":
        return row["disagreement_bps"]
    if score_name == "disagreement_z":
        return abs(row["signed_disagreement_z"]) if finite(row["signed_disagreement_z"]) else float("nan")
    if score_name == "innovation_abs_z":
        return row["innovation_abs_z"]
    raise RuntimeError(f"Unsupported challenger score: {score_name}")


def class_weights(labels: Sequence[int]) -> Tuple[float, float]:
    n = len(labels)
    p = sum(labels)
    q = n - p
    if p == 0 or q == 0:
        return 1.0, 1.0
    return n / (2.0 * p), n / (2.0 * q)


def fit_scaler(rows: List[dict]) -> dict:
    medians, means, sds = {}, {}, {}
    for name in FEATURES:
        vals = [r[name] for r in rows if finite(r[name])]
        med = quantile(vals, 0.5) if vals else 0.0
        filled = [r[name] if finite(r[name]) else med for r in rows]
        m = mean(filled)
        sd = stdev(filled)
        if not finite(sd) or sd < 1e-8:
            sd = 1.0
        medians[name], means[name], sds[name] = med, m, sd
    return {"medians": medians, "means": means, "sds": sds}


def vectorize(row: dict, scaler: dict) -> List[float]:
    vals = [1.0]  # intercept
    for name in FEATURES:
        x = row[name]
        if not finite(x):
            x = scaler["medians"][name]
        vals.append((x - scaler["means"][name]) / scaler["sds"][name])
    return vals


def solve_linear(A: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-12:
            M[pivot][col] += 1e-8
        M[col], M[pivot] = M[pivot], M[col]
        piv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= piv
        for r in range(n):
            if r == col:
                continue
            fac = M[r][col]
            if fac == 0:
                continue
            for j in range(col, n + 1):
                M[r][j] -= fac * M[col][j]
    return [M[i][n] for i in range(n)]


def fit_ridge_logistic(rows: List[dict], lam: float, scaler: dict, max_iter: int = 40) -> dict:
    X = [vectorize(r, scaler) for r in rows]
    y = [int(r["p1a_better"]) for r in rows]
    pcount = len(X[0])

    # Class balancing is intentional: the gate should learn both "P1a useful"
    # and "P1a lagging" states even when one is historically more frequent.
    wpos, wneg = class_weights(y)
    cweights = [wpos if yi == 1 else wneg for yi in y]

    # Degenerate class: return a constant-probability model.
    if sum(y) == 0 or sum(y) == len(y):
        prevalence = (sum(y) + 0.5) / (len(y) + 1.0)
        beta = [math.log(prevalence / (1.0 - prevalence))] + [0.0] * (pcount - 1)
        return {"beta": beta, "lambda": lam, "iterations": 0, "degenerate": True}

    beta = [0.0] * pcount
    for it in range(max_iter):
        H = [[0.0] * pcount for _ in range(pcount)]
        rhs = [0.0] * pcount

        for xi, yi, cw in zip(X, y, cweights):
            eta = sum(b * x for b, x in zip(beta, xi))
            pr = min(max(sigmoid(eta), 1e-7), 1.0 - 1e-7)
            wi = cw * pr * (1.0 - pr)
            zi = eta + (yi - pr) / (pr * (1.0 - pr))
            for j in range(pcount):
                rhs[j] += wi * xi[j] * zi
                xj = xi[j]
                for k in range(j, pcount):
                    H[j][k] += wi * xj * xi[k]

        for j in range(pcount):
            for k in range(j):
                H[j][k] = H[k][j]
        # Ridge penalty except intercept.
        for j in range(1, pcount):
            H[j][j] += lam
        H[0][0] += 1e-8

        new_beta = solve_linear(H, rhs)
        delta = max(abs(a - b) for a, b in zip(new_beta, beta))
        beta = new_beta
        if delta < 1e-7:
            return {"beta": beta, "lambda": lam, "iterations": it + 1, "degenerate": False}

    return {"beta": beta, "lambda": lam, "iterations": max_iter, "degenerate": False}


def predict_prob(row: dict, model: dict, scaler: dict) -> float:
    x = vectorize(row, scaler)
    return sigmoid(sum(b * v for b, v in zip(model["beta"], x)))


def balanced_logloss(rows: List[dict], probs: Sequence[float]) -> float:
    y = [int(r["p1a_better"]) for r in rows]
    wpos, wneg = class_weights(y)
    losses, weights = [], []
    for yi, pr in zip(y, probs):
        pr = min(max(pr, 1e-10), 1.0 - 1e-10)
        w = wpos if yi else wneg
        losses.append(-w * (yi * math.log(pr) + (1 - yi) * math.log(1 - pr)))
        weights.append(w)
    return sum(losses) / sum(weights) if weights else float("nan")


def subset_metrics(rows: List[dict]) -> dict:
    if not rows:
        return {
            "n": 0, "raw_mae_bps": float("nan"), "p1a_mae_bps": float("nan"),
            "mean_improvement_bps": float("nan"), "p1a_better_rate": float("nan")
        }
    return {
        "n": len(rows),
        "raw_mae_bps": mean([r["raw_error_bps"] for r in rows]),
        "p1a_mae_bps": mean([r["p1a_error_bps"] for r in rows]),
        "mean_improvement_bps": mean([r["improvement_bps"] for r in rows]),
        "p1a_better_rate": mean([r["p1a_better"] for r in rows]),
    }


def write_csv(path: Path, rows: List[dict], fieldnames: Sequence[str] | None = None):
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
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            out = {}
            for k in fieldnames:
                v = r.get(k, "")
                if isinstance(v, float) and not math.isfinite(v):
                    v = ""
                out[k] = v
            wr.writerow(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", required=True)
    ap.add_argument("--p1ac-dir", required=True, help="outputs/<asset>/p1a_c")
    ap.add_argument("--challenger-report", required=True, help="prior challenger_tail_report.json")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--train-fraction", type=float, default=0.70)
    ap.add_argument("--gate-threshold", type=float, default=0.50)
    args = ap.parse_args()

    asset = args.asset.lower()
    p1dir = Path(args.p1ac_dir)
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    report = json.loads(Path(args.challenger_report).read_text(encoding="utf-8"))
    score_name = report["selected_score"]
    q80 = float(report["score_q80_from_crossfit"])
    q90 = float(report["score_q90_from_crossfit"])
    tail_threshold = float(report["relative_tail_threshold_bps_from_crossfit"])

    crossfit_all = read_and_engineer(p1dir / "crossfit_scores.csv", require_score_eligible=True)
    test_all = read_and_engineer(p1dir / "test_primary_intervals.csv", require_score_eligible=False)

    # Underlying is allowed only for historical labels/evaluation.
    crossfit = [r for r in crossfit_all if finite(r["raw_error_bps"]) and finite(r["p1a_error_bps"])]
    test = [r for r in test_all if finite(r["raw_error_bps"]) and finite(r["p1a_error_bps"])]

    for r in crossfit:
        r["base_score"] = score_value(r, score_name)
    for r in test:
        r["base_score"] = score_value(r, score_name)

    # Gate is deliberately trained only where the existing challenger already
    # sees an unusual observation (WATCH + REVIEW zone). This keeps the task
    # focused on "which side is wrong?" rather than relearning ordinary pricing.
    candidate = [r for r in crossfit if finite(r["base_score"]) and r["base_score"] >= q80]
    if len(candidate) < 200:
        raise RuntimeError(f"{asset}: too few candidate rows for gate training: {len(candidate)}")

    cut = max(100, min(len(candidate) - 100, int(len(candidate) * args.train_fraction)))
    fit_rows = candidate[:cut]
    val_rows = candidate[cut:]

    lambda_rows = []
    best = None
    for lam in LAMBDA_GRID:
        scaler = fit_scaler(fit_rows)
        model = fit_ridge_logistic(fit_rows, lam, scaler)
        probs = [predict_prob(r, model, scaler) for r in val_rows]
        ll = balanced_logloss(val_rows, probs)
        auc = auroc(probs, [r["p1a_better"] for r in val_rows])
        apv = average_precision(probs, [r["p1a_better"] for r in val_rows])
        rec = {
            "lambda": lam,
            "validation_balanced_logloss": ll,
            "validation_auroc": auc,
            "validation_average_precision": apv,
            "fit_n": len(fit_rows),
            "validation_n": len(val_rows),
            "fit_p1a_better_rate": mean([r["p1a_better"] for r in fit_rows]),
            "validation_p1a_better_rate": mean([r["p1a_better"] for r in val_rows]),
        }
        lambda_rows.append(rec)
        if best is None or (finite(ll) and ll < best[0]):
            best = (ll, lam)

    selected_lambda = best[1] if best else 1.0

    # Freeze lambda, then refit on all leakage-safe cross-fit candidate rows.
    full_scaler = fit_scaler(candidate)
    full_model = fit_ridge_logistic(candidate, selected_lambda, full_scaler)

    for r in test:
        r["gate_probability_p1a_better"] = predict_prob(r, full_model, full_scaler)
        base_score = r["base_score"]
        r["base_review"] = bool(finite(base_score) and base_score >= q90)
        r["base_watch_or_review"] = bool(finite(base_score) and base_score >= q80)
        r["gated_review"] = bool(
            r["base_review"] and
            r["gate_probability_p1a_better"] >= args.gate_threshold
        )
        if r["gated_review"]:
            r["gated_status"] = "REVIEW"
        elif r["base_watch_or_review"]:
            r["gated_status"] = "WATCH"
        else:
            r["gated_status"] = "SUPPORT"
        r["true_tail_event"] = bool(r["raw_error_bps"] >= tail_threshold)

    candidate_test = [r for r in test if r["base_watch_or_review"]]
    gate_auc = auroc(
        [r["gate_probability_p1a_better"] for r in candidate_test],
        [r["p1a_better"] for r in candidate_test],
    )
    gate_ap = average_precision(
        [r["gate_probability_p1a_better"] for r in candidate_test],
        [r["p1a_better"] for r in candidate_test],
    )

    base_review = [r for r in test if r["base_review"]]
    gated_review = [r for r in test if r["gated_review"]]

    base_tail_conf = confusion(
        [r["base_review"] for r in test],
        [r["true_tail_event"] for r in test],
    )
    gated_tail_conf = confusion(
        [r["gated_review"] for r in test],
        [r["true_tail_event"] for r in test],
    )

    metrics = {
        "asset": asset,
        "selected_base_score": score_name,
        "base_q80_threshold": q80,
        "base_q90_threshold": q90,
        "raw_tail_threshold_bps": tail_threshold,
        "selected_lambda": selected_lambda,
        "gate_threshold": args.gate_threshold,
        "crossfit_rows": len(crossfit),
        "gate_candidate_crossfit_rows": len(candidate),
        "test_labeled_rows": len(test),
        "gate_candidate_test_rows": len(candidate_test),
        "gate_test_auroc_p1a_better": gate_auc,
        "gate_test_average_precision_p1a_better": gate_ap,
        **{f"base_review_{k}": v for k, v in subset_metrics(base_review).items()},
        **{f"gated_review_{k}": v for k, v in subset_metrics(gated_review).items()},
        "base_review_tail_precision": base_tail_conf["precision"],
        "base_review_tail_recall": base_tail_conf["recall"],
        "gated_review_tail_precision": gated_tail_conf["precision"],
        "gated_review_tail_recall": gated_tail_conf["recall"],
    }

    status_rows = []
    for status in ["SUPPORT", "WATCH", "REVIEW"]:
        ss = [r for r in test if r["gated_status"] == status]
        m = subset_metrics(ss)
        status_rows.append({
            "asset": asset,
            "status": status,
            **m,
            "true_tail_rate": mean([1 if r["true_tail_event"] else 0 for r in ss]) if ss else float("nan"),
            "mean_gate_probability": mean([r["gate_probability_p1a_better"] for r in ss]) if ss else float("nan"),
        })

    coeff_rows = [{"feature": "(intercept)", "coefficient": full_model["beta"][0]}]
    for name, coef in zip(FEATURES, full_model["beta"][1:]):
        coeff_rows.append({"feature": name, "coefficient": coef})

    scored_fields = [
        "timestamp_utc", "session_state", "raw_error_bps", "p1a_error_bps",
        "improvement_bps", "p1a_better", "base_score",
        "gate_probability_p1a_better", "base_review", "gated_review",
        "gated_status", "true_tail_event",
    ] + FEATURES

    write_csv(outdir / "validation_lambda_metrics.csv", lambda_rows)
    write_csv(outdir / "test_gate_metrics.csv", [metrics])
    write_csv(outdir / "status_error_profile.csv", status_rows)
    write_csv(outdir / "feature_coefficients.csv", coeff_rows)
    write_csv(outdir / "test_gate_scored_rows.csv", test, scored_fields)

    model_json = {
        "asset": asset,
        "purpose": "lag-vs-dislocation gate",
        "training_label": "1 when P1a point estimate is closer than raw xStock to the hidden contemporaneous underlying",
        "gate_training_zone": "crossfit rows with prior challenger score >= crossfit q80",
        "base_score": score_name,
        "q80": q80,
        "q90": q90,
        "gate_threshold": args.gate_threshold,
        "selected_lambda": selected_lambda,
        "features": FEATURES,
        "scaler": full_scaler,
        "coefficients": {
            "(intercept)": full_model["beta"][0],
            **{k: v for k, v in zip(FEATURES, full_model["beta"][1:])},
        },
        "fit_iterations": full_model["iterations"],
        "fit_degenerate": full_model["degenerate"],
        "leakage_note": (
            "Current underlying is used only to form historical training labels and final evaluation. "
            "No current underlying value is included in gate features."
        ),
    }
    (outdir / "gate_model.json").write_text(json.dumps(model_json, indent=2), encoding="utf-8")
    (outdir / "gate_report.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
