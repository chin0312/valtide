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
  if (!Number.isFinite(d.getTime())) return DASH;
  return `${d.toISOString().slice(11, 16)} UTC`;
}

export function dateTimeUTC(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return DASH;
  return `${d.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function unixTimeUTC(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds <= 0) return DASH;
  return timeUTC(new Date(seconds * 1000).toISOString());
}

export function unixDateTimeUTC(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds <= 0) return DASH;
  return dateTimeUTC(new Date(seconds * 1000).toISOString());
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

export function coverageLabel(target: number | null | undefined): string {
  if (target == null || !Number.isFinite(target)) return "Calibrated interval";
  return `${Math.round(target * 100)}% calibrated interval`;
}

export function timeAxisUTC(timestampMs: number, multiDay: boolean): string {
  const d = new Date(timestampMs);
  if (!Number.isFinite(d.getTime())) return DASH;
  if (!multiDay) return `${d.toISOString().slice(11, 16)} UTC`;
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })} ${d.toISOString().slice(11, 16)}`;
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

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return DASH;
  const labels: Record<string, string> = {
    okx_onchainos: "OKX OnchainOS",
    okx_xperp_index: "OKX X-Perp index",
    alpaca: "Alpaca NVDA",
    dexscreener: "DexScreener diagnostic",
  };
  return labels[source] ?? source;
}

// Human-readable reason codes; unknown codes fall back to a de-snaked label.
const REASON_LABELS: Record<string, string> = {
  TOKEN_DATA_UNAVAILABLE: "Tokenized-market observation unavailable",
  COMPARATOR_UNAVAILABLE: "Independent comparator unavailable",
  MODEL_UNCERTAINTY_INVALID: "Model uncertainty unavailable",
  REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL: "Reference under test is outside the calibrated interval",
  UNDERLYING_REFERENCE_STALE: "Trusted underlying observation is stale",
  REFERENCE_UNDER_TEST_STALE: "Reference under test is stale",
  TOKEN_MARKET_QUALITY_LOW: "Tokenized-market quality is low",
  TOKEN_AND_CHALLENGER_AGREE: "Tokenized market agrees with the estimate",
  TOKEN_UNIT_SUSPECT: "Possible token/underlying unit mismatch",
  MODEL_UNCERTAINTY_HIGH: "Model uncertainty is high",
  CALIBRATION_GLOBAL_FALLBACK: "Global fallback calibration",
};

// Internal model diagnostics that should not be presented to a risk team as
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
