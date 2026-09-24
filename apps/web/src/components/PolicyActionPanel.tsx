import type { EvidenceState, OnchainEvaluation, OnchainPolicy, PolicyAction } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { ageLabel } from "../lib/format";
import { EvidenceChip } from "./EvidenceChip";
import { Panel } from "../components/ui";

const STATES: EvidenceState[] = ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED"];

// Used only when Demo mode cannot reach the backend/onchain control plane.
// It is explicitly labelled as an example rather than treated as a universal policy.
export const EXAMPLE_DEMO_POLICY: OnchainPolicy = {
  max_age: 900,
  on_supported: "ALLOW",
  on_inconclusive: "REQUIRE_REVIEW",
  on_challenged: "RESTRICT_NEW_RISK",
  on_stale: "REQUIRE_REVIEW",
};

const ACTION_MEANING: Record<PolicyAction, string> = {
  ALLOW: "The consuming application may permit new exposure.",
  MONITOR: "The consuming application may permit exposure while monitoring.",
  REQUIRE_REVIEW: "The consuming application should require review before new exposure.",
  RESTRICT_NEW_RISK: "The consuming application should reject new exposure.",
};

interface PolicyActionPanelProps {
  current: EvidenceState;
  policy?: OnchainPolicy;
  evaluation?: OnchainEvaluation;
  policySource: string;
}

export function PolicyActionPanel({ current, policy, evaluation, policySource }: PolicyActionPanelProps) {
  const currentStyle = EVIDENCE[current];
  const mappedAction = policy ? actionFor(policy, current) : null;
  const action = evaluation?.policy_action ?? mappedAction;

  return (
    <Panel title="Evidence → policy action" subtitle="Valtide evaluates evidence; the curator policy selects an action; the consumer enforces it.">
      <div className="rounded-xl px-4 py-4" style={{ background: currentStyle.soft, border: `1px solid ${currentStyle.line}` }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>Valtide Evidence State</div>
            <div className="mt-2"><EvidenceChip state={current} size="lg" /></div>
          </div>
          <div className="text-right">
            <div className="text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
              {evaluation ? "RiskGuard Policy Action" : "Configured Policy Action"}
            </div>
            <div className="mt-1 text-2xl font-bold" style={{ color: action ? currentStyle.fg : "var(--color-muted)" }}>
              {action ?? "—"}
            </div>
          </div>
        </div>
        {action && <div className="mt-2 text-sm" style={{ color: "var(--color-ink-dim)" }}>{ACTION_MEANING[action]}</div>}
        {evaluation && (
          <div className="mt-3 border-t pt-3 text-xs" style={{ borderColor: currentStyle.line, color: "var(--color-ink-dim)" }}>
            {evaluation.exists
              ? `X Layer attestation: ${evaluation.fresh ? "fresh" : "stale"}${evaluation.evidence_state !== current ? ` · Registry state ${evaluation.evidence_state}` : ""}`
              : "X Layer attestation: none published · RiskGuard is using the configured stale policy"}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 text-xs" style={{ color: "var(--color-ink-dim)" }}>
        <span>Policy source</span>
        <strong className="text-right text-ink">{policySource}</strong>
      </div>

      {policy ? (
        <>
          <div className="mt-3 flex items-center justify-between gap-3 text-xs" style={{ color: "var(--color-ink-dim)" }}>
            <span>Maximum observation age</span>
            <strong className="tnum text-ink">{ageLabel(policy.max_age)}</strong>
          </div>
          <div className="mt-4 overflow-hidden rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
            {STATES.map((state, index) => <MappingRow key={state} state={state} action={actionFor(policy, state)} active={state === current} first={index === 0} />)}
            <MappingRow stateLabel="STALE ATTESTATION" action={policy.on_stale} active={false} />
          </div>
        </>
      ) : (
        <p className="mt-4 rounded-lg px-3 py-2 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          No policy mapping is available from the backend/onchain control plane. The frontend does not assume a default action.
        </p>
      )}

      <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>
        Evidence State and Policy Action are separate. Valtide determines the evidence; the policy owner chooses the mapping; the consuming contract enforces the result.
      </p>
    </Panel>
  );
}

function actionFor(policy: OnchainPolicy, state: EvidenceState): PolicyAction {
  if (state === "SUPPORTED") return policy.on_supported;
  if (state === "INCONCLUSIVE") return policy.on_inconclusive;
  return policy.on_challenged;
}

function MappingRow({ state, stateLabel, action, active, first }: { state?: EvidenceState; stateLabel?: string; action: PolicyAction; active: boolean; first?: boolean }) {
  const label = state ?? stateLabel ?? "";
  const style = state ? EVIDENCE[state] : undefined;
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 text-sm" style={{ background: active && style ? style.soft : "var(--color-panel)", borderTop: first ? "none" : "1px solid var(--color-line)" }}>
      <span className="font-medium" style={{ color: active && style ? style.fg : "var(--color-ink-dim)" }}>{label}</span>
      <span aria-hidden style={{ color: "var(--color-muted)" }}>→</span>
      <span className="ml-auto tnum font-semibold text-ink">{action}</span>
    </div>
  );
}
