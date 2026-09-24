// Mirrors apps/api/valtide_api/models.py. Keep in sync with /docs on the backend.

export type EvidenceState = "SUPPORTED" | "INCONCLUSIVE" | "CHALLENGED";

export interface ValuationResult {
  asset: string;
  timestamp: string; // ISO UTC
  market_state: string;

  last_trusted_reference: number;
  token_price: number | null;
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
  reference_under_test_ts: string | null;
  reference_under_test_age_seconds: number | null;
  reference_deviation_pct: number | null;
  standardized_deviation: number | null;

  evidence_state: EvidenceState;
  reason_codes: string[];

  confidence: number | null;
  model_id: string;
  model_version: string;
  interval_semantics: string;
  interval_calibration_type: string;
  interval_calibration_source: string;
  reference_age_seconds: number;
}

export interface AssetInfo {
  asset: string;
  token_source: string;
  underlying_source: string;
  model_available: boolean;
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
}
