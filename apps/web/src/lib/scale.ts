import type { ValuationResult } from "../api/types";
import { isEvidenceStateV2, isXStockValidation, validationTargetPrice } from "./semantics";

export type PriceDomain = { min: number; max: number };

const DOMAIN_PADDING_RATIO = 0.1;
const MAX_INTERVAL_FRACTION = 0.5;
const ZERO_SPAN_FALLBACK = 1e-9;

function plottedPrices(result: ValuationResult): number[] {
  const xstockValidation = isXStockValidation(result);
  const referencePrice = xstockValidation
    ? rangeViewXperpPrice(result)
    : result.reference_under_test;
  const prices = [
    result.fair_value_lower,
    result.fair_value_upper,
    result.valtide_fair_value,
    ...(xstockValidation ? [result.token_price, referencePrice] : [referencePrice]),
  ];
  return prices.filter((price): price is number => price != null && Number.isFinite(price));
}

/** Preserve the Range View's existing explicit-X-Perp and legacy-reference fallback contract. */
export function rangeViewXperpPrice(result: ValuationResult): number | null {
  return result.xperp_index_price ?? (isEvidenceStateV2(result) ? null : result.reference_under_test);
}

/** Derive one padded raw-price domain from the already-filtered active timeline window. */
export function rangeViewPriceDomain(results: ValuationResult[]): PriceDomain {
  const prices = results.flatMap(plottedPrices);
  if (prices.length === 0) return { min: -0.5, max: 0.5 };

  const rawMin = Math.min(...prices);
  const rawMax = Math.max(...prices);
  const rawSpan = rawMax - rawMin;
  const center = rawMin / 2 + rawMax / 2;
  const widestInterval = results.reduce((widest, result) => {
    const interval = result.fair_value_upper - result.fair_value_lower;
    return Number.isFinite(interval) && interval > widest ? interval : widest;
  }, 0);

  const paddedRawSpan = Number.isFinite(rawSpan) ? rawSpan * (1 + 2 * DOMAIN_PADDING_RATIO) : Number.MAX_VALUE;
  const intervalMinimumSpan = widestInterval * (1 / MAX_INTERVAL_FRACTION + 0.2);
  const relativeFallbackSpan = Math.abs(center) * 0.02;
  const domainSpan = Math.min(Number.MAX_VALUE, Math.max(paddedRawSpan, intervalMinimumSpan, relativeFallbackSpan, ZERO_SPAN_FALLBACK));
  const halfSpan = domainSpan / 2;
  let min = center - halfSpan;
  let max = center + halfSpan;

  if (!Number.isFinite(min) || !Number.isFinite(max) || !(max > min) || min > rawMin || max < rawMax) {
    min = rawMin;
    max = rawMax;
  }
  if (!(max > min)) {
    const fallbackSpan = Math.max(Math.abs(center) * 0.02, ZERO_SPAN_FALLBACK);
    min = center - fallbackSpan / 2;
    max = center + fallbackSpan / 2;
  }

  return Number.isFinite(min) && Number.isFinite(max) && max > min
    ? { min, max }
    : { min: -0.5, max: 0.5 };
}

/** Map a raw price to the shared 0..1 fraction used by the Range View. */
export function priceToFraction(price: number, domain: PriceDomain): number {
  if (!Number.isFinite(price) || !Number.isFinite(domain.min) || !Number.isFinite(domain.max) || !(domain.max > domain.min)) return 0.5;
  const span = domain.max - domain.min;
  let fraction = Number.isFinite(span)
    ? (price - domain.min) / span
    : (() => {
      const scale = Math.max(Math.abs(price), Math.abs(domain.min), Math.abs(domain.max));
      return (price / scale - domain.min / scale) / (domain.max / scale - domain.min / scale);
    })();
  if (!Number.isFinite(fraction)) fraction = price <= domain.min ? 0 : 1;
  return Math.max(0, Math.min(1, fraction));
}

/** Is the active validation target outside the actual calibrated interval bounds? */
export function referenceOutsideBand(r: ValuationResult): boolean {
  const target = validationTargetPrice(r);
  if (target == null) return false;
  return target < r.fair_value_lower || target > r.fair_value_upper;
}
