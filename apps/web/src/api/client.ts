// Typed client for the full Valtide backend contract. Operational, historical,
// and scenario lanes are explicit so a degraded source cannot silently become
// another kind of evidence. A static fixture backs Demo mode only.
//
// Endpoint map (FastAPI, apps/api):
//   GET  /health
//   GET  /api/valuation/{asset}         persisted/warmed result (503 on cold cache)
//   GET  /api/valuation/{asset}/live    one-off cold-start diagnostic
//   GET  /api/history/{asset}?limit=N   successful warmed operational history
//   GET  /api/replay/{asset}?source=panel historical panel sequence
//   GET  /api/replay/{asset}?source=scenario deterministic demo sequence
//   GET  /api/backtest/{asset}?source=historical historical diagnostics
//   GET  /api/runtime/{asset}           warmed scheduler status
//   GET  /api/onchain/{asset}           X Layer Registry / RiskGuard state
//   GET  /api/onchain/{asset}/enforcement DemoVault read-only enforcement check

import type {
  AssetInfo,
  BacktestMetrics,
  OnchainControlPlane,
  OnchainEnforcement,
  RuntimeStatus,
  ValuationResult,
} from "./types";
import weekendDivergence from "../fixtures/weekend_divergence.json";

export const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const ASSET = "NVDAx";

const FIXTURE = weekendDivergence as unknown as ValuationResult[];

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

async function getJSON<T>(path: string, timeoutMs = 6000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json())?.detail ?? detail;
      } catch {
        /* non-JSON body */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

async function getJSONWithHeaders<T>(path: string, timeoutMs = 12000): Promise<{ data: T; headers: Headers }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json())?.detail ?? detail;
      } catch {
        /* non-JSON body */
      }
      throw new ApiError(res.status, detail);
    }
    return { data: (await res.json()) as T, headers: res.headers };
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchHealth(): Promise<boolean> {
  try {
    await getJSON<{ status: string }>("/health", 2500);
    return true;
  } catch {
    return false;
  }
}

/** On-demand cold-start inference; it is diagnostic and does not warm/publish state. */
export function fetchLiveDiagnostic(): Promise<ValuationResult> {
  return getJSON<ValuationResult>(`/api/valuation/${ASSET}/live`, 12000);
}

/** Latest persisted/warmed operational result (never advances the filter). */
export function fetchOperationalValuation(): Promise<ValuationResult> {
  return getJSON<ValuationResult>(`/api/valuation/${ASSET}`);
}

export function fetchRuntime(): Promise<RuntimeStatus> {
  return getJSON<RuntimeStatus>(`/api/runtime/${ASSET}`);
}

export function fetchAssets(): Promise<AssetInfo[]> {
  return getJSON<AssetInfo[]>("/api/assets");
}

/** Successful warmed scheduler observations only; never replay/backtest data. */
export function fetchOperationalHistory(limit = 72): Promise<ValuationResult[]> {
  return getJSON<ValuationResult[]>(`/api/history/${ASSET}?limit=${limit}`, 10000);
}

export interface HistoricalReplayResponse {
  results: ValuationResult[];
  source: "historical_panel";
}

/** Historical panel replay. A scenario response is rejected rather than substituted. */
export async function fetchHistoricalReplay(): Promise<HistoricalReplayResponse> {
  const response = await getJSONWithHeaders<ValuationResult[]>(`/api/replay/${ASSET}?source=panel`, 20000);
  const source = response.headers.get("X-Valtide-Source");
  // The backend path is explicit. If CORS does not expose the diagnostic header,
  // the browser returns null; reject only an explicitly conflicting source.
  if (source != null && source !== "historical_panel") {
    throw new Error(`Unexpected replay source: ${source ?? "missing"}`);
  }
  if (!Array.isArray(response.data) || response.data.length === 0) {
    throw new Error("Historical panel replay is empty");
  }
  return { results: response.data, source: "historical_panel" };
}

export function fetchHistoricalBacktest(): Promise<BacktestMetrics> {
  return getJSON<BacktestMetrics>(`/api/backtest/${ASSET}?source=historical`);
}

export function fetchOnchain(): Promise<OnchainControlPlane> {
  return getJSON<OnchainControlPlane>(`/api/onchain/${ASSET}`, 12000);
}

export function fetchOnchainEnforcement(): Promise<OnchainEnforcement> {
  return getJSON<OnchainEnforcement>(`/api/onchain/${ASSET}/enforcement`, 12000);
}

export type ReplaySource = "backend-scenario" | "offline-fixture";
export interface ReplayResponse {
  results: ValuationResult[];
  source: ReplaySource;
}

/**
 * Demo replay sequence. Tries the live backend first; on any failure falls back
 * to the bundled fixture and reports which source was used.
 */
