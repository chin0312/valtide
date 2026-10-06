import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from quant.tools.evaluate_fresh_panels import (
    _update_evidence_manifest,
    evaluate_panel,
)

from valtide_api.assets import resolve_asset_config
from valtide_api.challenger_detector import tri_source_capability_artifact
from valtide_api.config import Settings


def _iso(timestamp):
    return timestamp.isoformat().replace("+00:00", "Z")


def _write_asset_panel(path, asset="SPYx"):
    config = resolve_asset_config(asset, Settings(_env_file=None))
    header = (
        "timestamp_utc,asset,underlying_symbol,token_source,token_chain_index,"
        "token_address,reference_under_test_instrument,session_state,token_close,"
        "token_volume,token_volume_usd,token_available,token_observed_at,"
        "underlying_close,underlying_available,underlying_observed_at,"
        "last_trusted_reference,last_trusted_reference_ts,reference_under_test,"
        "reference_under_test_available,reference_under_test_source,"
        "reference_under_test_ts,reference_profile"
    )
    rows = []
    start = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    for index in range(4):
        timestamp = start + timedelta(minutes=5 * index)
        underlying = 500.0 + index * 0.1
        token = 500.1 + index * 0.1
        reference = 500.2 + index * 0.1
        timestamp_text = _iso(timestamp)
        prior_timestamp_text = _iso(timestamp - timedelta(minutes=5))
        row = (
            f"{timestamp_text},{asset},{config.underlying_symbol},"
            f"okx_onchainos,{config.okx_chain_index},{config.token_address},"
            f"{config.reference_under_test_instrument},"
            f"regular,{token},100,50000,TRUE,{timestamp_text},"
            f"{underlying},TRUE,{timestamp_text},"
            f"{underlying - 0.1},{prior_timestamp_text},"
            f"{reference},TRUE,okx_xperp_index,{timestamp_text},"
            "unified_xstock_p1ac_xperp_evidence_v1"
        )
        rows.append(row)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_fresh_panel_evaluator_uses_verified_asset_runtime_and_real_replay(tmp_path):
    panel = _write_asset_panel(tmp_path / "spyx.csv")

    result = evaluate_panel("SPYx", panel)

    assert result["asset"] == "SPYx"
    assert result["panel"]["canonical_identity_verified"] is True
    assert result["panel"]["replay_compatible"] is True
    assert result["panel"]["input_rows"] == 4
    assert result["panel"]["replay_observations"] == 4
    assert result["identity"]["chain_index"] == "501"
    assert result["identity"]["token_address"] == (
        "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"
    )
    assert result["runtime"]["model_id"] == "P1a-C"
    assert result["runtime"]["model_version"] == "0.3.0"
    assert result["source_counts"]["xperp_index"] == 4
    assert result["token_update_weight"]["n_token_observations"] == 4
    assert 0 <= result["token_update_weight"]["max_gain"] <= 1
    assert result["n_evaluable"] == 4
    assert sum(result["evidence_state_counts"].values()) == 4
    assert "not Gaussian-calibrated" in result["interpretation"]["evidence_states"]
    assert "not independent-market proof" in result["interpretation"]["evidence_states"]
    detector = result["frozen_challenger_detector"]
    assert detector["promotion_status"] == "CHALLENGER_DETECTOR_PROMOTABLE"
    assert detector["canonical_rows"] == 4
    assert detector["rows_eligible_for_score"] == 4
    assert detector["rows_with_contemporaneous_underlying"] == 4
    assert detector["underlying_tail_event"]["evaluable_rows"] == 4
    assert sum(detector["research_band_counts"].values()) == 4
    assert detector["threshold_challenge_q95"] > detector["threshold_review_q80"]
    tri = detector["tri_source_state_candidates"]
    assert tri["tri_source_supported"]["count"] >= tri[
        "tri_source_supported"
    ]["evaluable_count"]
    assert tri["tri_source_challenged"]["count"] >= tri[
        "tri_source_challenged"
    ]["candidate_truth_evaluable_count"]
    assert tri["overall_tail_prevalence"] is not None
    assert "tri_source_supported" in detector["session_breakdown"]["regular"]
    state_distribution = result["tri_source_state_distribution"]
    assert state_distribution["total"] == 4
    assert sum(state_distribution["counts"].values()) == 4
    assert state_distribution["tri_source_inconclusive"]["count"] == result[
        "evidence_state_counts"
    ].get("INCONCLUSIVE", 0)
    assert state_distribution["session_breakdown"]["regular"]["count"] == 4
    repeated = evaluate_panel("SPYx", panel)
    assert repeated["frozen_challenger_detector"] == detector
    assert repeated["tri_source_state_distribution"] == state_distribution


