// Range View compares each selected observation against its own valuation interval.

import type { ValuationResult } from "../api/types";
import { validationTargetPrice } from "./semantics";

/** Fixed normalized viewport; prices outside the interval can extend to its edges. */
export const AXIS_MIN = -3.5;
export const AXIS_MAX = 3.5;

/** Map a price linearly across the selected result's valuation interval. */
export function toBandUnits(price: number, r: ValuationResult): number {
  const lower = r.fair_value_lower;
  const upper = r.fair_value_upper;
  const interval = upper - lower;
  if (!Number.isFinite(price) || !Number.isFinite(lower) || !Number.isFinite(upper) || !Number.isFinite(interval) || !(interval > 0)) return 0;
  const units = -1 + (2 * (price - lower)) / interval;
  return Number.isFinite(units) ? units : 0;
}

/** Map band-units to a 0..1 fraction across the fixed axis (for CSS %). */
export function unitsToFraction(units: number): number {
  if (!Number.isFinite(units)) return 0.5;
  const clamped = Math.max(AXIS_MIN, Math.min(AXIS_MAX, units));
  if (clamped <= -1) return ((clamped - AXIS_MIN) / (-1 - AXIS_MIN)) * 0.25;
  if (clamped <= 1) return 0.25 + ((clamped + 1) / 2) * 0.5;
  return 0.75 + ((clamped - 1) / (AXIS_MAX - 1)) * 0.25;
}

/** Convenience: fraction position of a price directly. */
export function priceToFraction(price: number, r: ValuationResult): number {
  return unitsToFraction(toBandUnits(price, r));
}

/** Is the active validation target outside the actual calibrated interval bounds? */
export function referenceOutsideBand(r: ValuationResult): boolean {
  const target = validationTargetPrice(r);
  if (target == null) return false;
  return target < r.fair_value_lower || target > r.fair_value_upper;
}
