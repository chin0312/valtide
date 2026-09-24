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
    <div className="mx-auto min-h-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Valtide</h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--color-ink-dim)" }}>
            Is this tokenized-equity collateral price still supported by the market?
          </p>
        </div>
        <ModeToggle mode={mode} onChange={setManualMode} backendUp={!!health.data} />
      </header>

      {mode === "live" ? <LiveView /> : <DemoView />}
    </div>
  );
}

function ModeToggle({ mode, onChange, backendUp }: { mode: Mode; onChange: (m: Mode) => void; backendUp: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} title={backendUp ? "Backend reachable" : "Backend unreachable"}>
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} />
        {backendUp ? "backend online" : "backend offline"}
      </span>
      <div className="inline-flex overflow-hidden rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
        {(["live", "demo"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => onChange(m)}
            disabled={m === "live" && !backendUp}
            className="px-3 py-1.5 text-sm font-medium capitalize disabled:cursor-not-allowed disabled:opacity-40"
            style={mode === m ? { background: "var(--color-accent)", color: "#fff" } : { background: "#fff", color: "var(--color-ink-dim)" }}
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
    <div className="space-y-6">
      <StatusStrip r={r} provenance="live" runtime={runtime.data} />
      <ValidationOverview r={r} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ReferenceComparison r={r} /></div>
        <PolicyActionPanel current={r.evidence_state} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ModelEvidence results={[r]} source="scenario" /></div>
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
    <div className="space-y-6">
      <StatusStrip r={r} provenance={provenance} />
      <ValidationOverview r={r} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ReferenceComparison r={r} /></div>
        <PolicyActionPanel current={r.evidence_state} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <HistoricalReplay results={data.results} index={index} setIndex={setIndex} playing={playing} setPlaying={setPlaying} />
        </div>
        <RegistryPanel />
      </div>
      <ModelEvidence results={data.results} source="scenario" />
      <Footer r={r} />
    </div>
  );
}

function Footer({ r, live }: { r: ValuationResult; live?: boolean }) {
  return (
    <footer className="pt-2 text-center text-xs" style={{ color: "var(--color-muted)" }}>
      Model {r.model_id} {r.model_version} · reference {r.reference_under_test_source}
      {live ? " · live inference, updates every 20s" : ""} · hackathon research prototype, not a production oracle
    </footer>
  );
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <div className="card-shadow rounded-2xl bg-white p-10 text-center" style={{ border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
      {children}
    </div>
  );
}