def test_qqqx_remains_available_to_offline_research_evaluator(tmp_path):
    panel = _write_asset_panel(tmp_path / "qqqx.csv", asset="QQQx")

    result = evaluate_panel("QQQx", panel)

    assert result["asset"] == "QQQx"
    assert result["identity"]["underlying_symbol"] == "QQQ"
    assert result["panel"]["canonical_identity_verified"] is True
    tri = result["frozen_challenger_detector"]["tri_source_state_candidates"]
    assert tri["production_capability"]["status"] == (
        "research_only_no_production_state_capability"
    )


def test_frozen_detector_config_matches_retained_research_hashes_and_thresholds():
    repo_root = Path(__file__).resolve().parents[3]
    artifact_path = (
        repo_root
        / "apps/api/valtide_api/detectors/challenger_tail_v1.json"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    for asset, checksums in artifact["source_checksums"].items():
        entry = artifact["assets"][asset]
        slug = asset.lower()
        report = json.loads(
            (repo_root / "quant/research/challenger/results" / slug / "challenger_tail_report.json")
            .read_text(encoding="utf-8")
        )
        assert entry["score_name"] == report["selected_score"]
        assert entry["threshold_review_q80"] == report["score_q80_from_crossfit"]
        assert entry["threshold_challenge_q95"] == report["score_q95_from_crossfit"]
        assert entry["tail_event_threshold_bps"] == report[
            "relative_tail_threshold_bps_from_crossfit"
        ]
        for source_path, expected_hash in checksums.items():
            actual_hash = hashlib.sha256((repo_root / source_path).read_bytes()).hexdigest()
            assert actual_hash == expected_hash

    assert artifact["fresh_validation"]["period_start_utc"] == "2026-09-21T00:00:00Z"
    assert artifact["fresh_validation"]["period_end_utc"] == "2026-10-05T06:25:00Z"


def test_committed_fresh_detector_evidence_is_machine_readable_and_asset_bound():
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads(
        (repo_root / "quant/data_manifest/fresh_validation_20261005.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["period_start_utc"] == "2026-09-21T00:00:00Z"
    assert manifest["period_end_utc"] == "2026-10-05T06:25:00Z"
    assert "not prospective validation or a guarantee" in manifest["purpose"]
    for asset in ("NVDAx", "SPYx", "QQQx", "AAPLx"):
        record = manifest["assets"][asset]
        assert len(record["panel_sha256"]) == 64
        detector = record["frozen_challenger_detector"]
        assert detector["canonical_rows"] == manifest["row_count_per_asset"]
        assert detector["threshold_review_q80"] < detector["threshold_challenge_q95"]
        assert detector["underlying_tail_event"]["evaluable_rows"] == record[
            "underlying_evaluable_rows"
        ]
        assert "q95_threshold_detection" in detector["underlying_tail_event"]
        assert "session_breakdown" in detector
        assert "xperp_diagnostics" in detector

    spy = manifest["assets"]["SPYx"]
    confusion = spy["frozen_challenger_detector"]["underlying_tail_event"][
        "q95_threshold_detection"
    ]
    assert (confusion["tp"], confusion["fp"], confusion["fn"], confusion["tn"]) == (
        20,
        0,
        1,
        812,
    )
    assert confusion["precision"] == 1.0
    assert confusion["recall"] == pytest.approx(20 / 21)
    assert spy["evidence_state_counts"] == {
        "CHALLENGED": 71,
        "INCONCLUSIVE": 1838,
        "SUPPORTED": 2201,
    }
    assert spy["frozen_challenger_detector"]["xperp_diagnostics"]["counts"][
        "review_xperp_closer_to_p1a"
    ] == 71

    nvda = manifest["assets"]["NVDAx"]
    assert nvda["evidence_state_counts"] == {
        "CHALLENGED": 60,
        "INCONCLUSIVE": 2228,
        "SUPPORTED": 1822,
    }
    nvda_challenge = nvda["frozen_challenger_detector"][
        "tri_source_state_candidates"
    ]["tri_source_challenged"]
    assert (nvda_challenge["count"], nvda_challenge["candidate_truth_evaluable_count"]) == (
        60,
        6,
    )
    assert (nvda_challenge["tp"], nvda_challenge["fp"]) == (5, 1)
    assert nvda_challenge["precision"] == pytest.approx(5 / 6)
    assert nvda_challenge["recall"] == pytest.approx(5 / 29)

    aapl = manifest["assets"]["AAPLx"]
    assert aapl["evidence_state_counts"] == {
        "CHALLENGED": 7,
        "INCONCLUSIVE": 1915,
        "SUPPORTED": 2188,
    }
    aapl_challenge = aapl["frozen_challenger_detector"][
        "tri_source_state_candidates"
    ]["tri_source_challenged"]
    assert (aapl_challenge["count"], aapl_challenge["candidate_truth_evaluable_count"]) == (
        7,
        4,
    )
    assert (aapl_challenge["tp"], aapl_challenge["fp"]) == (4, 0)
    assert "three remaining candidates have no ex-post truth label" in (
        tri_source_capability_artifact()["assets"]["AAPLx"]["challenge"]["rationale"]
    )


def test_tri_source_capabilities_bind_only_production_assets_to_exact_fresh_panels():
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads(
        (repo_root / "quant" / "data_manifest" / "fresh_validation_20261005.json").read_text()
    )
    artifact = tri_source_capability_artifact()

    assert artifact["validation_dataset_id"] == manifest["dataset_id"]
    assert artifact["evaluation_kind"] == "retrospective_frozen_threshold_diagnostic"
    assert set(artifact["assets"]) == {"NVDAx", "SPYx", "AAPLx"}
    for asset, capability in artifact["assets"].items():
        assert capability["panel_sha256"] == manifest["assets"][asset]["panel_sha256"]

    assert artifact["assets"]["NVDAx"]["support"]["enabled"] is True
    assert artifact["assets"]["NVDAx"]["challenge"]["enabled"] is True
    assert artifact["assets"]["SPYx"]["challenge"]["enabled"] is True
    assert artifact["assets"]["AAPLx"]["challenge"]["enabled"] is True
    for asset in ("NVDAx", "SPYx", "AAPLx"):
        assert artifact["assets"][asset]["support"]["enabled"] is True
        assert artifact["assets"][asset]["challenge"]["enabled"] is True
    assert artifact["schema"] == "valtide-tri-source-state-capabilities-v2"
    assert artifact["evidence_semantics"] == (
        "p1a_xstock_band_with_xperp_review_corroboration_v2"
    )
    assert all(
        artifact["assets"][asset]["support"]["rule"]
        == "frozen_support_band_and_exact_xperp_available"
        for asset in ("NVDAx", "SPYx", "AAPLx")
    )
    assert manifest["reproduction"]["state_capability_artifact_sha256"] == hashlib.sha256(
        (repo_root / "apps/api/valtide_api/detectors/tri_source_capabilities_v1.json").read_bytes()
    ).hexdigest()
    assert manifest["reproduction"]["evaluator_source_sha256"] == hashlib.sha256(
        (repo_root / "quant/tools/evaluate_fresh_panels.py").read_bytes()
    ).hexdigest()
    # These source identities bind the unchanged historical v1 evaluation
    # snapshot. The current backend now runs semantics v2 and must not rewrite
    # that frozen research manifest in this backend-only change.
    for key in (
        "validation_source_sha256",
        "challenger_detector_source_sha256",
    ):
        value = manifest["reproduction"][key]
        assert len(value) == 64
        assert all(character in "0123456789abcdef" for character in value)
    assert manifest["reproduction"]["validation_source_sha256"] != hashlib.sha256(
        (repo_root / "apps/api/valtide_api/validation.py").read_bytes()
    ).hexdigest()


def test_frozen_panel_aggregates_imply_expected_v2_state_totals():
    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads(
        (repo_root / "quant/data_manifest/fresh_validation_20261005.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        "NVDAx": {"SUPPORTED": 3731, "INCONCLUSIVE": 319, "CHALLENGED": 60},
        "SPYx": {"SUPPORTED": 4009, "INCONCLUSIVE": 30, "CHALLENGED": 71},
        "AAPLx": {"SUPPORTED": 4001, "INCONCLUSIVE": 102, "CHALLENGED": 7},
    }
    # The canonical CSV bytes are external to this repository. This arithmetic
    # derives state totals only from their committed, panel-hash-bound frozen
    # band and exact-time X-Perp aggregates; it is not a row-level replay.
    for asset, expected_counts in expected.items():
        record = manifest["assets"][asset]
        detector = record["frozen_challenger_detector"]
        bands = detector["research_band_counts"]
        relations = detector["xperp_diagnostics"]["counts"]
        supported = relations["support_with_exact_xperp"]
        challenged = relations["review_xperp_closer_to_p1a"]
        unscored = manifest["row_count_per_asset"] - sum(bands.values())
        distribution = {
            "SUPPORTED": supported,
            "INCONCLUSIVE": unscored + bands["watch"] + bands["review"] - challenged,
            "CHALLENGED": challenged,
        }
        assert supported == bands["support"]
        assert challenged <= bands["review"]
        assert distribution == expected_counts


def test_evidence_manifest_refresh_is_sha_guarded_and_deterministic(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    source = json.loads(
        (repo_root / "quant" / "data_manifest" / "fresh_validation_20261005.json").read_text()
    )
    manifest_path = tmp_path / "fresh_validation.json"
    manifest_path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    evaluated_assets = {}
    for asset, record in source["assets"].items():
        evaluated_assets[asset] = {
            "panel": {
                "sha256": record["panel_sha256"],
                "input_rows": source["row_count_per_asset"],
                "window_start_utc": "2026-09-21T00:00:00+00:00",
                "window_end_utc": "2026-10-05T06:25:00+00:00",
            },
            "identity": {
                "token_source": "okx_onchainos",
                "reference_source": "okx_xperp_index",
                "chain_index": record["chain_index"],
                "token_address": record["token_address"],
                "underlying_symbol": record["underlying_symbol"],
                "reference_instrument": record["reference_instrument"],
            },
            "runtime": {
                "model_id": "P1a-C",
                "registered_model_id": "P1a-C",
                "model_version": record["model_version"],
                "registered_model_version": record["model_version"],
            },
            "evidence_state_counts": {"INCONCLUSIVE": source["row_count_per_asset"]},
            "reason_code_counts": {},
            "frozen_challenger_detector": {},
            "tri_source_state_distribution": {},
        }
    result = {"assets": evaluated_assets}
    wrong_sha_result = json.loads(json.dumps(result))
    wrong_sha_result["assets"]["SPYx"]["panel"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="panel SHA"):
        _update_evidence_manifest(manifest_path, wrong_sha_result)
    before = manifest_path.read_bytes()

    _update_evidence_manifest(manifest_path, result)
    first = manifest_path.read_bytes()
    _update_evidence_manifest(manifest_path, result)
    assert manifest_path.read_bytes() == first
    assert before != first


def test_fresh_panel_evaluator_rejects_cross_asset_panel(tmp_path):
    panel = _write_asset_panel(tmp_path / "spyx.csv")

    with pytest.raises(ValueError, match="not verified/replay-ready"):
        evaluate_panel("QQQx", panel)
