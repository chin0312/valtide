import type { OnchainControlPlane, OnchainEnforcement } from "../api/types";
import { Panel } from "../components/ui";
import { unixTimeUTC } from "../lib/format";

interface RegistryPanelProps {
  controlPlane?: OnchainControlPlane;
  enforcement?: OnchainEnforcement;
  isLoading?: boolean;
  isError?: boolean;
  errorDetail?: string;
}

export function RegistryPanel({ controlPlane, enforcement, isLoading, isError, errorDetail }: RegistryPanelProps) {
  if (isLoading) {
    return <Panel title="X Layer Control Plane" subtitle="Read-only Registry → RiskGuard → DemoVault status">Loading deployed control-plane state…</Panel>;
  }

  if (!controlPlane) {
    return (
      <Panel title="X Layer Control Plane" subtitle="Read-only Registry → RiskGuard → DemoVault status">
        <div className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-inconclusive-line)", color: "var(--color-inconclusive)" }}>
          <strong>Control-plane status unavailable.</strong>
          <div className="mt-1" style={{ color: "var(--color-ink-dim)" }}>{isError ? errorDetail ?? "The backend could not read the deployed X Layer contracts." : "No onchain response has been loaded."}</div>
        </div>
        <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>
          The browser is read-only and holds no signer key. Publication remains an explicit backend operation.
        </p>
      </Panel>
    );
  }

  const attestation = controlPlane.attestation;
  return (
    <Panel title="X Layer Control Plane" subtitle="Deployed Registry → curator policy → RiskGuard → DemoVault">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2.5" style={{ background: "var(--color-supported-soft)", border: "1px solid var(--color-supported-line)" }}>
        <div className="text-sm font-semibold" style={{ color: "var(--color-supported)" }}>{controlPlane.network}</div>
        <div className="text-xs tnum" style={{ color: "var(--color-ink-dim)" }}>chain {controlPlane.chain_id} · deployed</div>
      </div>

      <div className="mt-4 grid gap-x-4 gap-y-2 sm:grid-cols-2">
        <Detail label="Registry" value={shortHex(controlPlane.registry)} />
        <Detail label="RiskGuard" value={shortHex(controlPlane.risk_guard)} />
        <Detail label="DemoVault" value={shortHex(controlPlane.demo_vault)} />
        <Detail label="Reference" value={shortHex(controlPlane.reference_id)} />
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-ink-dim)" }}>Latest attestation</div>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Detail label="Exists" value={controlPlane.exists ? "Yes" : "No attestation published"} />
          <Detail label="Registry fresh" value={controlPlane.registry_fresh ? "Yes" : "No"} />
          <Detail label="Evidence State" value={controlPlane.exists ? controlPlane.evidence_state : "—"} />
          <Detail label="RiskGuard Action" value={controlPlane.policy_action} />
          <Detail label="Observed" value={unixTimeUTC(attestation?.observedAt)} />
          <Detail label="Published" value={unixTimeUTC(attestation?.publishedAt)} />
          <Detail label="Valid until" value={unixTimeUTC(attestation?.validUntil)} />
          <Detail label="Model version" value={shortHex(attestation?.modelVersion ?? controlPlane.model_version)} />
        </div>
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-ink-dim)" }}>Configured policy</div>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Detail label="Max observation age" value={`${controlPlane.policy.max_age}s`} />
          <Detail label="SUPPORTED" value={controlPlane.policy.on_supported} />
          <Detail label="INCONCLUSIVE" value={controlPlane.policy.on_inconclusive} />
          <Detail label="CHALLENGED" value={controlPlane.policy.on_challenged} />
          <Detail label="STALE" value={controlPlane.policy.on_stale} />
          <Detail label="Evaluation freshness" value={controlPlane.fresh ? "Fresh" : "Stale / unavailable"} />
        </div>
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-ink-dim)" }}>Consumer enforcement</div>
        {enforcement ? (
          <div className="rounded-lg px-3 py-2.5 text-sm" style={{ background: enforcement.passed ? "var(--color-supported-soft)" : "var(--color-inconclusive-soft)", border: `1px solid ${enforcement.passed ? "var(--color-supported-line)" : "var(--color-inconclusive-line)"}`, color: enforcement.passed ? "var(--color-supported)" : "var(--color-inconclusive)" }}>
            <strong>{enforcement.passed ? "DemoVault enforcement verified" : "DemoVault enforcement check failed"}</strong>
            <div className="mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>
              Evidence {enforcement.exists ? enforcement.evidence_state : "not published"} → {enforcement.policy_action} · {enforcement.expected_revert ? "new exposure rejected" : "demo exposure permitted"}
            </div>
          </div>
        ) : (
          <div className="text-sm" style={{ color: "var(--color-ink-dim)" }}>Enforcement result unavailable.</div>
        )}
      </div>

      <p className="mt-4 text-xs" style={{ color: "var(--color-muted)" }}>
        Read-only browser view. No private key is exposed and no publication transaction is initiated here.
      </p>
    </Panel>
  );
}

function shortHex(value: string | undefined): string {
  if (!value) return "—";
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 text-sm">
      <span style={{ color: "var(--color-ink-dim)" }}>{label}</span>
      <span className="tnum truncate font-medium text-ink" title={value}>{value}</span>
    </div>
  );
}
