// Typed client for the full Valtide backend contract. Every screen is built from
// the same ValuationResult shape, so the UI can render warmed operational,
// diagnostic, historical-replay, or scenario data without conflating them. A
// static fixture backs the demo scenario so a pitch can't fail on a network/CORS/key issue.
//
// Endpoint map (FastAPI, apps/api):
//   GET  /health
//   GET  /api/valuation/{asset}         persisted/warmed result (503 on cold cache)
//   GET  /api/valuation/{asset}/live    one-off cold-start diagnostic
//   GET  /api/replay/{asset}            historical/scenario sequence
//   GET  /api/backtest/{asset}?source=historical historical diagnostics
//   GET  /api/runtime/{asset}           warmed scheduler status
//   GET  /api/onchain/{asset}           X Layer Registry / RiskGuard state
//   GET  /api/onchain/{asset}/enforcement DemoVault read-only enforcement check

import type {
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
    return { results, source: "backend-scenario" };
  } catch {
    return { results: FIXTURE, source: "offline-fixture" };
  }
}
