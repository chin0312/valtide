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
import consoleWeekendDivergenceV2 from "../fixtures/console_weekend_divergence_v2.json";

export const BASE = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");
export const DEFAULT_ASSET = "NVDAx";
const LEGACY_REFERENCE_PROFILE = "legacy_xperp_vs_p1ac";
const EVIDENCE_SEMANTICS_V2 = "p1a_xstock_band_with_xperp_review_corroboration_v2";

const CONSOLE_BACKUP = consoleWeekendDivergenceV2 as unknown as ValuationResult[];
export const DEMO_REPLAY_QUERY_KEY = ["demo-replay", DEFAULT_ASSET, "weekend_divergence", EVIDENCE_SEMANTICS_V2] as const;

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

function assertAsset(result: ValuationResult, asset: string): ValuationResult {
  if (result.asset !== asset) {
    throw new Error(`Backend returned ${result.asset} for requested asset ${asset}`);
  }
  if (result.reference_profile) return result;
  if (asset === DEFAULT_ASSET) {
    // Rollout compatibility for the pre-registry NVDAx API. Never infer a
    // profile for another asset: the new backend must identify it explicitly.
    return { ...result, reference_profile: LEGACY_REFERENCE_PROFILE };
  }
  throw new Error(`Backend omitted the reference profile for requested asset ${asset}`);
}

function assertAssetRows(results: ValuationResult[], asset: string): ValuationResult[] {
  if (!Array.isArray(results)) throw new Error("Backend returned an invalid observation list");
  return results.map((result) => assertAsset(result, asset));
}

function assertScopedResponse<T extends { asset?: string }>(
  data: T,
  asset: string,
  label: string,
): T & { asset: string } {
  if (data.asset === asset) return data as T & { asset: string };
  if (data.asset == null && asset === DEFAULT_ASSET) {
    // Pre-registry NVDAx on-chain responses were scoped by the endpoint but did
    // not repeat the asset in the body. Keep that one migration seam only.
    return { ...data, asset };
  }
  throw new Error(`Backend returned ${data.asset ?? "no asset"} ${label} for ${asset}`);
}

function normalizeAssetInfo(value: unknown): AssetInfo {
  if (!value || typeof value !== "object") {
    throw new Error("Backend returned an invalid asset catalog entry");
  }
  const item = value as Partial<AssetInfo>;
  if (
    typeof item.asset !== "string"
    || typeof item.token_source !== "string"
    || typeof item.underlying_source !== "string"
    || typeof item.model_available !== "boolean"
  ) {
    throw new Error("Backend returned an invalid asset catalog entry");
  }

  const legacyNvda = item.asset === DEFAULT_ASSET && item.reference_profile == null;
  if (item.reference_profile == null && !legacyNvda) {
    throw new Error(`Backend omitted readiness identity for asset ${item.asset}`);
  }

  return {
    asset: item.asset,
    token_source: item.token_source,
    underlying_source: item.underlying_source,
    reference_profile: item.reference_profile ?? LEGACY_REFERENCE_PROFILE,
    registered: item.registered ?? true,
    api_exposed: item.api_exposed ?? true,
    model_available: item.model_available,
    quant_artifact_ready: item.quant_artifact_ready ?? item.model_available,
    historical_data_available: item.historical_data_available ?? false,
    historical_panel_file_available: item.historical_panel_file_available ?? false,
    canonical_panel_verified: item.canonical_panel_verified ?? false,
    historical_replay_ready: item.historical_replay_ready ?? false,
    historical_replay_mode: item.historical_replay_mode ?? null,
    historical_panel_error_code: item.historical_panel_error_code ?? null,
    challenger_detector_status: item.challenger_detector_status ?? null,
    evidence_state_capability: item.evidence_state_capability ?? null,
    live_data_configured: item.live_data_configured ?? false,
    live_market_data_available: item.live_market_data_available ?? false,
    runtime_ready: item.runtime_ready ?? item.model_available,
    operational_ready: item.operational_ready ?? false,
    operational_scheduler_enabled: item.operational_scheduler_enabled ?? false,
    latest_observation_timestamp: item.latest_observation_timestamp ?? null,
    latest_observation_age_seconds: item.latest_observation_age_seconds ?? null,
    latest_observation_freshness: item.latest_observation_freshness ?? "unavailable",
    // Only the legacy NVDAx deployment is known to expose these routes without
    // readiness metadata. Missing metadata never enables another asset.
    onchain_binding_configured: item.onchain_binding_configured ?? legacyNvda,
    readiness_error_codes: Array.isArray(item.readiness_error_codes)
      ? item.readiness_error_codes
      : legacyNvda ? [] : ["ASSET_READINESS_METADATA_UNAVAILABLE"],
  };
}