export async function fetchDemoReplay(scenario = "weekend_divergence"): Promise<ReplayResponse> {
  try {
    const results = await getJSON<ValuationResult[]>(
      `/api/replay/${ASSET}?source=scenario&scenario=${encodeURIComponent(scenario)}`,
    );
    if (!Array.isArray(results) || results.length === 0) throw new Error("empty replay");
    return { results: densifyDemoResults(results), source: "backend-scenario" };
  } catch {
    return { results: densifyDemoResults(FIXTURE), source: "offline-fixture" };
  }
}

/**
 * Adds one-minute presentation frames between the backend-owned five-minute
 * scenario anchors. This is used only in the explicitly labelled demo lane;
 * operational history is never interpolated.
 */
function densifyDemoResults(anchors: ValuationResult[], subdivisions = 5): ValuationResult[] {
  if (anchors.length < 2 || subdivisions < 2) return anchors;
  const frames: ValuationResult[] = [];

  for (let anchorIndex = 0; anchorIndex < anchors.length - 1; anchorIndex += 1) {
    const from = anchors[anchorIndex];
    const to = anchors[anchorIndex + 1];
    const fromTs = Date.parse(from.timestamp);
    const toTs = Date.parse(to.timestamp);

    for (let step = 0; step < subdivisions; step += 1) {
      const t = step / subdivisions;
      const timestamp = new Date(fromTs + (toTs - fromTs) * t).toISOString();
      const frame: ValuationResult = {
        ...from,
        timestamp,
        token_observed_at: from.token_observed_at == null ? null : timestamp,
        reference_under_test_ts: from.reference_under_test_ts == null ? null : timestamp,
        token_price: lerpNullable(from.token_price, to.token_price, t),
        token_volume: lerpNullable(from.token_volume, to.token_volume, t),
        token_volume_usd: lerpNullable(from.token_volume_usd, to.token_volume_usd, t),
        token_liquidity_usd: lerpNullable(from.token_liquidity_usd, to.token_liquidity_usd, t),
        external_constructed_reference: lerpNullable(from.external_constructed_reference, to.external_constructed_reference, t),
        valtide_fair_value: lerp(from.valtide_fair_value, to.valtide_fair_value, t),
        fair_value_lower: lerp(from.fair_value_lower, to.fair_value_lower, t),
        fair_value_upper: lerp(from.fair_value_upper, to.fair_value_upper, t),
        observed_token_move_pct: lerpNullable(from.observed_token_move_pct, to.observed_token_move_pct, t),
        model_implied_move_pct: lerp(from.model_implied_move_pct, to.model_implied_move_pct, t),
        residual_premium_discount_pct: lerpNullable(from.residual_premium_discount_pct, to.residual_premium_discount_pct, t),
        reference_under_test: lerpNullable(from.reference_under_test, to.reference_under_test, t),
        reference_under_test_age_seconds: lerpNullable(from.reference_under_test_age_seconds, to.reference_under_test_age_seconds, t),
        reference_deviation_pct: lerpNullable(from.reference_deviation_pct, to.reference_deviation_pct, t),
        standardized_deviation: lerpNullable(from.standardized_deviation, to.standardized_deviation, t),
        reference_age_seconds: Math.round(lerp(from.reference_age_seconds, to.reference_age_seconds, t)),
        source_provenance: { ...(from.source_provenance ?? {}), scenario: "weekend_divergence", presentation: "interpolated_1m" },
      };
      frame.evidence_state = evidenceStateFor(frame);
      frame.reason_codes = demoReasonCodes(frame, from.reason_codes);
      frames.push(frame);
    }
  }

  const last = anchors[anchors.length - 1];
  frames.push({ ...last, source_provenance: { ...(last.source_provenance ?? {}), scenario: "weekend_divergence", presentation: "interpolated_1m" } });
  return frames;
}

function evidenceStateFor(result: ValuationResult): ValuationResult["evidence_state"] {
  if (result.standardized_deviation == null) return "INCONCLUSIVE";
  const magnitude = Math.abs(result.standardized_deviation);
  if (magnitude >= 2) return "CHALLENGED";
  if (magnitude < 1) return "SUPPORTED";
  return "INCONCLUSIVE";
}

function demoReasonCodes(result: ValuationResult, inherited: string[]): string[] {
  const codes = inherited.filter((code) => code !== "REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL" && code !== "TOKEN_AND_CHALLENGER_AGREE");
  if (result.reference_under_test != null && (result.reference_under_test < result.fair_value_lower || result.reference_under_test > result.fair_value_upper)) codes.push("REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL");
  if (result.token_price != null && Math.abs(result.token_price - result.valtide_fair_value) / result.valtide_fair_value < 0.01) codes.push("TOKEN_AND_CHALLENGER_AGREE");
  return [...new Set(codes)];
}

function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * t;
}

function lerpNullable(from: number | null | undefined, to: number | null | undefined, t: number): number | null {
  if (from == null || to == null) return null;
  return lerp(from, to, t);
}
