// Band-relative helpers remain available for interval-relative diagnostics.
// The Range View uses a separate raw-price domain so prices move consistently
// across the active Operational, Historical, or Demo result set.

import type { ValuationResult } from "../api/types";
import { isEvidenceStateV2, isXStockValidation, validationTargetPrice } from "./semantics";

/** Fixed viewport so the reference visibly travels outward across steps. */
export const AXIS_MIN = -3.5;
export const AXIS_MAX = 3.5;

/** Convert a price into band-relative units for a given result. */
export function toBandUnits(price: number, r: ValuationResult): number {
  const fair = r.valtide_fair_value;
  if (price <= fair) {
    const half = fair - r.fair_value_lower;
    return half > 0 ? (price - fair) / half : 0;
  }
  const half = r.fair_value_upper - fair;
  return half > 0 ? (price - fair) / half : 0;
}

/** Map band-units to a 0..1 fraction across the fixed axis (for CSS %). */
export function unitsToFraction(units: number): number {
  const clamped = Math.max(AXIS_MIN, Math.min(AXIS_MAX, units));
  return (clamped - AXIS_MIN) / (AXIS_MAX - AXIS_MIN);
}

/** Convenience: fraction position of a price directly. */
export function priceToFraction(price: number, r: ValuationResult): number {
  return unitsToFraction(toBandUnits(price, r));
}

export type RangeViewPriceDomain = readonly [number, number];

/** Build one padded raw-price domain for the selected active timeline. */
export function rangeViewPriceDomain(results: readonly ValuationResult[]): RangeViewPriceDomain {
  const prices: number[] = [];
  const intervalWidths: number[] = [];
  const include = (value: number | null | undefined) => {
    if (value != null && Number.isFinite(value)) prices.push(value);
  };

  for (const result of results) {
    include(result.fair_value_lower);
    include(result.fair_value_upper);
    include(result.valtide_fair_value);
    const xstockValidation = isXStockValidation(result);
    if (xstockValidation) {
      include(result.token_price);
      include(isEvidenceStateV2(result)
        ? result.xperp_index_price
        : result.xperp_index_price ?? result.reference_under_test);
    } else {
      include(result.reference_under_test);
    }
    const width = result.fair_value_upper - result.fair_value_lower;
    if (Number.isFinite(width) && width > 0) intervalWidths.push(width);
  }

  if (prices.length === 0) return [0, 1];
  const rawMin = Math.min(...prices);
  const rawMax = Math.max(...prices);
  const span = rawMax - rawMin;
  intervalWidths.sort((left, right) => left - right);
  const middle = Math.floor(intervalWidths.length / 2);
  const representativeIntervalWidth = intervalWidths.length === 0
    ? 0
    : intervalWidths.length % 2 === 0
      ? (intervalWidths[middle - 1] + intervalWidths[middle]) / 2
      : intervalWidths[middle];
  const smallPositivePadding = Math.max(0.01, Math.max(1, Math.abs(rawMin), Math.abs(rawMax)) * 0.0001);

  if (!(span > 0)) {
    const halfSpan = Math.max(representativeIntervalWidth * 0.1, smallPositivePadding);
    return [rawMin - halfSpan, rawMax + halfSpan];
  }

  const padding = Math.max(span * 0.1, representativeIntervalWidth * 0.1, smallPositivePadding);
  return [rawMin - padding, rawMax + padding];
}

/** Map a raw price to a clamped fraction of the shared Range View domain. */
export function priceToRangeFraction(price: number, domain: RangeViewPriceDomain): number {
  const [minPrice, maxPrice] = domain;
  const span = maxPrice - minPrice;
  if (!Number.isFinite(price) || !Number.isFinite(minPrice) || !Number.isFinite(maxPrice) || !(span > 0)) return 0.5;
  return Math.max(0, Math.min(1, (price - minPrice) / span));
}

/** Is the active validation target outside the actual calibrated interval bounds? */
export function referenceOutsideBand(r: ValuationResult): boolean {
  const target = validationTargetPrice(r);
  if (target == null) return false;
  return target < r.fair_value_lower || target > r.fair_value_upper;
}
