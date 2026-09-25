import type { OnchainControlPlane, OnchainEnforcement, RuntimeStatus } from "../api/types";
import type { OnchainSyncStatus } from "../lib/onchain";
import { Panel } from "../components/ui";
import { unixDateTimeUTC } from "../lib/format";

interface RegistryPanelProps {
  controlPlane?: OnchainControlPlane;
  enforcement?: OnchainEnforcement;
  runtime?: RuntimeStatus;
  sync?: OnchainSyncStatus;
  mode?: "operational" | "historical" | "demo";
  isLoading?: boolean;
  isError?: boolean;
  errorDetail?: string;
}

export function RegistryPanel({ controlPlane, enforcement, runtime, sync, mode = "operational", isLoading, isError, errorDetail }: RegistryPanelProps) {
  if (isLoading) {
    return <Panel title="X Layer Control Plane" subtitle="Backend publisher → Registry → RiskGuard → DemoVault">Loading deployed control-plane state…</Panel>;
  }

  if (!controlPlane) {
    return (
      <Panel title="X Layer Control Plane" subtitle="Backend publisher → Registry → RiskGuard → DemoVault">
        <div className="rounded-lg px-3 py-3 text-sm" style={{ background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-inconclusive-line)", color: "var(--color-inconclusive)" }}>
          <strong>Control-plane status unavailable.</strong>
          <div className="mt-1" style={{ color: "var(--color-ink-dim)" }}>{isError ? errorDetail ?? "The backend could not read the deployed X Layer contracts." : "No onchain response has been loaded."}</div>
        </div>
        {mode === "demo" && <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>Live deployed control plane — not driven by this scenario replay.</p>}
        {mode === "historical" && <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>Current deployed control plane — not historical state for the selected observation.</p>}
        <p className="mt-3 text-xs" style={{ color: "var(--color-muted)" }}>
          Publication is backend-controlled. The browser is read-only and never holds the publisher signer.
        </p>
      </Panel>
    );
  }

  const attestation = controlPlane.attestation;
  return (
    <Panel title="X Layer Control Plane" subtitle="Backend publisher → Registry → curator policy → RiskGuard → DemoVault">
      {mode === "demo" ? (
        <div className="rounded-lg px-3 py-2.5 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          <strong className="text-ink">Live deployed control plane</strong> — not driven by this scenario replay.
        </div>
      ) : mode === "historical" ? (
        <div className="rounded-lg px-3 py-2.5 text-sm" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
          <strong className="text-ink">Current deployed control plane</strong> — not historical Registry or RiskGuard state for the selected observation.
        </div>
      ) : sync ? (
        <SyncBanner sync={sync} />
      ) : null}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2.5" style={{ background: "var(--color-supported-soft)", border: "1px solid var(--color-supported-line)" }}>
        <div className="text-sm font-semibold" style={{ color: "var(--color-supported)" }}>{controlPlane.network}</div>
        <div className="text-xs tnum" style={{ color: "var(--color-ink-dim)" }}>chain {controlPlane.chain_id} · deployed</div>
      </div>

      <div className="mt-4 grid gap-x-4 gap-y-2 sm:grid-cols-2">
        <Detail label="Registry" value={shortHex(controlPlane.registry)} />
        <Detail label="RiskGuard" value={shortHex(controlPlane.risk_guard)} />
        <Detail label="DemoVault" value={shortHex(controlPlane.demo_vault)} />
        <Detail label="Reference ID" value={shortHex(controlPlane.reference_id)} />
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <SectionTitle>Registry attestation</SectionTitle>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Detail label="Attestation exists" value={controlPlane.exists ? "Yes" : "No attestation published"} />
          <Detail label="Registry fresh" value={controlPlane.registry_fresh ? "Yes" : "No"} />
          <Detail label="Evidence State" value={controlPlane.exists ? controlPlane.evidence_state : "—"} />
          <Detail label="Observed" value={unixDateTimeUTC(attestation?.observedAt)} />
          <Detail label="Published" value={unixDateTimeUTC(attestation?.publishedAt)} />
          <Detail label="Valid until" value={unixDateTimeUTC(attestation?.validUntil)} />
          <Detail label="Model version hash" value={shortHex(attestation?.modelVersion ?? controlPlane.model_version)} />
          <Detail label="Reference ID" value={shortHex(controlPlane.reference_id)} />
        </div>
      </div>

      {runtime && <PublicationStatus runtime={runtime} />}

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <SectionTitle>Curator policy</SectionTitle>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Detail label="Max observation age" value={`${controlPlane.policy.max_age}s`} />
          <Detail label="SUPPORTED" value={controlPlane.policy.on_supported} />
          <Detail label="INCONCLUSIVE" value={controlPlane.policy.on_inconclusive} />
          <Detail label="CHALLENGED" value={controlPlane.policy.on_challenged} />
          <Detail label="STALE" value={controlPlane.policy.on_stale} />
          <Detail label="Current RiskGuard action" value={controlPlane.policy_action} />
        </div>
        <p className="mt-2 text-xs" style={{ color: "var(--color-muted)" }}>The deployed consuming application owns this mapping; the frontend reads it but does not edit it.</p>
      </div>

      <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
        <SectionTitle>Consumer enforcement</SectionTitle>
        {enforcement ? (
          <div className="rounded-lg px-3 py-2.5 text-sm" style={{ background: enforcement.passed ? "var(--color-supported-soft)" : "var(--color-inconclusive-soft)", border: `1px solid ${enforcement.passed ? "var(--color-supported-line)" : "var(--color-inconclusive-line)"}`, color: enforcement.passed ? "var(--color-supported)" : "var(--color-inconclusive)" }}>
            <strong>{enforcement.passed ? "DemoVault enforcement verified" : "DemoVault enforcement check failed"}</strong>
            <div className="mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>
              Registry Evidence: {enforcement.exists ? enforcement.evidence_state : "no attestation"} · RiskGuard: {enforcement.policy_action} · {enforcementOutcome(enforcement)}
            </div>
            <div className="mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>
              Enforcement readback: {enforcement.exists ? "attestation exists" : "attestation absent"} · {enforcement.fresh ? "fresh" : "stale"}
            </div>
          </div>
        ) : (
          <div className="text-sm" style={{ color: "var(--color-ink-dim)" }}>Enforcement result unavailable.</div>
        )}
      </div>

      <p className="mt-4 text-xs" style={{ color: "var(--color-muted)" }}>
        Publication is backend-controlled. The browser is read-only, never holds the publisher signer, and never initiates a publication transaction.
      </p>
    </Panel>
  );
}

function SyncBanner({ sync }: { sync: OnchainSyncStatus }) {
  const tone = sync.state === "SYNCED" ? "supported" : sync.state === "BEHIND" ? "inconclusive" : "challenged";
  const colors = tone === "supported"
    ? { fg: "var(--color-supported)", soft: "var(--color-supported-soft)", line: "var(--color-supported-line)" }
    : tone === "inconclusive"
      ? { fg: "var(--color-inconclusive)", soft: "var(--color-inconclusive-soft)", line: "var(--color-inconclusive-line)" }
      : { fg: "var(--color-challenged)", soft: "var(--color-challenged-soft)", line: "var(--color-challenged-line)" };
  return (
    <div className="rounded-lg px-3 py-2.5 text-sm" style={{ background: colors.soft, border: `1px solid ${colors.line}`, color: colors.fg }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <strong>Onchain sync · {sync.state}</strong>
        <span className="text-xs" style={{ color: "var(--color-ink-dim)" }}>freshness is separate from sync</span>
      </div>
      <div className="mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>{sync.detail}</div>
      <div className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
        <span>Operational observed: <strong className="text-ink">{unixDateTimeUTC(sync.operationalObservedAt)}</strong></span>
        <span>Registry observed: <strong className="text-ink">{unixDateTimeUTC(sync.registryObservedAt)}</strong></span>
      </div>
    </div>
  );
}

function enforcementOutcome(enforcement: OnchainEnforcement): string {
  if (enforcement.policy_action === "ALLOW") return "ALLOWED";
  if (enforcement.policy_action === "MONITOR") return "MONITORED";
  if (enforcement.policy_action === "REQUIRE_REVIEW") return "BLOCKED PENDING REVIEW";
  if (enforcement.policy_action === "RESTRICT_NEW_RISK") return "NEW EXPOSURE BLOCKED";
  return enforcement.expected_revert ? "NEW EXPOSURE BLOCKED" : "OUTCOME UNAVAILABLE";
}

function PublicationStatus({ runtime }: { runtime: RuntimeStatus }) {
  return (
    <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--color-line)" }}>
      <SectionTitle>Publication delivery</SectionTitle>
      <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
        <Detail label="Auto publication" value={runtime.auto_publish_enabled ? "Enabled" : "Disabled"} />
        <Detail label="Last status" value={runtime.last_publish_status ?? "—"} />
        <Detail label="Last attempt at" value={unixDateTimeUTC(runtime.last_publish_attempt_at ? Date.parse(runtime.last_publish_attempt_at) / 1000 : null)} />
        <Detail label="Observation attempted" value={unixDateTimeUTC(runtime.last_publish_observation_ts ? Date.parse(runtime.last_publish_observation_ts) / 1000 : null)} />
        <Detail label="Last published observation" value={unixDateTimeUTC(runtime.last_published_observation_ts ? Date.parse(runtime.last_published_observation_ts) / 1000 : null)} />
        <Detail label="Published at" value={unixDateTimeUTC(runtime.last_published_at)} />
        <Detail label="Transaction hash" value={shortHex(runtime.last_publish_tx_hash ?? undefined)} />
      </div>
      {runtime.last_publish_error && <p className="mt-2 text-xs" style={{ color: "var(--color-inconclusive)" }}>Publication error: {runtime.last_publish_error}</p>}
      <p className="mt-2 text-xs" style={{ color: "var(--color-muted)" }}>Backend-controlled delivery status; the browser is read-only and never holds the publisher signer.</p>
    </div>
  );
}

function shortHex(value: string | undefined): string {
  if (!value) return "—";
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function SectionTitle({ children }: { children: string }) {
  return <div className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-ink-dim)" }}>{children}</div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 text-sm">
      <span style={{ color: "var(--color-ink-dim)" }}>{label}</span>
      <span className="tnum truncate font-medium text-ink" title={value}>{value}</span>
    </div>
  );
}
