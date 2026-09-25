import type { RuntimeStatus, ValuationResult } from "../api/types";
import { sessionLabel, staleness, timeUTC } from "../lib/format";

export type Provenance = "live" | "cached" | "demo-scenario" | "demo-fixture";

const PROVENANCE: Record<Provenance, { label: string; tone: "ok" | "warn" }> = {
  live: { label: "Live pipeline", tone: "ok" },
  cached: { label: "Warmed cache", tone: "ok" },
  "demo-scenario": { label: "Demo (backend scenario)", tone: "warn" },
  "demo-fixture": { label: "Demo (offline fixture)", tone: "warn" },
};

export function StatusStrip({
  r,
  provenance,
  runtime,
}: {
  r: ValuationResult;
  provenance: Provenance;
  runtime?: RuntimeStatus;
}) {
  const age = staleness(r.reference_age_seconds);
  const prov = PROVENANCE[provenance];
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-sm px-4 py-2.5 text-xs" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <span className="tnum font-medium text-ink">{r.asset}</span>
      <Item label="Validating" value={r.reference_under_test_source} />
      <Item label="Session" value={sessionLabel(r.market_state)} />
      <Item label="Observed" value={timeUTC(r.timestamp)} />

      <span className="inline-flex items-center gap-1.5 rounded-sm px-2 py-0.5 font-mono text-[10px]" style={{ background: age.soft, color: age.fg, border: `1px solid ${age.line}` }} title="Age of the last trusted underlying price">
        underlying {age.label}
      </span>

      {runtime && (
        <span className="text-xs" style={{ color: "var(--color-ink-dim)" }} title="Warmed live scheduler status">
          scheduler {runtime.scheduler_enabled ? (runtime.last_tick_status ?? "idle") : "off"}
        </span>
      )}

      <span
        className="ml-auto inline-flex items-center gap-1.5 rounded-sm px-2 py-1 font-mono text-[10px] uppercase tracking-[0.06em]"
        style={{
          background: "var(--color-panel-2)",
          color: prov.tone === "ok" ? "var(--color-accent)" : "var(--color-ink-dim)",
          border: "1px solid var(--color-line)",
        }}
      >
        <span aria-hidden>{prov.tone === "ok" ? "●" : "◇"}</span>
        {prov.label}
      </span>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ color: "var(--color-ink-dim)" }}>
      {label}: <span className="tnum font-medium text-ink">{value}</span>
    </span>
  );
}
