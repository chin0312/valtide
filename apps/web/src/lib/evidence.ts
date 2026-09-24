// Redundant evidence encoding — colour is never the only signal (icon + label +
// colour), per FRONTEND_PLAN §6. Each state also carries plain-English copy so a
// first-time viewer understands the verdict without the jargon.

import type { EvidenceState } from "../api/types";

export interface EvidenceStyle {
  label: string;
  headline: string;
  description: string;
  icon: string;
  fg: string;
  soft: string;
  line: string;
  policyDefault: string;
}

export const EVIDENCE: Record<EvidenceState, EvidenceStyle> = {
  SUPPORTED: {
    label: "SUPPORTED",
    headline: "Reference price looks supported",
    description:
      "Independent market evidence gives no material reason to doubt the reference price.",
    icon: "✓",
    fg: "var(--color-supported)",
    soft: "var(--color-supported-soft)",
    line: "var(--color-supported-line)",
    policyDefault: "ALLOW",
  },
  INCONCLUSIVE: {
    label: "INCONCLUSIVE",
    headline: "Evidence is inconclusive",
    description:
      "The evidence isn't strong enough to confirm or challenge the reference price.",
    icon: "?",
    fg: "var(--color-inconclusive)",
    soft: "var(--color-inconclusive-soft)",
    line: "var(--color-inconclusive-line)",
    policyDefault: "MONITOR",
  },
  CHALLENGED: {
    label: "CHALLENGED",
    headline: "Reference price is challenged",
    description:
      "The reference price is materially inconsistent with independent market evidence.",
    icon: "!",
    fg: "var(--color-challenged)",
    soft: "var(--color-challenged-soft)",
    line: "var(--color-challenged-line)",
    policyDefault: "RESTRICT_NEW_RISK",
  },
};

export const POLICY_OPTIONS = [
  "ALLOW",
  "MONITOR",
  "REQUIRE_REVIEW",
  "RESTRICT_NEW_RISK",
] as const;
export type PolicyAction = (typeof POLICY_OPTIONS)[number];

// Plain-language reading of how far the reference sits from fair value.
export function likelihoodPhrase(z: number | null): string {
  if (z == null) return "no comparison available";
  const a = Math.abs(z);
  if (a < 1) return "well within the normal range";
  if (a < 2) return "at the edge of the normal range";
  if (a < 3) return "outside the normal range";
  return "far outside the normal range — very unlikely to be chance";
}