export const assetQueryKeys = {
  assets: ["assets"] as const,
  operational: (asset: string, profile: string) => ["valuation", "operational", asset, profile] as const,
  history: (asset: string, limit: number, profile: string) => ["history", asset, limit, profile] as const,
  // The replay endpoint returns the complete panel. Time ranges are client-side
  // views of that same immutable response, so they must share one cache entry.
  historical: (asset: string, profile: string) => ["replay", asset, "historical-panel", profile] as const,
  runtime: (asset: string) => ["runtime", asset] as const,
  onchain: (asset: string) => ["onchain", asset] as const,
  enforcement: (asset: string) => ["onchain", asset, "enforcement"] as const,
  backtest: (asset: string, profile: string) => ["backtest", asset, "historical", profile] as const,
};

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
export async function fetchLiveDiagnostic(asset = DEFAULT_ASSET): Promise<ValuationResult> {
  return assertAsset(await getJSON<ValuationResult>(`/api/valuation/${asset}/live`, 12000), asset);
}

/** Latest persisted/warmed operational result (never advances the filter). */
export async function fetchOperationalValuation(asset = DEFAULT_ASSET): Promise<ValuationResult> {
  return assertAsset(await getJSON<ValuationResult>(`/api/valuation/${asset}`), asset);
}

export async function fetchRuntime(asset = DEFAULT_ASSET): Promise<RuntimeStatus> {
  const data = await getJSON<RuntimeStatus>(`/api/runtime/${asset}`);
  if (data.asset !== asset) throw new Error(`Backend returned ${data.asset} runtime for ${asset}`);
  return data;
}

export async function fetchAssets(): Promise<AssetInfo[]> {
  const data = await getJSON<unknown>("/api/assets");
  if (!Array.isArray(data)) throw new Error("Backend returned an invalid asset catalog");
  return data.map(normalizeAssetInfo);
}

/** Successful warmed scheduler observations only; never replay/backtest data. */
export async function fetchOperationalHistory(asset = DEFAULT_ASSET, limit = 72): Promise<ValuationResult[]> {
  return assertAssetRows(await getJSON<ValuationResult[]>(`/api/history/${asset}?limit=${limit}`, 10000), asset);
}

export interface HistoricalReplayResponse {
  results: ValuationResult[];
  source: "historical_panel";
}

/** Historical panel replay. A scenario response is rejected rather than substituted. */
export async function fetchHistoricalReplay(asset = DEFAULT_ASSET): Promise<HistoricalReplayResponse> {
  const response = await getJSONWithHeaders<ValuationResult[]>(`/api/replay/${asset}?source=panel`, 20000);
  const source = response.headers.get("X-Valtide-Source");
  // Fail closed: explicit panel routing alone does not verify response provenance.
  if (source !== "historical_panel") {
    throw new Error(`Unexpected replay source: ${source ?? "missing"}`);
  }
  if (!Array.isArray(response.data) || response.data.length === 0) {
    throw new Error("Historical panel replay is empty");
  }
  return { results: assertAssetRows(response.data, asset), source: "historical_panel" };
}

export async function fetchHistoricalBacktest(asset = DEFAULT_ASSET): Promise<BacktestMetrics> {
  const data = await getJSON<BacktestMetrics>(`/api/backtest/${asset}?source=historical`, 20000);
  if (data.source !== "historical") throw new Error("Historical backtest source could not be verified");
  return assertScopedResponse(data, asset, "backtest");
}

export async function fetchOnchain(asset = DEFAULT_ASSET): Promise<OnchainControlPlane> {
  const data = await getJSON<OnchainControlPlane>(`/api/onchain/${asset}`, 12000);
  return assertScopedResponse(data, asset, "control plane");
}

export async function fetchOnchainEnforcement(asset = DEFAULT_ASSET): Promise<OnchainEnforcement> {
  const data = await getJSON<OnchainEnforcement>(`/api/onchain/${asset}/enforcement`, 12000);
  return assertScopedResponse(data, asset, "enforcement");
}

export type ReplaySource = "backend-scenario" | "console-backup";
export interface ReplayResponse {
  results: ValuationResult[];
  source: ReplaySource;
}

/**
 * Demo replay sequence. Tries the production classifier first; on failure uses
 * a separate Console-only snapshot of that same v2 scenario response.
 */
export async function fetchDemoReplay(
  asset = DEFAULT_ASSET,
  scenario = "weekend_divergence",
): Promise<ReplayResponse> {
  if (asset !== DEFAULT_ASSET) {
    throw new Error("The bundled synthetic Demo is NVDAx-only; no other asset is substituted");
  }
  try {
    const results = await getJSON<ValuationResult[]>(
      `/api/replay/${asset}?source=scenario&scenario=${encodeURIComponent(scenario)}`,
    );
    if (!isV2Demo(results)) throw new Error("backend scenario does not satisfy the v2 Demo contract");
    return { results: assertAssetRows(results, asset), source: "backend-scenario" };
  } catch {
    return { results: assertAssetRows(CONSOLE_BACKUP, asset), source: "console-backup" };
  }
}

function isV2Demo(results: unknown): results is ValuationResult[] {
  return Array.isArray(results)
    && results.length === 6
    && results.every((row) => row && typeof row === "object"
      && (row as ValuationResult).asset === DEFAULT_ASSET
      && (row as ValuationResult).evidence_semantics === EVIDENCE_SEMANTICS_V2
      && (row as ValuationResult).validation_target === "xstock_observed_price"
      && (row as ValuationResult).xperp_role === "second_market_challenger"
      && (row as ValuationResult).xperp_index_price != null);
}
