import type { OnchainControlPlane, RuntimeStatus, ValuationResult } from "../api/types";
import { ageLabel, sourceLabel } from "../lib/format";

// Ages are backend measurements at the selected observation, not risk buckets.
export function ObservationAudit({ result, context, runtime, controlPlane }: {
  result?: ValuationResult;
  context: "Operational" | "Historical" | "Demo";
  runtime?: RuntimeStatus;
  controlPlane?: OnchainControlPlane;
}) {
  const observed = result?.timestamp;
  const recency = observed ? Math.max(0, Math.floor((Date.now() - Date.parse(observed)) / 1000)) : null;
  return (
    <details className="rounded-[10px] text-xs" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <summary className="cursor-pointer px-5 py-3 text-ink-dim">Observation audit · {context === "Demo" ? "Scenario observation" : context === "Historical" ? "Historical panel observation" : "Canonical 5m operational observation"} · {observed ?? "unavailable"}</summary>
      <div className="grid gap-5 border-t p-5 md:grid-cols-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        <dl className="space-y-2">
          <Field label="Observation (UTC)" value={observed} />
          <Field label="Token source" value={sourceLabel(result?.token_source)} />
          <Field label="Token observed (UTC)" value={result?.token_observed_at} />
          <Field label="Reference source" value={sourceLabel(result?.reference_under_test_source)} />
          <Field label="Reference observed (UTC)" value={result?.reference_under_test_ts} />
        </dl>
        <dl className="space-y-2">
          <Field label="Reference source lag" value={ageLabel(result?.reference_under_test_age_seconds)} />
          <Field label="Trusted-anchor age" value={ageLabel(result?.reference_age_seconds)} />
          {context === "Operational" && <Field label="Observation elapsed time" value={ageLabel(recency)} />}
          <Field label="Model / version" value={result ? `${result.model_id} / ${result.model_version}` : null} />
          <Field label="Calibration" value={result ? `${result.interval_calibration_type} · ${result.interval_calibration_source}` : null} />
          <Field label="Current RiskGuard" value={controlPlane ? controlPlane.fresh ? "fresh" : "stale" : "unavailable"} />
        </dl>
        <dl className="space-y-2">
          <Field label="Current live scheduler" value={runtime ? runtime.scheduler_enabled ? "enabled" : "disabled" : "unavailable"} />
          <Field label="Last tick status" value={runtime?.last_tick_status} />
          <Field label="Last attempt (UTC)" value={runtime?.last_tick_attempt_at} />
          <Field label="Latest result (UTC)" value={runtime?.last_result_timestamp} />
          <Field label="Scheduler error" value={runtime?.last_error ?? (runtime ? "None" : "Unavailable")} />
        </dl>
        <div className="md:col-span-3">
          <div className="eyebrow mb-2 text-muted">Selected observation source provenance</div>
          <dl className="grid gap-2 md:grid-cols-3">{Object.entries(result?.source_provenance ?? {}).map(([key, value]) => <Field key={key} label={key} value={value} />)}</dl>
          {!Object.keys(result?.source_provenance ?? {}).length && <span className="text-muted">Not supplied</span>}
        </div>
      </div>
    </details>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return <div className="min-w-0"><dt className="text-[10px] text-muted">{label}</dt><dd className="tnum break-words text-ink">{value ?? "—"}</dd></div>;
}
