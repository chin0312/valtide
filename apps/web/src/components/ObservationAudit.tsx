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
  const evidenceRule = result?.evidence_semantics === "p1a_xstock_band_with_xperp_review_corroboration_v2"
    ? "Evidence State v2"
    : result?.evidence_semantics === "p1a_xstock_challenger_xperp_second_market_v1"
      ? "Earlier tri-source rule; recorded state and reasons are preserved"
      : result?.evidence_semantics ?? null;
  const feedStatus = runtime?.scheduler_enabled ? "Ready" : "Unavailable";
  const latestUpdate = runtime?.last_tick_status === "success" ? "Ready"
    : runtime?.last_tick_status === "failure" ? "Check Failed"
    : runtime?.last_tick_status ? runtime.last_tick_status.replace(/[_-]+/g, " ").replace(/(^|\s)\w/g, (letter) => letter.toUpperCase())
    : "Unavailable";
  return (
    <details className="rounded-[10px] text-xs" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <summary className="cursor-pointer px-5 py-3 text-ink-dim">Observation Details · {context === "Demo" ? "Scenario Observation" : context === "Historical" ? "Historical Observation" : "5-Minute Operational Observation"} · {observed ?? "Unavailable"}</summary>
      <div className="grid gap-5 border-t p-5 md:grid-cols-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        <dl className="space-y-2">
          <Field label="Observation Time (UTC)" value={observed} />
          <Field label="xStock Source" value={sourceLabel(result?.token_source)} />
          <Field label="xStock Observed (UTC)" value={result?.token_observed_at} />
          <Field label="X-Perp Source" value={sourceLabel(result?.xperp_index_source ?? result?.reference_under_test_source)} />
          <Field label="X-Perp Observed (UTC)" value={result?.xperp_index_ts ?? result?.reference_under_test_ts} />
        </dl>
        <dl className="space-y-2">
          <Field label="X-Perp Source Lag" value={ageLabel(result?.reference_under_test_age_seconds)} />
          <Field label="Trusted Anchor Age" value={ageLabel(result?.reference_age_seconds)} />
          {context === "Operational" && <Field label="Observation Age" value={ageLabel(recency)} />}
          <Field label="Model And Version" value={result ? `${result.model_id} / ${result.model_version}` : null} />
          <Field label="Calibration" value={result ? `${result.interval_calibration_type} · ${result.interval_calibration_source}` : null} />
          <Field label="Evidence Rule" value={evidenceRule} />
          <Field label="Current RiskGuard Status" value={controlPlane ? controlPlane.fresh ? "Fresh" : "Stale" : "Unavailable"} />
        </dl>
        <dl className="space-y-2">
          <Field label="Operational Feed" value={feedStatus} />
          <Field label="Latest Update" value={latestUpdate} />
          <Field label="Last Update Attempt (UTC)" value={runtime?.last_tick_attempt_at} />
          <Field label="Latest Operational Observation (UTC)" value={runtime?.last_result_timestamp} />
          <Field label="Operational Feed Error" value={runtime?.last_error ?? (runtime ? "None" : "Unavailable")} />
        </dl>
        <div className="md:col-span-3">
          <div className="eyebrow mb-2 text-muted">Source Provenance</div>
          <dl className="grid gap-2 md:grid-cols-3">{Object.entries(result?.source_provenance ?? {}).map(([key, value]) => <Field key={key} label={key} value={value} />)}</dl>
          {!Object.keys(result?.source_provenance ?? {}).length && <span className="text-muted">Not Supplied</span>}
        </div>
      </div>
    </details>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return <div className="min-w-0"><dt className="text-[10px] text-muted">{label}</dt><dd className="technical-mono break-words text-sm text-ink">{value ?? "—"}</dd></div>;
}
