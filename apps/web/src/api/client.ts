// Typed client for the full Valtide backend contract. Every screen is built from
// the same ValuationResult shape, so the UI can render live, cached-warmed,
// historical-replay, or scenario data identically. A static fixture backs the
// demo scenario so a pitch can't fail on a network/CORS/key issue.
//
// Endpoint map (FastAPI, apps/api):
//   GET  /health
//   GET  /api/valuation/{asset}         cached warmed result (503 on cold cache)
//   GET  /api/valuation/{asset}/live    on-demand live inference through the quant
//   GET  /api/replay/{asset}            historical/scenario sequence
//   GET  /api/backtest/{asset}          metrics / evidence-state counts
//   GET  /api/runtime/{asset}           warmed scheduler status

import type { BacktestMetrics, RuntimeStatus, ValuationResult } from "./types";
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

/** On-demand live inference: DexScreener + Alpaca + OKX → quant runtime → validation. */
export function fetchLiveValuation(): Promise<ValuationResult> {
  return getJSON<ValuationResult>(`/api/valuation/${ASSET}/live`, 12000);
}

/** Latest cached warmed result (never advances the filter). */
export function fetchCachedValuation(): Promise<ValuationResult> {
  return getJSON<ValuationResult>(`/api/valuation/${ASSET}`);
}

export function fetchRuntime(): Promise<RuntimeStatus> {
  return getJSON<RuntimeStatus>(`/api/runtime/${ASSET}`);
}

export function fetchBacktest(source = "scenario", scenario = "weekend_divergence"): Promise<BacktestMetrics> {
  return getJSON<BacktestMetrics>(`/api/backtest/${ASSET}?source=${source}&scenario=${scenario}`);
}

export type ReplaySource = "live" | "fixture";
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
    return { results, source: "live" };
  } catch {
    return { results: FIXTURE, source: "fixture" };
  }
}
