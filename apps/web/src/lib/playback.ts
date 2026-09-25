/** Clamp every playback entry point, including animation timestamps and scrubs. */
export function clampPosition(position: number, count: number): number {
  return Number.isFinite(position) ? Math.max(0, Math.min(position, Math.max(0, count - 1))) : 0;
}

export function advancePosition(origin: number, elapsed: number, count: number): number {
  return clampPosition(origin + Math.max(0, elapsed) / 420, count);
}
