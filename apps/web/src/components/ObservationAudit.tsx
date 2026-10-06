import type { OnchainControlPlane, RuntimeStatus, ValuationResult } from "../api/types";
import { ageLabel, dateTimeUTC, modelDisplayName, sourceLabel, timeUTC } from "../lib/format";

const EVIDENCE_STATE_V2 = "p1a_xstock_band_with_xperp_review_corroboration_v2";

// Ages are backend measurements at the selected observation, not risk buckets.
export function ObservationAudit({ result, context, runtime, controlPlane }: {
  result?: ValuationResult;
  context: "Operational" | "Historical" | "Demo";
  runtime?: RuntimeStatus;
  controlPlane?: OnchainControlPlane;
}) {
  const observed = result?.timestamp;
  const recency = observed ? Math.max(0, Math.floor((Date.now() - Date.parse(observed)) / 1000)) : null;
  const operational = context === "Operational";
  const runtimeHasError = operational && !!runtime && (runtime.last_tick_status === "failure" || !!runtime.last_error);
  const feedStatus = !runtime?.scheduler_enabled ? "Unavailable"
    : runtimeHasError ? "Check Required"
      : runtime.last_tick_status === "success" ? "Ready" : "Starting";
  const titleTime = context === "Demo" ? timeUTC(observed) : dateTimeUTC(observed);
  const olderRule = !!result?.evidence_semantics && result.evidence_semantics !== EVIDENCE_STATE_V2;

  return (
    <details className="rounded-[10px] text-xs" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <summary className="cursor-pointer px-5 py-3 text-ink-dim">Observation Details · {context} · {titleTime}</summary>
      <div className="grid gap-5 border-t p-5 md:grid-cols-3" style={{ borderColor: "var(--color-line-subtle)" }}>
        <dl className="space-y-2">
          <Field label="Observation Time" value={dateTimeUTC(observed)} />
          <Field label="xStock Source" value={sourceLabel(result?.token_source)} />
          <Field label="xStock Observed" value={dateTimeUTC(result?.token_observed_at)} />
          <Field label="X-Perp Source" value={sourceLabel(result?.xperp_index_source ?? result?.reference_under_test_source)} />
          <Field label="X-Perp Observed" value={dateTimeUTC(result?.xperp_index_ts ?? result?.reference_under_test_ts)} />
        </dl>
        <dl className="space-y-2">
          <Field label="X-Perp Age" value={ageLabel(result?.reference_under_test_age_seconds)} />
          <Field label="Underlying Price Age" value={ageLabel(result?.reference_age_seconds)} />
          {operational && <Field label="Observation Age" value={ageLabel(recency)} />}
          <Field label="Model" value={result ? modelDisplayName(result.model_version) : null} />
          {olderRule && <Field label="Classification Version" value="Earlier Rule" />}
          {operational && controlPlane && <Field label="Current RiskGuard Status" value={controlPlane.fresh ? "Fresh" : "Stale"} />}
        </dl>
        {operational && <dl className="space-y-2">
          <Field label="Feed Status" value={feedStatus} />
          <Field label="Latest Observation" value={dateTimeUTC(runtime?.last_result_timestamp)} />
          {runtimeHasError && <Field label="Last Update Attempt" value={dateTimeUTC(runtime?.last_tick_attempt_at)} />}
          {runtimeHasError && <Field label="Feed Error" value={runtime?.last_error ?? "Latest update failed."} />}
        </dl>}
        <div className="md:col-span-3">
          <div className="eyebrow mb-2 text-muted">Source Provenance</div>
          <dl className="grid gap-2 md:grid-cols-3">{Object.entries(result?.source_provenance ?? {}).map(([key, value]) => <Field key={key} label={provenanceLabel(key)} value={value} />)}</dl>
          {!Object.keys(result?.source_provenance ?? {}).length && <span className="text-muted">Not Supplied</span>}
        </div>
      </div>
    </details>
  );
}

function provenanceLabel(key: string): string {
  const known: Record<string, string> = {
    token_source: "Token Source",
    underlying_source: "Underlying Source",
    scenario: "Scenario",
  };
  return known[key] ?? key.replace(/[_-]+/g, " ").replace(/(^|\s)\w/g, (letter) => letter.toUpperCase());
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return <div className="min-w-0"><dt className="text-[10px] text-muted">{label}</dt><dd className="technical-mono break-words text-sm text-ink">{value ?? "—"}</dd></div>;
}
