// Redundant evidence encoding — colour is never the only signal (icon + label +
// colour), per PRODUCT_SEMANTICS.md. Each state also carries plain-English copy so a
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
}

export const EVIDENCE: Record<EvidenceState, EvidenceStyle> = {
  SUPPORTED: {
    label: "SUPPORTED",
    headline: "Validation target is supported",
    description:
      "The active, asset-authorized evidence rule supports the validation target; this is not proof that the observed price is objectively correct.",
    icon: "✓",
    fg: "var(--color-supported)",
    soft: "var(--color-supported-soft)",
    line: "var(--color-supported-line)",
  },
  INCONCLUSIVE: {
    label: "INCONCLUSIVE",
    headline: "Evidence is inconclusive",
    description:
      "The evidence is unavailable, watch-band, ambiguous, stale, or quality-gated, so the backend deliberately abstains.",
    icon: "?",
    fg: "var(--color-inconclusive)",
    soft: "var(--color-inconclusive-soft)",
    line: "var(--color-inconclusive-line)",
  },
  CHALLENGED: {
    label: "CHALLENGED",
    headline: "Validation target is challenged",
    description:
      "The active, asset-authorized evidence rule challenges the validation target; that is not proof it is objectively wrong.",
    icon: "!",
    fg: "var(--color-challenged)",
    soft: "var(--color-challenged-soft)",
    line: "var(--color-challenged-line)",
  },
};
