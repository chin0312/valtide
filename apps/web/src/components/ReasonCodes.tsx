import type { EvidenceState } from "../api/types";
import { reasonLabel } from "../lib/format";

const POSITIVE = new Set(["P1A_XSTOCK_SUPPORT_BAND"]);
const CHALLENGE = new Set(["XPERP_CORROBORATES_P1A"]);
const WARNING = new Set([
  "TOKEN_DATA_UNAVAILABLE",
  "COMPARATOR_UNAVAILABLE",
  "MODEL_UNCERTAINTY_INVALID",
  "UNDERLYING_REFERENCE_STALE",
  "REFERENCE_UNDER_TEST_STALE",
  "TOKEN_MARKET_QUALITY_LOW",
  "TOKEN_UNIT_SUSPECT",
  "MODEL_UNCERTAINTY_HIGH",
  "P1A_XSTOCK_DETECTOR_UNAVAILABLE",
  "P1A_XSTOCK_WATCH_BAND",
  "P1A_XSTOCK_SUPPORT_NOT_PROMOTED",
  "P1A_XSTOCK_CHALLENGE_NOT_PROMOTED",
  "XPERP_EVIDENCE_UNAVAILABLE",
  "XPERP_EVIDENCE_STALE",
  "XPERP_EVIDENCE_AMBIGUOUS",
  "XPERP_CORROBORATES_XSTOCK",
  "P1A_XSTOCK_REVIEW_BAND",
  "XPERP_EVIDENCE_WRONG_SOURCE",
]);

export function ReasonCodes({ codes, evidenceState }: { codes: string[]; evidenceState: EvidenceState }) {
  if (!codes.length)
    return (
      <span className="text-sm" style={{ color: "var(--color-ink-dim)" }}>
        No signals recorded.
      </span>
    );
  return (
    <ul className="flex flex-wrap gap-2">
      {codes.map((c) => {
        const challengeSignal = evidenceState === "CHALLENGED" && (CHALLENGE.has(c) || c === "P1A_XSTOCK_REVIEW_BAND");
        const tone = POSITIVE.has(c) ? "positive" : challengeSignal ? "challenge" : WARNING.has(c) || CHALLENGE.has(c) ? "warning" : "neutral";
        const colors = tone === "positive"
          ? { background: "var(--color-supported-soft)", color: "var(--color-supported)", border: "var(--color-supported-line)" }
          : tone === "challenge"
            ? { background: "var(--color-challenged-soft)", color: "var(--color-challenged)", border: "var(--color-challenged-line)" }
            : tone === "warning"
              ? { background: "var(--color-inconclusive-soft)", color: "var(--color-inconclusive)", border: "var(--color-inconclusive-line)" }
              : { background: "var(--color-panel-2)", color: "var(--color-ink-dim)", border: "var(--color-line)" };
        return (
          <li
            key={c}
            title={c}
            className="rounded px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.035em]"
            style={{
              background: colors.background,
              color: colors.color,
              border: `1px solid ${colors.border}`,
            }}
          >
            {reasonLabel(c)}
          </li>
        );
      })}
    </ul>
  );
}
