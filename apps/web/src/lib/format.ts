// Display formatting. Nulls render as "—", never NaN/blank (FRONTEND_PLAN §5).

export const DASH = "—";

export function money(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return DASH;
  return `$${x.toFixed(2)}`;
}

export function pct(x: number | null | undefined, dp = 2): string {
  if (x == null || Number.isNaN(x)) return DASH;
  const sign = x > 0 ? "+" : "";
  return `${sign}${x.toFixed(dp)}%`;
}

export function sigma(z: number | null | undefined, dp = 1): string {
  if (z == null || Number.isNaN(z)) return DASH;
  const sign = z > 0 ? "+" : "";
  return `${sign}${z.toFixed(dp)}σ`;
}

export function timeUTC(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  return `${d.toISOString().slice(11, 16)} UTC`;
}

export function unixTimeUTC(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds <= 0) return DASH;
  return timeUTC(new Date(seconds * 1000).toISOString());
}

export function ageLabel(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return DASH;
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

export function compactUsd(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return DASH;
  if (x >= 1e9) return `$${(x / 1e9).toFixed(1)}B`;
  if (x >= 1e6) return `$${(x / 1e6).toFixed(1)}M`;
  if (x >= 1e3) return `$${(x / 1e3).toFixed(0)}K`;
  return `$${x.toFixed(0)}`;
}

export interface Staleness {
  label: string;
  fg: string;
  soft: string;
  line: string;
}

// A trader keys on data age. Colour-code it instead of burying it in gray.
export function staleness(seconds: number | null | undefined): Staleness {
  const neutral = { fg: "var(--color-ink)", soft: "var(--color-panel-2)", line: "var(--color-line)" };
  if (seconds == null) return { label: DASH, ...neutral };
  const a = ageLabel(seconds);
  if (seconds < 15 * 60) return { label: `${a} · fresh`, fg: "var(--color-supported)", soft: "var(--color-supported-soft)", line: "var(--color-supported-line)" };
  if (seconds < 4 * 3600) return { label: `${a} · stale`, fg: "var(--color-inconclusive)", soft: "var(--color-inconclusive-soft)", line: "var(--color-inconclusive-line)" };
  return { label: `${a} · very stale`, fg: "var(--color-challenged)", soft: "var(--color-challenged-soft)", line: "var(--color-challenged-line)" };
}

export function sessionLabel(state: string): string {
  switch (state) {
    case "regular":
      return "Regular session";
    case "premarket":
    case "afterhours":
      return "Extended hours";
    case "overnight":
      return "Overnight";
    case "closed":
      return "Market closed";
    default:
      return state;
  }
}

// Human-readable reason codes; unknown codes fall back to a de-snaked label.
const REASON_LABELS: Record<string, string> = {
  REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL: "Reference is outside the model's range",
  TOKEN_AND_CHALLENGER_AGREE: "Tokenized market agrees with the estimate",
  COMPARATOR_UNAVAILABLE: "No comparator available",
  TOKEN_UNIT_SUSPECT: "Possible token/underlying unit mismatch",
  STALE_REFERENCE: "Trusted price is stale",
};

// Internal model diagnostics that shouldn't be presented to a trader as
// "signals" — handled elsewhere (e.g. the calibration caveat) or hidden.
export const INTERNAL_REASON_CODES = new Set(["CALIBRATION_GLOBAL_FALLBACK"]);

export function reasonLabel(code: string): string {
  return (
    REASON_LABELS[code] ??
    code
      .toLowerCase()
      .split("_")
      .join(" ")
      .replace(/^\w/, (c) => c.toUpperCase())
  );
}
