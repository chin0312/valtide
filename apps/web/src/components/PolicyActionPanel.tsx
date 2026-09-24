import type { EvidenceState, OnchainEvaluation, OnchainPolicy, PolicyAction } from "../api/types";
import { EVIDENCE } from "../lib/evidence";
import { ageLabel } from "../lib/format";
import type { OnchainSyncStatus } from "../lib/onchain";
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
  REQUIRE_REVIEW: "New exposure should not proceed until review.",
  RESTRICT_NEW_RISK: "The consuming application should reject new exposure.",
};

const ACTION_COLOR: Record<PolicyAction, string> = {
  ALLOW: "var(--color-supported)",
  MONITOR: "var(--color-supported)",
  REQUIRE_REVIEW: "var(--color-inconclusive)",
  RESTRICT_NEW_RISK: "var(--color-challenged)",
};

interface PolicyActionPanelProps {
  current: EvidenceState;
  policy?: OnchainPolicy;
  evaluation?: OnchainEvaluation;
  policySource: string;
  sync?: OnchainSyncStatus;
  scenarioMode?: boolean;
}

export function PolicyActionPanel({ current, policy, evaluation, policySource, sync, scenarioMode = false }: PolicyActionPanelProps) {
  const currentStyle = EVIDENCE[current];
  const projectedAction = policy ? actionFor(policy, current) : null;
  const enforcedAction = evaluation?.policy_action ?? null;

  return (
    <Panel title={scenarioMode ? "Scenario policy projection" : "Evidence → policy action"} subtitle="Valtide evaluates evidence; the curator policy selects an action; the consumer enforces it.">
      <div className="rounded-xl px-4 py-4" style={{ background: currentStyle.soft, border: `1px solid ${currentStyle.line}` }}>
        <div className="text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
          {scenarioMode ? "Scenario Evidence State" : "Current Operational Evidence"}
        </div>
        <div className="mt-2"><EvidenceChip state={current} size="lg" /></div>

        {scenarioMode ? (
          <ActionBlock
            label="Curator mapping for this scenario Evidence State"
            action={projectedAction}
            description="This deterministic replay does not publish its state to the deployed Registry."
            detail="This mapping applies to a fresh attestation. A stale attestation uses the configured STALE policy."
          />
        ) : (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <ActionBlock
              label="Curator mapping for this Evidence State"
              action={projectedAction}
              description="The configured curator mapping for the current operational Evidence State."
              detail="This mapping applies to a fresh attestation. A stale attestation uses the configured STALE policy."
            />
            <ActionBlock
              label="Current onchain enforced action"
              action={enforcedAction}
              description="The RiskGuard result for the Registry generation currently on X Layer."
              detail={evaluation ? evaluationDescription(evaluation) : undefined}
            />
          </div>
        )}
      </div>

      {!scenarioMode && sync && (
        <div className="mt-3 rounded-lg px-3 py-2 text-xs" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          <div className="flex items-center justify-between gap-3">
            <span>Operational ↔ Registry</span>
            <strong className="text-ink">{sync.state}</strong>
          </div>
          <div className="mt-1">{sync.detail}</div>
        </div>
      )}

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
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--color-panel-2)", color: "var(--color-ink-dim)" }}>Curator policy mapping</div>
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

function ActionBlock({ label, action, description, detail }: { label: string; action: PolicyAction | null; description: string; detail?: string }) {
  return (
    <div className="rounded-lg px-3 py-3" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
      <div className="text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>{label}</div>
      <div className="mt-1 text-xl font-bold" style={{ color: action ? ACTION_COLOR[action] : "var(--color-muted)" }}>{action ?? "—"}</div>
      <div className="mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>{action ? ACTION_MEANING[action] : description}</div>
      {detail && <div className="mt-1 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>{detail}</div>}
    </div>
  );
}

function evaluationDescription(evaluation: OnchainEvaluation): string {
  if (!evaluation.exists) return "Registry Evidence: no attestation; stale-policy action returned.";
  return `Registry Evidence: ${evaluation.evidence_state} · ${evaluation.fresh ? "fresh" : "stale"} attestation.`;
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
