import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError, fetchDemoReplay, fetchHealth, fetchLiveValuation, fetchRuntime } from "./api/client";
import type { ValuationResult } from "./api/types";
import { StatusStrip, type Provenance } from "./components/StatusStrip";
import { PolicyActionPanel } from "./components/PolicyActionPanel";
import { RegistryPanel } from "./components/RegistryPanel";
import { ValidationOverview } from "./views/ValidationOverview";
import { ReferenceComparison } from "./views/ReferenceComparison";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ModelEvidence } from "./views/ModelEvidence";

type Mode = "live" | "demo";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 15_000 });
  const [manualMode, setManualMode] = useState<Mode | null>(null);
  // Prefer live when the backend is reachable; fall back to demo otherwise.
  const mode: Mode = manualMode ?? (health.data ? "live" : "demo");

  return (
    <div className="mx-auto min-h-full max-w-[1480px] px-4 py-5 sm:px-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        <div className="flex items-center gap-5">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ color: "var(--color-accent)" }}>Independent valuation control</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-ink">Valtide</h1>
          </div>
          <div className="hidden h-8 w-px sm:block" style={{ background: "var(--color-line)" }} />
          <div className="hidden sm:block">
            <div className="text-[13px] font-medium text-ink">Evidence Monitor</div>
            <p className="text-xs" style={{ color: "var(--color-muted)" }}>Validate → Diagnose → Triage → Guard</p>
          </div>
        </div>
        <ModeToggle mode={mode} onChange={setManualMode} backendUp={!!health.data} />
      </header>

      <Watchlist />
      {mode === "live" ? <LiveView /> : <DemoView />}
    </div>
  );
}

function ModeToggle({ mode, onChange, backendUp }: { mode: Mode; onChange: (m: Mode) => void; backendUp: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.08em]" style={{ color: "var(--color-muted)" }} title={backendUp ? "Backend reachable" : "Backend unreachable"}>
        <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: backendUp ? "var(--color-accent)" : "var(--color-muted)" }} />
        {backendUp ? "backend online" : "backend offline"}
      </span>
      <div className="inline-flex overflow-hidden rounded-sm" style={{ border: "1px solid var(--color-line)" }}>
        {(["live", "demo"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => onChange(m)}
            disabled={m === "live" && !backendUp}
            className="px-3 py-1.5 text-xs font-medium capitalize disabled:cursor-not-allowed disabled:opacity-30"
            style={mode === m ? { background: "var(--color-accent-soft, #affc4117)", color: "var(--color-accent)" } : { background: "var(--color-panel)", color: "var(--color-muted)" }}
          >
            {m}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Live mode: real pipeline — DexScreener + Alpaca + OKX → quant runtime → validation. */
function LiveView() {
  const live = useQuery({ queryKey: ["live"], queryFn: fetchLiveValuation, refetchInterval: 20_000, retry: 0 });
  const runtime = useQuery({ queryKey: ["runtime"], queryFn: fetchRuntime, refetchInterval: 20_000, retry: 0 });

  if (live.isLoading) return <Message>Running live inference through the pipeline…</Message>;
  if (live.isError || !live.data) {
    const detail = live.error instanceof ApiError ? live.error.detail : "backend unreachable";
    return (
      <Message>
        <div className="font-medium text-ink">Live inference unavailable</div>
        <p className="mx-auto mt-1 max-w-md text-sm">
          {detail}. The live path needs the backend running with market-data access (Alpaca / DexScreener /
          OKX). Switch to <strong>Demo</strong> above to see the flow on the bundled scenario.
        </p>
      </Message>
    );
  }

  const r = live.data;
  return (
    <div className="space-y-4">
      <StatusStrip r={r} provenance="live" runtime={runtime.data} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <ValidationOverview r={r} />
        <PolicyActionPanel current={r.evidence_state} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.8fr)]">
        <ReferenceComparison r={r} />
        <ModelEvidence results={[r]} source="scenario" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.8fr)]">
        <div />
        <RegistryPanel />
      </div>
      <Footer r={r} live />
    </div>
  );
}

/** Demo mode: point-in-time scenario replay (backend if up, else bundled fixture). */
function DemoView() {
  const { data, isLoading } = useQuery({ queryKey: ["demo-replay"], queryFn: () => fetchDemoReplay(), staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  if (isLoading || !data) return <Message>Loading demo scenario…</Message>;

  const r = data.results[Math.min(index, data.results.length - 1)];
  const provenance: Provenance = data.source === "live" ? "demo-scenario" : "demo-fixture";

  return (
    <div className="space-y-4">
      <StatusStrip r={r} provenance={provenance} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <ValidationOverview r={r} />
        <PolicyActionPanel current={r.evidence_state} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.8fr)]">
        <div>
          <HistoricalReplay results={data.results} index={index} setIndex={setIndex} playing={playing} setPlaying={setPlaying} />
        </div>
        <ReferenceComparison r={r} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.8fr)]">
        <ModelEvidence results={data.results} source="scenario" />
        <RegistryPanel />
      </div>
      <Footer r={r} />
    </div>
  );
}

function Footer({ r, live }: { r: ValuationResult; live?: boolean }) {
  return (
    <footer className="border-t pt-4 text-left font-mono text-[10px] uppercase tracking-[0.06em]" style={{ borderColor: "var(--color-line-subtle)", color: "var(--color-muted)" }}>
      Model {r.model_id} {r.model_version} · reference {r.reference_under_test_source}
      {live ? " · live inference, updates every 20s" : ""} · hackathon research prototype, not a production oracle
    </footer>
  );
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <div className="card-shadow rounded-sm p-10 text-center" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", color: "var(--color-ink-dim)" }}>
      {children}
    </div>
  );
}

function Watchlist() {
  const items = [
    { symbol: "NVDAx", state: "ACTIVE", meta: "selected evidence stream" },
    { symbol: "SPYx", state: "P1", meta: "coming soon" },
    { symbol: "TSLAx", state: "P1", meta: "coming soon" },
  ];
  return (
    <div className="mb-4 flex overflow-x-auto rounded-sm" style={{ border: "1px solid var(--color-line-subtle)", background: "var(--color-panel)" }}>
      <div className="flex items-center px-3 font-mono text-[10px] uppercase tracking-[0.1em]" style={{ color: "var(--color-muted)", borderRight: "1px solid var(--color-line-subtle)" }}>Watchlist</div>
      {items.map((item, index) => (
        <div key={item.symbol} className="min-w-[190px] px-4 py-2.5" style={{ borderRight: index < items.length - 1 ? "1px solid var(--color-line-subtle)" : undefined, opacity: index === 0 ? 1 : 0.48 }}>
          <div className="flex items-center justify-between gap-4">
            <span className="tnum text-sm font-medium text-ink">{item.symbol}</span>
            <span className="font-mono text-[9px] uppercase tracking-[0.08em]" style={{ color: index === 0 ? "var(--color-accent)" : "var(--color-muted)" }}>{item.state}</span>
          </div>
          <div className="mt-0.5 text-[11px]" style={{ color: "var(--color-muted)" }}>{item.meta}</div>
        </div>
      ))}
    </div>
  );
}
