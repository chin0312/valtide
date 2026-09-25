import type { ValuationResult } from "../api/types";

/** Polls can finish out of order; keep the newest observation and deduplicate. */
export function mergeObservations(history: ValuationResult[], latest?: ValuationResult): ValuationResult[] {
  const rows = new Map(history.map((row) => [row.timestamp, row]));
  if (latest) rows.set(latest.timestamp, latest);
  return [...rows.values()].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
}

/** Keep the selected timestamp when a rolling history window gains/loses rows. */
export function rebasePosition(position: number, previous: ValuationResult[], next: ValuationResult[]): number {
  const safe = clampPosition(position, previous.length);
  const selected = previous[Math.floor(safe)];
  const index = next.findIndex((row) => row.timestamp === selected?.timestamp);
  return index < 0 ? 0 : clampPosition(index + safe % 1, next.length);
}

/** Clamp every playback entry point, including animation timestamps and scrubs. */
export function clampPosition(position: number, count: number): number {
  return Number.isFinite(position) ? Math.max(0, Math.min(position, Math.max(0, count - 1))) : 0;
}

export function advancePosition(origin: number, elapsed: number, count: number, periodMs = 120): number {
  // 120ms per presentation period: about 1.75x faster than the previous 210ms.
  return clampPosition(origin + Math.max(0, elapsed) / periodMs, count);
}
