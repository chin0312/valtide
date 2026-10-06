"""Reproduce out-of-fit-period diagnostics from externally stored canonical panels.

This offline tool uses the production panel identity checks and the same
asset-specific replay/validation path as the backend. It never fetches market
data, fits a model, recalibrates an interval, or substitutes another source.

Example (run from the repository root after installing backend + quant packages):

    PYTHONPATH=apps/api python quant/tools/evaluate_fresh_panels.py \\
      --panel NVDAx=/data/panels/nvdax.csv \\
      --panel SPYx=/data/panels/spyx.csv \\
      --panel QQQx=/data/panels/qqqx.csv \\
      --panel AAPLx=/data/panels/aaplx.csv \\
      --output /tmp/fresh-validation.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from importlib import resources
from pathlib import Path
from statistics import mean, median
from typing import Any

from valtide_api.assets import resolve_asset_config, supported_asset_names
from valtide_api.challenger_detector import (
    detector_artifact,
    detector_band,
    detector_score,
    resolve_challenger_detector,
)
from valtide_api.config import Settings
from valtide_api.models import ChallengerEstimate, ValuationResult
from valtide_api.panel import inspect_panel_readiness, load_panel_snapshots
from valtide_api.quant_runtime import estimate, get_quant_service, resolve_quant_runtime
from valtide_api.replay import _warm_state_to_first_observation, replay
from valtide_api.state_store import KalmanState

_EXPECTED_ASSETS = ("NVDAx", "SPYx", "QQQx", "AAPLx")
_PRICE_FIELDS = (
    "token_close",
    "underlying_close",
    "reference_under_test",
    "last_trusted_reference",
)


def _pinned_settings(asset: str) -> Settings:
    """Build secret-free settings pinned to the committed production identity."""
    config = resolve_asset_config(asset, Settings(_env_file=None))
    return Settings(
        _env_file=None,
        okx_nvdax_chain_index=config.okx_chain_index or "",
        okx_nvdax_token_address=config.token_address or "",
    )


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("panel has duplicate header columns")
        rows = list(reader)
    if not rows:
        raise ValueError("panel is empty")
    for index, row in enumerate(rows, start=2):
        if None in row:
            raise ValueError(f"panel row {index} has more fields than its header")
        for field in _PRICE_FIELDS:
            raw = (row.get(field) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(f"panel row {index} has invalid {field}") from exc
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"panel row {index} has non-positive/non-finite {field}")
        for field in ("token_volume", "token_volume_usd"):
            raw = (row.get(field) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(f"panel row {index} has invalid {field}") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"panel row {index} has invalid {field}")
    return rows


def _mae_rmse(errors: list[float]) -> dict[str, float | None]:
    if not errors:
        return {"mae": None, "rmse": None}
    return {
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pairwise_diagnostics(snapshots: list[Any], results: list[ValuationResult]) -> dict[str, Any]:
    pairs: dict[str, list[float]] = {
        "xstock_minus_p1ac_bps": [],
        "xperp_minus_p1ac_bps": [],
        "xstock_minus_xperp_bps": [],
    }
    for snapshot, result in zip(snapshots, results, strict=True):
        fair = result.valtide_fair_value
        token = snapshot.token_price
        xperp = snapshot.xperp_index_price
        if token is not None and fair > 0:
            pairs["xstock_minus_p1ac_bps"].append((token / fair - 1) * 10_000)
        if xperp is not None and fair > 0:
            pairs["xperp_minus_p1ac_bps"].append((xperp / fair - 1) * 10_000)
        if token is not None and xperp is not None and xperp > 0:
            pairs["xstock_minus_xperp_bps"].append((token / xperp - 1) * 10_000)
    return {
        name: {
            "n": len(values),
            "mean_signed_bps": _mean(values),
            "mean_absolute_bps": _mean([abs(value) for value in values]),
        }
        for name, values in pairs.items()
    }


def _token_update_weight(asset: str, snapshots: list[Any]) -> dict[str, Any]:
    """Reproduce scalar Kalman token gain from posterior covariance and R_token."""
    artifact = get_quant_service(asset).runtime.artifact
    token_variance = artifact.r_nvdax
    m = p = timestamp = None
    gains: list[float] = []
    for snapshot in snapshots:
        estimate_result = estimate(snapshot, m, p, timestamp)
        if snapshot.token_price is not None:
            # P_post = P_prior * R / (P_prior + R) = R * K.
            gain = estimate_result.state_sd_log**2 / token_variance
            if not math.isfinite(gain) or not 0 <= gain <= 1:
                raise ValueError("runtime produced an invalid token assimilation gain")
            gains.append(gain)
        m = estimate_result.state_m_after_nvda
        p = estimate_result.state_P_after_nvda
        timestamp = snapshot.observation_ts
    return {
        "n_token_observations": len(gains),
        "mean_gain": mean(gains) if gains else None,
        "median_gain": median(gains) if gains else None,
        "max_gain": max(gains) if gains else None,
        "method": "posterior_log_variance_divided_by_fitted_token_measurement_variance",
    }


def _challenger_estimate_sequence(
    snapshots: list[Any],
) -> list[ChallengerEstimate]:
    """Return P1a-C estimates with exactly the replay's causal warm state."""
    if not snapshots:
        return []
    state = _warm_state_to_first_observation(snapshots[0])
    estimates: list[ChallengerEstimate] = []
    for snapshot in snapshots:
        result = estimate(
            snapshot,
            state.m if state else None,
            state.P if state else None,
            state.last_ts if state else None,
        )
        estimates.append(result)
        state = KalmanState(
            m=result.state_m_after_nvda,
            P=result.state_P_after_nvda,
            last_ts=snapshot.observation_ts,
        )
    return estimates


