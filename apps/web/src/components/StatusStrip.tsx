import type { RuntimeStatus, ValuationResult } from "../api/types";
import { ageLabel, sessionLabel, sourceLabel, staleness, timeUTC } from "../lib/format";

export type Provenance = "cached" | "diagnostic" | "demo-scenario" | "demo-fixture";

const PROVENANCE: Record<Provenance, { label: string; tone: "ok" | "warn" }> = {
  cached: { label: "Warmed operational state", tone: "ok" },
  diagnostic: { label: "Cold-start diagnostic", tone: "warn" },
  "demo-scenario": { label: "Demo (backend scenario)", tone: "warn" },
  "demo-fixture": { label: "Demo (offline fixture)", tone: "warn" },
};

export function StatusStrip({
  r,
  provenance,
  runtime,
  onchainFresh,
}: {
  r: ValuationResult;
  provenance: Provenance;
  runtime?: RuntimeStatus;
  onchainFresh?: boolean;
}) {
  const operationalAgeSeconds = relativeAgeSeconds(r.timestamp);
  const referenceAge = staleness(r.reference_under_test_age_seconds);
  const anchorAge = staleness(r.reference_age_seconds);
  const prov = PROVENANCE[provenance];
  const isOperational = provenance === "cached";
  const observationLabel = isOperational ? "Operational observation" : provenance === "diagnostic" ? "Diagnostic observation" : "Scenario observation";
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl px-4 py-2.5 text-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
      <span className="font-semibold text-ink">{r.asset}</span>
      <Item label="Validating" value={sourceLabel(r.reference_under_test_source)} />
      <Item label="Session" value={sessionLabel(r.market_state)} />
      <Item
        label={observationLabel}
        value={isOperational ? `${ageLabel(operationalAgeSeconds)} ago` : timeUTC(r.timestamp)}
        title={isOperational ? `UTC observation timestamp: ${r.timestamp}` : `Scenario/diagnostic timestamp: ${r.timestamp}`}
      />

      <AgeTag label="Reference source lag:" age={referenceAge} status={false} title="Age of the reference-under-test source relative to this valuation observation; it is not the wall-clock age of the operational result." />
      <AgeTag label="Trusted anchor age:" age={anchorAge} status={false} title="Age of the latest trusted underlying anchor at this valuation observation; it is not the wall-clock age of the operational result." />

      {runtime && (
        <span className="text-xs" style={{ color: runtime.last_tick_status === "failure" ? "var(--color-inconclusive)" : "var(--color-ink-dim)" }} title={runtime.last_error ?? "Warmed live scheduler status"}>
          scheduler {runtime.scheduler_enabled ? (runtime.last_tick_status ?? "idle") : "off"}
          {runtime.last_tick_status === "failure" && " · degraded"}
        </span>
      )}

      {onchainFresh != null && (
        <span
          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
          style={{
            background: onchainFresh ? "var(--color-supported-soft)" : "var(--color-inconclusive-soft)",
            color: onchainFresh ? "var(--color-supported)" : "var(--color-inconclusive)",
            border: `1px solid ${onchainFresh ? "var(--color-supported-line)" : "var(--color-inconclusive-line)"}`,
          }}
          title="Freshness returned by the X Layer RiskGuard evaluation"
        >
          onchain {onchainFresh ? "fresh" : "stale"}
        </span>
      )}

      <span
        className="ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
        style={{
          background: prov.tone === "ok" ? "var(--color-supported-soft)" : "var(--color-inconclusive-soft)",
          color: prov.tone === "ok" ? "var(--color-supported)" : "var(--color-inconclusive)",
          border: `1px solid ${prov.tone === "ok" ? "var(--color-supported-line)" : "var(--color-inconclusive-line)"}`,
        }}
      >
        <span aria-hidden>{prov.tone === "ok" ? "●" : "◆"}</span>
        {prov.label}
      </span>
    </div>
  );
}

function AgeTag({ label, age, status = true, title }: { label: string; age: ReturnType<typeof staleness>; status?: boolean; title: string }) {
  const display = status ? age.label : age.label.split(" · ")[0];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ background: age.soft, color: age.fg, border: `1px solid ${age.line}` }} title={title}>
      {label} {display}
    </span>
  );
}

function Item({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span style={{ color: "var(--color-ink-dim)" }} title={title}>
      {label}: <span className="tnum font-medium text-ink">{value}</span>
    </span>
  );
}

function relativeAgeSeconds(timestamp: string): number | null {
  const observedMs = Date.parse(timestamp);
  if (!Number.isFinite(observedMs)) return null;
  return Math.max(0, Math.floor((Date.now() - observedMs) / 1000));
}
