import type { EvidenceState } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
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
  const cur = EVIDENCE[current];
  const action = POLICY[current];

  return (
    <Panel title="What the protocol does" subtitle="The curator's policy turns the verdict into an action">
      {/* the outcome for the current verdict */}
      <div className="rounded-xl px-4 py-4" style={{ background: cur.soft, border: `1px solid ${cur.line}` }}>
        <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-ink-dim)" }}>
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold text-white" style={{ background: cur.fg }} aria-hidden>
            {cur.icon}
          </span>
          Verdict is <strong style={{ color: cur.fg }}>{current}</strong>, so the policy triggers:
        </div>
        <div className="mt-2 text-2xl font-bold" style={{ color: cur.fg }}>
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
        <div className="overflow-hidden rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
          {STATES.map((sName, i) => {
            const active = sName === current;
            const st = EVIDENCE[sName];
            return (
              <div
                key={sName}
                className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                style={{
                  background: active ? st.soft : "var(--color-panel)",
                  borderTop: i === 0 ? "none" : "1px solid var(--color-line)",
                }}
              >
                <span className="font-medium" style={{ color: active ? st.fg : "var(--color-ink-dim)" }}>
                  {sName}
                </span>
                <span aria-hidden style={{ color: "var(--color-muted)" }}>→</span>
                <span className="ml-auto tnum font-semibold" style={{ color: active ? st.fg : "var(--color-ink)" }}>
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
