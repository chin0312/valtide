import type { ReactNode } from "react";
import type { OnchainControlPlane, OnchainEnforcement, RuntimeStatus } from "../api/types";
import type { OnchainSyncStatus } from "../lib/onchain";
import { dateTimeUTC, deliveryStatusLabel, pipelineStatusLabel, unixDateTimeUTC } from "../lib/format";
import { Panel } from "./ui";

interface RegistryPanelProps {
  controlPlane?: OnchainControlPlane;
  enforcement?: OnchainEnforcement;
  runtime?: RuntimeStatus;
  sync?: OnchainSyncStatus;
  mode?: "operational" | "historical" | "demo";
  bindingConfigured?: boolean;
  isLoading?: boolean;
  isError?: boolean;
  errorDetail?: string;
}

export function RegistryPanel({ controlPlane, enforcement, runtime, sync, mode = "operational", bindingConfigured = true, isLoading, isError, errorDetail }: RegistryPanelProps) {
  if (!bindingConfigured) {
    return null;
  }
  if (isLoading) return <UnavailableRegistryPanel status="Reading X Layer" detail="Fetching the deployed attestation and policy state…" runtime={runtime} />;

  if (!controlPlane) {
    const modeDetail = mode === "demo" ? "Demo playback is read-only and does not publish." : mode === "historical" ? "Historical evidence is not substituted for current chain state." : "No deployed state was returned.";
    return <UnavailableRegistryPanel status="Unavailable" detail={`${isError ? errorDetail ?? "The deployed contracts could not be read." : "No onchain response has loaded."} ${modeDetail}`} runtime={runtime} />;
  }

  const attestation = controlPlane.attestation;
  const modeNote = mode === "demo" ? "Live deployed state — not driven by this scenario." : mode === "historical" ? "Current deployed state — not historical chain state for the selected observation." : null;

  return (
    <Panel title="X Layer Testnet" icon="chain" subtitle="Attestation delivery and collateral policy enforcement">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 text-xs">
      <div><span className="font-semibold" style={{ color: "var(--color-accent)" }}>{controlPlane.network}</span><span className="technical-mono ml-2 text-sm" style={{ color: "var(--color-muted)" }}>Chain {controlPlane.chain_id} · DEPLOYED</span></div>
        {modeNote && <span style={{ color: "var(--color-ink-dim)" }}>{modeNote}</span>}
      </div>

      <div className="grid overflow-hidden rounded-lg md:grid-cols-5" style={{ border: "1px solid var(--color-line)" }}>
        <PipelineStep index="01" label="Publication" value={pipelineStatusLabel(runtime?.last_publish_status ?? (runtime?.auto_publish_enabled ? "Ready" : "Read Only"))} />
        <PipelineStep index="02" label="ValidationRegistry" value={controlPlane.exists ? controlPlane.evidence_state : "No Attestation"} />
        <PipelineStep index="03" label="Policy" value={controlPlane.policy_action} />
        <PipelineStep index="04" label="RiskGuard" value={controlPlane.fresh ? "Fresh" : "Stale"} />
        <PipelineStep index="05" label="DemoVault" value={enforcement ? (enforcement.passed ? "Policy Check Passed" : "Check Failed") : "Unavailable"} last />
      </div>

      {sync && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}><span><strong className="text-ink">Operational → Registry · {sync.state}</strong> — {sync.detail}</span><span className="technical-mono text-sm">{unixDateTimeUTC(sync.operationalObservedAt)} / {unixDateTimeUTC(sync.registryObservedAt)}</span></div>}

      <details className="mt-4 rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
        <summary className="flex items-center justify-between px-3 py-2.5 text-xs" style={{ background: "var(--color-panel-2)", color: "var(--color-ink-dim)" }}><span>Technical Details</span><span aria-hidden style={{ color: "var(--color-accent)" }}>＋</span></summary>
        <div className="grid gap-5 p-4 lg:grid-cols-3">
          <DetailGroup title="Contracts">
            <Detail label="Registry" value={shortHex(controlPlane.registry)} />
            <Detail label="RiskGuard" value={shortHex(controlPlane.risk_guard)} />
            <Detail label="DemoVault" value={shortHex(controlPlane.demo_vault)} />
            <Detail label="Reference ID" value={shortHex(controlPlane.reference_id)} />
          </DetailGroup>
          <DetailGroup title="Registry Attestation">
            <Detail label="Available / Up To Date" value={`${controlPlane.exists ? "Yes" : "No"} / ${controlPlane.registry_fresh ? "Fresh" : "Stale"}`} />
            <Detail label="Observed" value={unixDateTimeUTC(attestation?.observedAt)} />
            <Detail label="Published" value={unixDateTimeUTC(attestation?.publishedAt)} />
            <Detail label="Valid Until" value={unixDateTimeUTC(attestation?.validUntil)} />
          </DetailGroup>
          <DetailGroup title="Policy And Delivery">
            <Detail label="Maximum Age" value={`${controlPlane.policy.max_age}s`} />
            <Detail label="SUPPORTED" value={controlPlane.policy.on_supported} />
            <Detail label="INCONCLUSIVE" value={controlPlane.policy.on_inconclusive} />
            <Detail label="CHALLENGED" value={controlPlane.policy.on_challenged} />
            <Detail label="STALE" value={controlPlane.policy.on_stale} />
          </DetailGroup>
        </div>
        {runtime?.last_publish_error && <p className="border-t px-4 py-3 text-xs" style={{ borderColor: "var(--color-line)", color: "var(--color-inconclusive)" }}>Publication Error: {runtime.last_publish_error}</p>}
      </details>
      <PublicationDetails runtime={runtime} controlPlane={controlPlane} />
    </Panel>
  );
}

