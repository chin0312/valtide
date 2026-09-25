import type { EvidenceState } from "../api/types";
import { INTERNAL_REASON_CODES, reasonLabel } from "../lib/format";

const POSITIVE = new Set(["TOKEN_AND_CHALLENGER_AGREE"]);
const CHALLENGE = new Set(["REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL"]);
const WARNING = new Set([
  "TOKEN_DATA_UNAVAILABLE",
  "COMPARATOR_UNAVAILABLE",
  "MODEL_UNCERTAINTY_INVALID",
  "UNDERLYING_REFERENCE_STALE",
  "REFERENCE_UNDER_TEST_STALE",
  "TOKEN_MARKET_QUALITY_LOW",
  "TOKEN_UNIT_SUSPECT",
  "MODEL_UNCERTAINTY_HIGH",
]);

export function ReasonCodes({ codes: allCodes, evidenceState }: { codes: string[]; evidenceState: EvidenceState }) {
  const codes = allCodes.filter((c) => !INTERNAL_REASON_CODES.has(c));
  if (!codes.length)
    return (
      <span className="text-sm" style={{ color: "var(--color-ink-dim)" }}>
        No signals recorded.
      </span>
    );
  return (
    <ul className="flex flex-wrap gap-2">
      {codes.map((c) => {
        const tone = POSITIVE.has(c) ? "positive" : CHALLENGE.has(c) && evidenceState === "CHALLENGED" ? "challenge" : WARNING.has(c) || CHALLENGE.has(c) ? "warning" : "neutral";
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
            className="rounded-lg px-2.5 py-1 text-xs font-medium"
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
