import type { EvidenceState } from "../api/types";
import { Panel } from "../components/ui";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

// Fixed example policy for the demo. The point is separation of concerns:
// Valtide produces the verdict; the curator's policy decides the action.
const POLICY: Record<EvidenceState, string> = {
  SUPPORTED: "ALLOW",
  INCONCLUSIVE: "MONITOR",
  CHALLENGED: "RESTRICT_NEW_RISK",
};

const ACTION_MEANING: Record<string, string> = {
  ALLOW: "New borrowing allowed as normal",
  MONITOR: "Keep lending, watch more closely",
  REQUIRE_REVIEW: "Pause for a human/protocol review",
  RESTRICT_NEW_RISK: "Block new borrowing against this collateral",
};

export function PolicyActionPanel({ current }: { current: EvidenceState }) {
  const action = POLICY[current];

  return (
    <Panel title="Policy result" subtitle="Configured protocol rule — not a Valtide recommendation">
      {/* the outcome for the current verdict */}
      <div className="rounded-sm px-4 py-4" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-ink-dim)" }}>
          Evidence State <strong className="tnum text-ink">{current}</strong> maps to:
        </div>
        <div className="tnum mt-3 break-words text-xl font-medium tracking-[-0.03em]" style={{ color: "var(--color-accent)" }}>
          {action}
        </div>
        <div className="mt-1 text-sm" style={{ color: "var(--color-ink-dim)" }}>
          {ACTION_MEANING[action]}
        </div>
      </div>

      {/* the full rule set, current row highlighted */}
      <div className="mt-4">
        <div className="mb-2 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
          This curator's rules
        </div>
        <div className="overflow-hidden rounded-sm" style={{ border: "1px solid var(--color-line)" }}>
          {STATES.map((sName, i) => {
            const active = sName === current;
            return (
              <div
                key={sName}
                className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                style={{
                  background: active ? "var(--color-panel-2)" : "var(--color-panel)",
                  borderTop: i === 0 ? "none" : "1px solid var(--color-line)",
                }}
              >
                <span className="font-medium" style={{ color: active ? "var(--color-ink)" : "var(--color-muted)" }}>
                  {sName}
                </span>
                <span aria-hidden style={{ color: "var(--color-muted)" }}>→</span>
                <span className="ml-auto tnum font-medium" style={{ color: active ? "var(--color-accent)" : "var(--color-ink-dim)" }}>
                  {POLICY[sName]}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>
        These rules are set by the curator — not by Valtide. A different curator could respond to the
        same verdict differently.
      </p>
    </Panel>
  );
}