function UnavailableRegistryPanel({ status, detail, runtime }: { status: string; detail: string; runtime?: RuntimeStatus }) {
  return (
    <Panel title="X Layer Testnet" icon="chain" subtitle="Current registry and policy status" right={<span className="rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)", background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>{status}</span>}>
      <div className="grid overflow-hidden rounded-lg sm:grid-cols-5" style={{ border: "1px solid var(--color-line)" }}>
        <PipelineStep index="01" label="Publication" value="Unavailable" />
        <PipelineStep index="02" label="ValidationRegistry" value="Not Available" />
        <PipelineStep index="03" label="Policy" value="Not Available" />
        <PipelineStep index="04" label="RiskGuard" value="Not Available" />
        <PipelineStep index="05" label="DemoVault" value="Not Available" last />
      </div>
      <p className="mt-3 text-[11px]" style={{ color: "var(--color-muted)" }}>X Layer is the deployed control plane where Valtide attestations become protocol policy. {detail}</p>
      <PublicationDetails runtime={runtime} />
    </Panel>
  );
}

function PublicationDetails({ runtime, controlPlane }: { runtime?: RuntimeStatus; controlPlane?: OnchainControlPlane }) {
  return <details className="mt-3 rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
    <summary className="cursor-pointer px-3 py-2.5 text-xs text-ink-dim">Publication Status</summary>
    <dl className="grid gap-3 p-4 text-xs sm:grid-cols-2">
      <Detail label="Automatic Publishing" value={runtime ? runtime.auto_publish_enabled ? "Enabled" : "Disabled" : "Unavailable"} />
      <Detail label="Publication Compatibility" value={controlPlane?.publication_compatible === true ? "Compatible" : "Read Only"} />
      <Detail label="Delivery Status" value={deliveryStatusLabel(runtime?.last_publish_status)} />
      <Detail label="Last Attempt (UTC)" value={dateTimeUTC(runtime?.last_publish_attempt_at)} />
      <Detail label="Attempted Observation" value={dateTimeUTC(runtime?.last_publish_observation_ts)} />
      <Detail label="Last Published Observation" value={dateTimeUTC(runtime?.last_published_observation_ts)} />
      <Detail label="Published At" value={unixDateTimeUTC(runtime?.last_published_at)} />
      <div className="sm:col-span-2"><dt className="text-muted">Transaction Hash</dt><dd className="technical-mono select-text break-all text-sm text-ink">{runtime?.last_publish_tx_hash ?? "—"}</dd></div>
      <div className="sm:col-span-2"><dt className="text-muted">Delivery Error</dt><dd className="break-words text-ink">{runtime?.last_publish_error ?? (runtime ? "None" : "Unavailable")}</dd></div>
    </dl>
  </details>;
}

function PipelineStep({ index, label, value, last }: { index: string; label: string; value: string; last?: boolean }) {
  return <div className="relative min-w-0 px-3 py-3" style={{ background: "var(--color-panel-2)", borderRight: last ? undefined : "1px solid var(--color-line)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{index} · {label}</div><div className="tnum mt-2 truncate text-xs font-semibold text-ink" title={value}>{value}</div>{!last && <span className="absolute -right-1 top-1/2 z-10 -translate-y-1/2" style={{ color: "var(--color-accent)", background: "var(--color-panel-2)" }}>›</span>}</div>;
}

function DetailGroup({ title, children }: { title: string; children: ReactNode }) {
  return <div><div className="eyebrow mb-2" style={{ color: "var(--color-muted)" }}>{title}</div><dl className="space-y-2">{children}</dl></div>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div className="flex min-w-0 items-center justify-between gap-3 text-xs"><dt style={{ color: "var(--color-muted)" }}>{label}</dt><dd className="technical-mono truncate text-sm font-medium text-ink" title={value}>{value}</dd></div>;
}

function shortHex(value: string | undefined): string {
  if (!value) return "—";
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}…${value.slice(-6)}`;
}
