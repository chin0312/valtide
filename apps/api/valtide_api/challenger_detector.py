"""Load James's frozen, asset-specific challenger-tail detector thresholds."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from valtide_api.models import ChallengerDetectorEvidence, ChallengerEstimate

_ARTIFACT_NAME = "challenger_tail_v1.json"


@dataclass(frozen=True)
class ChallengerDetectorSpec:
    asset: str
    score_name: str
    threshold_review: float
    threshold_challenge: float
    tail_event_threshold_bps: float
    promotion_status: str
    artifact_version: str


@lru_cache(maxsize=1)
def _artifact() -> dict[str, Any]:
    path = resources.files("valtide_api.detectors").joinpath(_ARTIFACT_NAME)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "valtide-challenger-tail-detector-v1":
        raise ValueError("unsupported challenger detector artifact schema")
    return payload


def resolve_challenger_detector(asset: str) -> ChallengerDetectorSpec | None:
    """Resolve an explicit per-asset detector; there is no cross-asset fallback."""
    entry = _artifact().get("assets", {}).get(asset)
    if not isinstance(entry, dict):
        return None
    score_name = entry.get("score_name")
    if score_name not in {"disagreement_bps", "disagreement_z"}:
        raise ValueError(f"invalid challenger detector score for {asset}")
    threshold_review = float(entry["threshold_review_q80"])
    threshold_challenge = float(entry["threshold_challenge_q95"])
    tail_threshold = float(entry["tail_event_threshold_bps"])
    if not all(
        math.isfinite(value) and value >= 0
        for value in (threshold_review, threshold_challenge, tail_threshold)
    ) or threshold_review > threshold_challenge:
        raise ValueError(f"invalid challenger detector thresholds for {asset}")
    return ChallengerDetectorSpec(
        asset=asset,
        score_name=score_name,
        threshold_review=threshold_review,
        threshold_challenge=threshold_challenge,
        tail_event_threshold_bps=tail_threshold,
        promotion_status=str(entry["promotion_status"]),
        artifact_version="james-challenger-tail-v1",
    )


def detector_score(
    spec: ChallengerDetectorSpec,
    token_price: float | None,
    estimate: ChallengerEstimate,
) -> float | None:
    """Compute only the score selected and frozen for this asset."""
    if token_price is None or not math.isfinite(token_price) or token_price <= 0:
        return None
    disagreement = abs(math.log(token_price) - estimate.state_m)
    if spec.score_name == "disagreement_bps":
        score = disagreement * 10_000
    else:
        scale = estimate.reference_predictive_sd_log
        if not math.isfinite(scale) or scale <= 0:
            return None
        score = disagreement / scale
    return score if math.isfinite(score) else None


def detector_band(spec: ChallengerDetectorSpec, score: float | None) -> str:
    """Return James's SUPPORT/WATCH/REVIEW research band, not Evidence State."""
    if score is None:
        return "unavailable"
    if score >= spec.threshold_challenge:
        return "review"
    if score >= spec.threshold_review:
        return "watch"
    return "support"


def detector_evidence(
    spec: ChallengerDetectorSpec,
    token_price: float | None,
    estimate: ChallengerEstimate,
) -> ChallengerDetectorEvidence:
    score = detector_score(spec, token_price, estimate)
    return ChallengerDetectorEvidence(
        artifact_version=spec.artifact_version,
        score_name=spec.score_name,
        score=score,
        review_threshold=spec.threshold_review,
        challenge_threshold=spec.threshold_challenge,
        research_band=detector_band(spec, score),
        promotion_status=spec.promotion_status,
    )


def detector_artifact() -> dict[str, Any]:
    """Return a detached copy for offline evaluators and integrity checks."""
    return json.loads(json.dumps(_artifact()))
