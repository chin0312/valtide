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

export const BASE = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");
export const DEFAULT_ASSET = "NVDAx";
export const PRIMARY_ASSET_OPTIONS = ["NVDAx", "SPYx", "QQQx", "AAPLx"] as const;
export type PrimaryAsset = (typeof PRIMARY_ASSET_OPTIONS)[number];

const FIXTURE = weekendDivergence as unknown as ValuationResult[];

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

function assertAsset(result: ValuationResult, asset: string): ValuationResult {
  if (result.asset !== asset) {
    throw new Error(`Backend returned ${result.asset} for requested asset ${asset}`);
  }
  return result;
}

function assertAssetRows(results: ValuationResult[], asset: string): ValuationResult[] {
  if (!Array.isArray(results)) throw new Error("Backend returned an invalid observation list");
  results.forEach((result) => assertAsset(result, asset));
  return results;
}

export const assetQueryKeys = {
  assets: ["assets"] as const,
  operational: (asset: string, profile: string) => ["valuation", "operational", asset, profile] as const,
  history: (asset: string, limit: number, profile: string) => ["history", asset, limit, profile] as const,
  historical: (asset: string, range: string, profile: string) => ["replay", asset, "historical-panel", range, profile] as const,
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

export function fetchAssets(): Promise<AssetInfo[]> {
  return getJSON<AssetInfo[]>("/api/assets");
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
  if (data.asset !== asset) throw new Error(`Backend returned ${data.asset} backtest for ${asset}`);
  return data;
}

export async function fetchOnchain(asset = DEFAULT_ASSET): Promise<OnchainControlPlane> {
  const data = await getJSON<OnchainControlPlane>(`/api/onchain/${asset}`, 12000);
  if (data.asset !== asset) throw new Error(`Backend returned ${data.asset} control plane for ${asset}`);
  return data;
}

export async function fetchOnchainEnforcement(asset = DEFAULT_ASSET): Promise<OnchainEnforcement> {
  const data = await getJSON<OnchainEnforcement>(`/api/onchain/${asset}/enforcement`, 12000);
  if (data.asset !== asset) throw new Error(`Backend returned ${data.asset} enforcement for ${asset}`);
  return data;
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
    if (!Array.isArray(results) || results.length === 0) throw new Error("empty replay");
    return { results: assertAssetRows(results, asset), source: "backend-scenario" };
  } catch {
    return { results: assertAssetRows(FIXTURE, asset), source: "offline-fixture" };
  }
}
