import type { RuntimeStatus, ValuationResult } from "../api/types";
import { sessionLabel, staleness, timeUTC } from "../lib/format";

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
  const referenceAge = staleness(r.reference_under_test_age_seconds);
  const anchorAge = staleness(r.reference_age_seconds);
  const prov = PROVENANCE[provenance];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl px-4 py-2.5 text-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
      <span className="font-semibold text-ink">{r.asset}</span>
      <Item label="Validating" value={r.reference_under_test_source} />
      <Item label="Session" value={sessionLabel(r.market_state)} />
      <Item label="Observed" value={timeUTC(r.timestamp)} />

      <AgeTag label="reference under test" age={referenceAge} title="Display-level age of the reference being validated; the authoritative onchain freshness decision is shown in the control-plane panel." />
      <AgeTag label="trusted anchor" age={anchorAge} title="Display-level age of the latest trusted underlying anchor used by the challenger." />

      {runtime && (
        <span className="text-xs" style={{ color: "var(--color-ink-dim)" }} title="Warmed live scheduler status">
          scheduler {runtime.scheduler_enabled ? (runtime.last_tick_status ?? "idle") : "off"}
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

function AgeTag({ label, age, title }: { label: string; age: ReturnType<typeof staleness>; title: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium" style={{ background: age.soft, color: age.fg, border: `1px solid ${age.line}` }} title={title}>
      {label} {age.label}
    </span>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ color: "var(--color-ink-dim)" }}>
      {label}: <span className="tnum font-medium text-ink">{value}</span>
    </span>
  );
}
