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
}

export const EVIDENCE: Record<EvidenceState, EvidenceStyle> = {
  SUPPORTED: {
    label: "SUPPORTED",
    headline: "Reference under test is supported",
    description:
      "Available independent evidence provides no material reason to challenge the reference under test.",
    icon: "✓",
    fg: "var(--color-supported)",
    soft: "var(--color-supported-soft)",
    line: "var(--color-supported-line)",
  },
  INCONCLUSIVE: {
    label: "INCONCLUSIVE",
    headline: "Evidence is inconclusive",
    description:
      "The evidence is not strong enough to support or materially challenge the reference under test.",
    icon: "?",
    fg: "var(--color-inconclusive)",
    soft: "var(--color-inconclusive-soft)",
    line: "var(--color-inconclusive-line)",
  },
  CHALLENGED: {
    label: "CHALLENGED",
    headline: "Reference under test is challenged",
    description:
      "The reference under test is materially inconsistent with sufficiently strong independent evidence; that is not proof it is objectively wrong.",
    icon: "!",
    fg: "var(--color-challenged)",
    soft: "var(--color-challenged-soft)",
    line: "var(--color-challenged-line)",
  },
};
