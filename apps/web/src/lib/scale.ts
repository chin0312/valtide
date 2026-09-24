// Band-relative scaling — the make-or-break decision from FRONTEND_PLAN §4A.
//
// The whole demo happens inside a ~$0.90 window, so a raw-price axis makes
// SUPPORTED and CHALLENGED look identical. We instead plot everything in
// band-relative units: the challenger fair value is 0, the lower interval edge
// is -1, the upper edge is +1 (handling asymmetric bands). A reference at +1
// sits exactly on the interval boundary; beyond ±1 it is outside the interval.

import type { ValuationResult } from "../api/types";

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

/** Is the reference under test outside the challenger interval? */
export function referenceOutsideBand(r: ValuationResult): boolean {
  if (r.reference_under_test == null) return false;
  return Math.abs(toBandUnits(r.reference_under_test, r)) > 1;
}