def _average_precision(scores: list[float], labels: list[bool]) -> float | None:
    pairs = sorted(enumerate(zip(scores, labels, strict=True)), key=lambda pair: -pair[1][0])
    positive_count = sum(labels)
    if positive_count == 0:
        return None
    true_positives = 0
    accumulated_precision = 0.0
    for rank, (_index, (_score, label)) in enumerate(pairs, start=1):
        if label:
            true_positives += 1
            accumulated_precision += true_positives / rank
    return accumulated_precision / positive_count


def _confusion(predicted: list[bool], actual: list[bool]) -> dict[str, Any]:
    tp = sum(pred and truth for pred, truth in zip(predicted, actual, strict=True))
    fp = sum(pred and not truth for pred, truth in zip(predicted, actual, strict=True))
    fn = sum(not pred and truth for pred, truth in zip(predicted, actual, strict=True))
    tn = sum(not pred and not truth for pred, truth in zip(predicted, actual, strict=True))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_challenge_rate": fp / (fp + tn) if fp + tn else None,
        "missed_tail_rate": fn / (tp + fn) if tp + fn else None,
    }


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    location = (len(ordered) - 1) * probability
    lower = math.floor(location)
    upper = math.ceil(location)
    if lower == upper:
        return ordered[lower]
    fraction = location - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _frozen_detector_metrics(
    asset: str,
    snapshots: list[Any],
    estimates: list[ChallengerEstimate],
) -> dict[str, Any]:
    spec = resolve_challenger_detector(asset)
    if spec is None:
        raise ValueError(f"no frozen challenger detector is registered for {asset}")
    artifact = detector_artifact()
    artifact_entry = artifact["assets"][asset]
    detector_rows: list[dict[str, Any]] = []
    session_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    corroboration = Counter()

    for snapshot, p1a in zip(snapshots, estimates, strict=True):
        score = detector_score(spec, snapshot.token_price, p1a)
        if score is None:
            continue
        band = detector_band(spec, score)
        contemporaneous_underlying = (
            snapshot.underlying_reference
            if snapshot.underlying_reference_ts == snapshot.observation_ts
            else None
        )
        token_log = math.log(snapshot.token_price) if snapshot.token_price else None
        p1a_row: dict[str, Any] = {
            "score": score,
            "band": band,
            "session": snapshot.market_state.value,
            "token_log": token_log,
            "p1a_log": p1a.state_m,
            "truth_log": (
                math.log(contemporaneous_underlying)
                if contemporaneous_underlying is not None
                else None
            ),
            "xperp_log": None,
            "tail_event": None,
        }
        xperp = snapshot.xperp_index_price
        xperp_ts = snapshot.xperp_index_ts
        if (
            xperp is None
            and snapshot.reference_under_test_source == "okx_xperp_index"
        ):
            xperp = snapshot.reference_under_test
            xperp_ts = snapshot.reference_under_test_ts
        if xperp is not None and xperp_ts == snapshot.observation_ts and xperp > 0:
            p1a_row["xperp_log"] = math.log(xperp)

        if p1a_row["truth_log"] is not None and token_log is not None:
            raw_error_bps = abs(token_log - p1a_row["truth_log"]) * 10_000
            p1a_error_bps = abs(p1a.state_m - p1a_row["truth_log"]) * 10_000
            p1a_row.update(
                {
                    "raw_error_bps": raw_error_bps,
                    "p1a_error_bps": p1a_error_bps,
                    "p1a_better": p1a_error_bps < raw_error_bps,
                    "tail_event": raw_error_bps >= spec.tail_event_threshold_bps,
                }
            )
        detector_rows.append(p1a_row)
        session_rows[p1a_row["session"]].append(p1a_row)

        if band == "review":
            if p1a_row["xperp_log"] is None:
                corroboration["review_without_exact_xperp"] += 1
            else:
                corroboration["review_with_exact_xperp"] += 1
                challenger_gap = abs(p1a_row["xperp_log"] - p1a.state_m)
                xstock_gap = abs(p1a_row["xperp_log"] - token_log)
                if challenger_gap < xstock_gap:
                    corroboration["review_xperp_closer_to_p1a"] += 1
                elif xstock_gap < challenger_gap:
                    corroboration["review_xperp_closer_to_xstock"] += 1
                else:
                    corroboration["review_equal_distance"] += 1
        if p1a_row["truth_log"] is not None and p1a_row["xperp_log"] is not None:
            truth_log = p1a_row["truth_log"]
            token_error = abs(token_log - truth_log)
            xperp_error = abs(p1a_row["xperp_log"] - truth_log)
            corroboration[
                "xperp_closer_to_underlying_than_xstock"
                if xperp_error < token_error
                else "xperp_not_closer_to_underlying_than_xstock"
            ] += 1

    eligible = [row for row in detector_rows if row["tail_event"] is not None]
    labels = [bool(row["tail_event"]) for row in eligible]
    scores = [float(row["score"]) for row in eligible]
    q95_flags = [row["score"] >= spec.threshold_challenge for row in eligible]
    all_scores = [float(row["score"]) for row in detector_rows]
    all_bands = Counter(row["band"] for row in detector_rows)

    def session_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        evaluated = [row for row in rows if row["tail_event"] is not None]
        labels_by_session = [bool(row["tail_event"]) for row in evaluated]
        scores_by_session = [float(row["score"]) for row in evaluated]
        q95_by_session = [row["score"] >= spec.threshold_challenge for row in evaluated]
        counts = Counter(row["band"] for row in rows)
        return {
            "score_rows": len(rows),
            "underlying_evaluable_rows": len(evaluated),
            "research_band_counts": dict(sorted(counts.items())),
            "tail_event_count": sum(labels_by_session),
            "tail_event_prevalence": (
                sum(labels_by_session) / len(labels_by_session) if labels_by_session else None
            ),
            "q95_detection": _confusion(q95_by_session, labels_by_session),
            "continuous_score_average_precision": _average_precision(
                scores_by_session, labels_by_session
            ),
        }

    return {
        "artifact_version": spec.artifact_version,
        "artifact_sha256": hashlib.sha256(
            resources.files("valtide_api.detectors")
            .joinpath("challenger_tail_v1.json")
            .read_bytes()
        ).hexdigest(),
        "promotion_status": spec.promotion_status,
        "score_name": spec.score_name,
        "score_definition": artifact["score_definitions"][spec.score_name],
        "threshold_review_q80": spec.threshold_review,
        "threshold_challenge_q95": spec.threshold_challenge,
        "training_tail_event_threshold_bps": spec.tail_event_threshold_bps,
        "original_oof_training_rows": artifact_entry["training_rows"],
        "research_status_mapping": artifact["research_bands"],
        "canonical_rows": len(snapshots),
        "rows_with_token": sum(snapshot.token_price is not None for snapshot in snapshots),
        "rows_with_contemporaneous_underlying": sum(
            snapshot.underlying_reference is not None
            and snapshot.underlying_reference_ts == snapshot.observation_ts
            for snapshot in snapshots
        ),
        "rows_with_p1a_output": len(estimates),
        "rows_eligible_for_score": len(detector_rows),
        "research_band_counts": dict(sorted(all_bands.items())),
        "research_band_rates": {
            band: all_bands.get(band, 0) / len(detector_rows) if detector_rows else None
            for band in ("support", "watch", "review")
        },
        "score_distribution": {
            "n": len(all_scores),
            "min": min(all_scores) if all_scores else None,
            "q50": _quantile(all_scores, 0.50),
            "q90": _quantile(all_scores, 0.90),
            "q95": _quantile(all_scores, 0.95),
            "max": max(all_scores) if all_scores else None,
        },
        "underlying_tail_event": {
            "definition": artifact["tail_event_definition"],
            "evaluable_rows": len(eligible),
            "event_count": sum(labels),
            "prevalence": sum(labels) / len(labels) if labels else None,
            "q95_threshold_detection": _confusion(q95_flags, labels),
            "continuous_score_average_precision": _average_precision(scores, labels),
            "p1a_closer_rate": (
                sum(bool(row["p1a_better"]) for row in eligible)
                / len(eligible)
                if eligible
                else None
            ),
        },
        "xperp_diagnostics": {
            "definition": (
                "Descriptive exact-timestamp distance comparisons only; no X-Perp residual "
                "z-score or fitted threshold is used."
            ),
            "counts": dict(sorted(corroboration.items())),
        },
        "session_breakdown": {
            session: session_summary(rows)
            for session, rows in sorted(session_rows.items())
        },
        "decision_limitations": artifact_entry["promotion_rationale"],
    }


