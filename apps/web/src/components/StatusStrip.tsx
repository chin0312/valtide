import type { RuntimeStatus, ValuationResult } from "../api/types";
import { ageLabel, dateTimeUTC, sessionLabel, sourceLabel, timeUTC } from "../lib/format";

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
  const referenceWarning = r.reason_codes.includes("REFERENCE_UNDER_TEST_STALE");
  const anchorWarning = r.reason_codes.includes("UNDERLYING_REFERENCE_STALE");
  const prov = PROVENANCE[provenance];
  const isOperational = provenance === "cached";
  const observationLabel = isOperational ? "Operational observation" : provenance === "diagnostic" ? "Diagnostic observation" : "Scenario observation";
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl px-4 py-2.5 text-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
      <span className="font-semibold text-ink">{r.asset}</span>
      <Item label="Validating" value={sourceLabel(r.reference_under_test_source)} />
      <Item label="Session" value={sessionLabel(r.market_state)} />
      <Item
        label={isOperational ? "Canonical 5m observation" : observationLabel}
        value={isOperational ? dateTimeUTC(r.timestamp) : timeUTC(r.timestamp)}
        title={isOperational ? "Successful warmed result for this canonical 5-minute observation window." : `Scenario/diagnostic timestamp: ${r.timestamp}`}
      />

      <AgeTag label="Reference source lag:" seconds={r.reference_under_test_age_seconds} warning={referenceWarning} title="Age of the reference-under-test source relative to this valuation observation; it is not the wall-clock age of the operational result." />
      <AgeTag label="Trusted anchor age:" seconds={r.reference_age_seconds} warning={anchorWarning} title="Age of the latest trusted underlying anchor at this valuation observation; it is not the wall-clock age of the operational result." />

      {runtime && (
        <span className="text-xs" style={{ color: runtime.last_tick_status === "failure" ? "var(--color-inconclusive)" : "var(--color-ink-dim)" }} title={runtime.last_error ?? "Warmed live scheduler status"}>
          Last scheduler attempt: {dateTimeUTC(runtime.last_tick_attempt_at)} · {runtime.scheduler_enabled ? (runtime.last_tick_status ?? "idle") : "off"}
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
          RiskGuard {onchainFresh ? "fresh" : "stale"}
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

function AgeTag({ label, seconds, warning, title }: { label: string; seconds: number | null; warning: boolean; title: string }) {
  const display = ageLabel(seconds);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ background: warning ? "var(--color-inconclusive-soft)" : "var(--color-panel-2)", color: warning ? "var(--color-inconclusive)" : "var(--color-ink)", border: `1px solid ${warning ? "var(--color-inconclusive-line)" : "var(--color-line)"}` }} title={title}>
      {label} {display}{warning ? " · backend flagged" : ""}
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
