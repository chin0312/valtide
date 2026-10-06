"""Load James's frozen, asset-specific challenger-tail detector thresholds."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from valtide_api.models import ChallengerDetectorEvidence, ChallengerEstimate

_ARTIFACT_NAME = "challenger_tail_v1.json"
_CAPABILITY_ARTIFACT_NAME = "tri_source_capabilities_v1.json"
_UNIFIED_EVIDENCE_SEMANTICS = "p1a_xstock_challenger_xperp_second_market_v1"


@dataclass(frozen=True)
class ChallengerDetectorSpec:
    asset: str
    score_name: str
    threshold_review: float
    threshold_challenge: float
    tail_event_threshold_bps: float
    promotion_status: str
    artifact_version: str


@dataclass(frozen=True)
class TriSourceStateCapability:
    """Evidence-state authority explicitly enabled for one production asset."""

    asset: str
    support_enabled: bool
    challenge_enabled: bool
    panel_sha256: str
    support_rationale: str
    challenge_rationale: str


@lru_cache(maxsize=1)
def _artifact() -> dict[str, Any]:
    path = resources.files("valtide_api.detectors").joinpath(_ARTIFACT_NAME)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "valtide-challenger-tail-detector-v1":
        raise ValueError("unsupported challenger detector artifact schema")
    return payload


@lru_cache(maxsize=1)
def _capability_artifact() -> dict[str, Any]:
    path = resources.files("valtide_api.detectors").joinpath(_CAPABILITY_ARTIFACT_NAME)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "valtide-tri-source-state-capabilities-v1":
        raise ValueError("unsupported tri-source state capability schema")
    if (
        payload.get("evidence_semantics") != _UNIFIED_EVIDENCE_SEMANTICS
        or payload.get("evaluation_kind") != "retrospective_frozen_threshold_diagnostic"
        or not isinstance(payload.get("validation_dataset_id"), str)
        or not payload["validation_dataset_id"].strip()
    ):
        raise ValueError("invalid tri-source capability provenance")
    detector_path = resources.files("valtide_api.detectors").joinpath(_ARTIFACT_NAME)
    actual_hash = hashlib.sha256(detector_path.read_bytes()).hexdigest()
    if payload.get("frozen_detector_artifact_sha256") != actual_hash:
        raise ValueError("tri-source capabilities do not match the frozen detector artifact")
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


def resolve_tri_source_state_capability(
    asset: str,
) -> TriSourceStateCapability | None:
    """Resolve asset-bound Evidence State authority; absent entries fail closed."""
    entry = _capability_artifact().get("assets", {}).get(asset)
    if not isinstance(entry, dict):
        return None
    panel_sha256 = entry.get("panel_sha256")
    if (
        not isinstance(panel_sha256, str)
        or len(panel_sha256) != 64
        or any(character not in "0123456789abcdef" for character in panel_sha256)
    ):
        raise ValueError(f"invalid tri-source evidence binding for {asset}")

    resolved: dict[str, tuple[bool, str]] = {}
    for name in ("support", "challenge"):
        capability = entry.get(name)
        if not isinstance(capability, dict) or not isinstance(capability.get("enabled"), bool):
            raise ValueError(f"invalid tri-source {name} capability for {asset}")
        enabled = capability["enabled"]
        expected_name = (
            "TRI_SOURCE_SUPPORTED" if name == "support" else "TRI_SOURCE_CHALLENGED"
        ) if enabled else "DISABLED"
        rationale = capability.get("rationale")
        if capability.get("capability") != expected_name or not isinstance(rationale, str):
            raise ValueError(f"invalid tri-source {name} rationale for {asset}")
        if not rationale.strip():
            raise ValueError(f"empty tri-source {name} rationale for {asset}")
        resolved[name] = (enabled, rationale)

    return TriSourceStateCapability(
        asset=asset,
        support_enabled=resolved["support"][0],
        challenge_enabled=resolved["challenge"][0],
        panel_sha256=panel_sha256,
        support_rationale=resolved["support"][1],
        challenge_rationale=resolved["challenge"][1],
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


def tri_source_capability_artifact() -> dict[str, Any]:
    """Return a detached copy of the asset-specific state-capability binding."""
    return json.loads(json.dumps(_capability_artifact()))
