// Mirrors apps/api/valtide_api/models.py. Keep in sync with /docs on the backend.

export type EvidenceState = "SUPPORTED" | "INCONCLUSIVE" | "CHALLENGED";
export type PolicyAction = "ALLOW" | "MONITOR" | "REQUIRE_REVIEW" | "RESTRICT_NEW_RISK";

export interface ChallengerDetectorEvidence {
  artifact_version: string;
  score_name: string;
  score: number | null;
  review_threshold: number;
  challenge_threshold: number;
  research_band: string;
  promotion_status: string;
}

export interface ValuationResult {
  asset: string;
  timestamp: string; // ISO UTC
  market_state: string;

  last_trusted_reference: number;
  token_price: number | null;
  token_source: string | null;
  token_observed_at: string | null;
  token_volume: number | null;
  token_volume_usd: number | null;
  token_liquidity_usd: number | null;
  external_constructed_reference: number | null;

  valtide_fair_value: number;
  fair_value_lower: number;
  fair_value_upper: number;
  interval_coverage_target: number;

  observed_token_move_pct: number | null;
  model_implied_move_pct: number;
  residual_premium_discount_pct: number | null;

  reference_under_test: number | null;
  reference_under_test_source: string;
  reference_profile: string;
  reference_under_test_ts: string | null;
  reference_under_test_age_seconds: number | null;
  reference_deviation_pct: number | null;
  standardized_deviation: number | null;
  xperp_index_price: number | null;
  xperp_index_source: string | null;
  xperp_index_ts: string | null;
  xstock_vs_p1ac_deviation_pct: number | null;
  xperp_vs_p1ac_deviation_pct: number | null;
  xstock_vs_xperp_deviation_pct: number | null;
  xperp_deviation_scaled_by_model_predictive_sd: number | null;
  evidence_state_basis: string;
  validation_target: string;
  evidence_semantics: string;
  xperp_role: string;
  challenger_detector: ChallengerDetectorEvidence | null;

  evidence_state: EvidenceState;
  reason_codes: string[];

  confidence: number | null;
  model_id: string;
  model_version: string;
  interval_semantics: string;
  interval_calibration_type: string;
  interval_calibration_source: string;
  reference_age_seconds: number;
  source_provenance: Record<string, string>;
}

export interface AssetInfo {
  asset: string;
  token_source: string;
  underlying_source: string;
  reference_profile: string;
  registered: boolean;
  api_exposed: boolean;
  model_available: boolean;
  quant_artifact_ready: boolean;
  historical_data_available: boolean;
  historical_panel_file_available: boolean;
  canonical_panel_verified: boolean;
  historical_replay_ready: boolean;
  historical_replay_mode: "canonical" | "legacy_diagnostic" | null;
  historical_panel_error_code: string | null;
  challenger_detector_status: string;
  evidence_state_capability: string;
  live_data_configured: boolean;
  live_market_data_available: boolean;
  runtime_ready: boolean;
  operational_ready: boolean;
  operational_scheduler_enabled: boolean;
  latest_observation_timestamp: string | null;
  latest_observation_age_seconds: number | null;
  latest_observation_freshness: "fresh" | "stale" | "unavailable";
  onchain_binding_configured: boolean;
  readiness_error_codes: string[];
}

export interface BacktestMetrics {
  asset: string;
  source: string;
  n_observations: number;
  evidence_state_counts: Record<string, number>;
  n_evaluable: number;
  mae: number | null;
  rmse: number | null;
  interval_coverage: number | null;
  window_start: string | null;
  window_end: string | null;
  model_id: string | null;
  model_version: string | null;
  note: string;
}

export interface RuntimeStatus {
  asset: string;
  scheduler_enabled: boolean;
  has_state: boolean;
  has_live_result: boolean;
  last_state_timestamp: string | null;
  last_result_timestamp: string | null;
  last_tick_status: string | null;
  last_tick_attempt_at: string | null;
  last_error: string | null;
  last_gap_steps: number;
  auto_publish_enabled: boolean;
  last_publish_status: string | null;
  last_publish_attempt_at: string | null;
  last_publish_observation_ts: string | null;
  last_published_observation_ts: string | null;
  last_published_at: number | null;
  last_publish_tx_hash: string | null;
  last_publish_error: string | null;
}

export interface OnchainPolicy {
  max_age: number;
  on_supported: PolicyAction;
  on_inconclusive: PolicyAction;
  on_challenged: PolicyAction;
  on_stale: PolicyAction;
}

export interface OnchainEvaluation {
  evidence_state_code: number;
  evidence_state: EvidenceState;
  policy_action_code: number;
  policy_action: PolicyAction;
  exists: boolean;
  fresh: boolean;
}

export interface OnchainAttestation {
  exists: boolean;
  referenceId: string;
  referencePriceE8: number;
  fairValueE8: number;
  lowerBoundE8: number;
  upperBoundE8: number;
  referenceDeviationBps: number;
  evidenceState: number;
  evidenceHash: string;
  modelVersion: string;
  observedAt: number;
  publishedAt: number;
  validUntil: number;
}

export interface OnchainControlPlane extends OnchainEvaluation {
  asset: string;
  configured: boolean;
  deployed: boolean;
  network: string;
  chain_id: number;
  registry: string;
  risk_guard: string;
  demo_vault: string;
  asset_id: string;
  reference_id: string;
  model_version: string;
  policy: OnchainPolicy;
  attestation: OnchainAttestation | null;
  registry_fresh: boolean;
  publication_compatible?: boolean;
  publication_compatibility_status?: string | null;
}

export interface OnchainEnforcement extends OnchainEvaluation {
  asset: string;
  expected_revert: boolean;
  reverted: boolean;
  returned_action_code: number | null;
  passed: boolean;
}