def evaluate_panel(asset: str, path: str | Path) -> dict[str, Any]:
    """Verify one panel and replay it using the registered frozen runtime."""
    if asset not in _EXPECTED_ASSETS or asset not in supported_asset_names():
        raise ValueError(f"unsupported evaluation asset: {asset}")
    panel_path = Path(path).expanduser().resolve(strict=True)
    settings = _pinned_settings(asset)
    readiness = inspect_panel_readiness(panel_path, asset=asset, settings=settings)
    if not readiness.canonical_identity_verified or not readiness.replay_compatible:
        raise ValueError(
            f"{asset} panel is not verified/replay-ready "
            f"(schema={readiness.schema}, code={readiness.error_code})"
        )
    rows = _load_rows(panel_path)
    snapshots = load_panel_snapshots(panel_path, asset=asset, settings=settings)
    if not snapshots:
        raise ValueError(f"{asset} panel has no replay observations")
    results = replay(snapshots)
    if len(results) != len(snapshots):
        raise RuntimeError("replay result count does not match validated observations")
    challenger_estimates = _challenger_estimate_sequence(snapshots)
    frozen_detector = _frozen_detector_metrics(asset, snapshots, challenger_estimates)

    config = resolve_asset_config(asset, settings)
    runtime = resolve_quant_runtime(config)
    model_ids = {result.model_id for result in results}
    model_versions = {result.model_version for result in results}
    calibrations = Counter(result.interval_calibration_type for result in results)

    evaluable = [
        (snapshot, result)
        for snapshot, result in zip(snapshots, results, strict=True)
        if snapshot.underlying_reference is not None
        and snapshot.token_price is not None
    ]
    model_errors = [
        result.valtide_fair_value - snapshot.underlying_reference
        for snapshot, result in evaluable
        if snapshot.underlying_reference is not None
    ]
    raw_errors = [
        snapshot.token_price - snapshot.underlying_reference
        for snapshot, _result in evaluable
        if snapshot.token_price is not None and snapshot.underlying_reference is not None
    ]
    model_errors_bps = [
        error / snapshot.underlying_reference * 10_000
        for (snapshot, _result), error in zip(evaluable, model_errors, strict=True)
        if snapshot.underlying_reference is not None
    ]
    raw_errors_bps = [
        error / snapshot.underlying_reference * 10_000
        for (snapshot, _result), error in zip(evaluable, raw_errors, strict=True)
        if snapshot.underlying_reference is not None
    ]

    coverage: list[bool] = []
    widths: list[float] = []
    interval_scores: list[float] = []
    for snapshot, result in evaluable:
        assert snapshot.underlying_reference is not None
        truth = snapshot.underlying_reference
        coverage.append(result.fair_value_lower <= truth <= result.fair_value_upper)
        widths.append(result.fair_value_upper - result.fair_value_lower)
        alpha = 1 - result.interval_coverage_target
        if alpha <= 0:
            raise ValueError("runtime interval coverage target must be below 1")
        interval_scores.append(
            widths[-1]
            + 2 / alpha * max(result.fair_value_lower - truth, 0)
            + 2 / alpha * max(truth - result.fair_value_upper, 0)
        )

    token_count = sum((row.get("token_available") or "").strip().upper() in {"TRUE", "T", "1"} for row in rows)
    underlying_count = sum((row.get("underlying_available") or "").strip().upper() in {"TRUE", "T", "1"} for row in rows)
    reference_count = sum(
        (row.get("reference_under_test_available") or "").strip().upper() in {"TRUE", "T", "1"}
        for row in rows
    )
    states = Counter(result.evidence_state.value for result in results)
    reasons = Counter(code for result in results for code in result.reason_codes)

    return {
        "asset": asset,
        "panel": {
            "path": str(panel_path),
            "sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
            "schema": readiness.schema,
            "canonical_identity_verified": readiness.canonical_identity_verified,
            "replay_compatible": readiness.replay_compatible,
            "input_rows": len(rows),
            "replay_observations": len(snapshots),
            "window_start_utc": snapshots[0].observation_ts.isoformat(),
            "window_end_utc": snapshots[-1].observation_ts.isoformat(),
        },
        "identity": {
            "token_source": config.token_source,
            "chain_index": config.okx_chain_index,
            "token_address": config.token_address,
            "underlying_symbol": config.underlying_symbol,
            "reference_source": config.reference_under_test_source,
            "reference_instrument": config.reference_under_test_instrument,
        },
        "runtime": {
            "runtime_key": config.quant_runtime_key,
            "model_id": next(iter(model_ids)) if len(model_ids) == 1 else None,
            "model_version": next(iter(model_versions)) if len(model_versions) == 1 else None,
            "registered_model_id": runtime.model_id,
            "registered_model_version": runtime.model_version,
            "calibration_type_counts": dict(sorted(calibrations.items())),
        },
        "source_counts": {
            "xstock": token_count,
            "underlying": underlying_count,
            "xperp_index": reference_count,
            "missing_xstock": len(rows) - token_count,
            "missing_underlying": len(rows) - underlying_count,
            "missing_xperp_index": len(rows) - reference_count,
        },
        "market_state_counts": dict(sorted(Counter(s.market_state.value for s in snapshots).items())),
        "token_update_weight": _token_update_weight(asset, snapshots),
        "n_evaluable": len(evaluable),
        "model_vs_underlying": {
            **_mae_rmse(model_errors),
            "mae_bps": _mae_rmse(model_errors_bps)["mae"],
            "rmse_bps": _mae_rmse(model_errors_bps)["rmse"],
        },
        "raw_xstock_vs_underlying": {
            **_mae_rmse(raw_errors),
            "mae_bps": _mae_rmse(raw_errors_bps)["mae"],
            "rmse_bps": _mae_rmse(raw_errors_bps)["rmse"],
        },
        "interval": {
            "n": len(coverage),
            "coverage": sum(coverage) / len(coverage) if coverage else None,
            "mean_width": _mean(widths),
            "mean_interval_score": _mean(interval_scores),
            "nominal_coverage": results[0].interval_coverage_target if results else None,
        },
        "evidence_state_counts": dict(sorted(states.items())),
        "reason_code_counts": dict(sorted(reasons.items())),
        "pairwise_diagnostics": _pairwise_diagnostics(snapshots, results),
        "frozen_challenger_detector": frozen_detector,
        "interpretation": {
            "evidence_states": (
                "Current backend abstains with INCONCLUSIVE for the registered OKX X-Perp/index "
                "because P1a-C predictive uncertainty is not calibrated for X-Perp residuals. "
                "Pairwise xStock/P1a-C and xStock/X-Perp diagnostics are descriptive and do not "
                "create a newly calibrated combined three-source decision. P1a-C assimilates "
                "xStock, so xStock-vs-model is model-based challenger evidence, not independent-market proof."
            ),
            "evaluation": (
                "Retrospective out-of-fit-period diagnostics only; not prospective validation, "
                "not calibration, and not production-readiness evidence."
            ),
        },
    }


def _parse_panel(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("panel must use ASSET=CSV_PATH")
    asset, path = value.split("=", 1)
    if not asset or not path:
        raise argparse.ArgumentTypeError("panel must use ASSET=CSV_PATH")
    return asset, Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", action="append", type=_parse_panel, required=True)
    parser.add_argument("--output", type=Path, help="write JSON here (default: stdout)")
    args = parser.parse_args(argv)
    panels = dict(args.panel)
    if len(panels) != len(args.panel) or tuple(sorted(panels)) != tuple(sorted(_EXPECTED_ASSETS)):
        parser.error("provide exactly one panel for each of NVDAx, SPYx, QQQx, and AAPLx")
    try:
        result = {
            "evaluation": "canonical_panel_replay_v1",
            "assets": {
                asset: evaluate_panel(asset, panels[asset]) for asset in _EXPECTED_ASSETS
            },
        }
        rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"fresh panel evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
