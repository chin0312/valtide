import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  fetchDemoReplay,
  fetchHealth,
  fetchHistoricalReplay,
  fetchLiveDiagnostic,
  fetchOnchain,
  fetchOnchainEnforcement,
  fetchOperationalHistory,
  fetchOperationalValuation,
  fetchRuntime,
} from "./api/client";
import type { ValuationResult } from "./api/types";
import { StatusStrip, type Provenance } from "./components/StatusStrip";
import { EXAMPLE_DEMO_POLICY, PolicyActionPanel } from "./components/PolicyActionPanel";
import { RegistryPanel } from "./components/RegistryPanel";
import { ValidationOverview } from "./views/ValidationOverview";
import { ReferenceComparison } from "./views/ReferenceComparison";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ModelEvidence } from "./views/ModelEvidence";
import { OperationalTimeline } from "./views/OperationalTimeline";
import { deriveOnchainSync } from "./lib/onchain";

type Mode = "operational" | "historical" | "demo";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const [mode, setMode] = useState<Mode>("operational");

  return (
    <div className="mx-auto min-h-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Valtide</h1>
          <p className="mt-0.5 text-sm" style={{ color: "var(--color-ink-dim)" }}>
            Can this tokenized-equity collateral reference be independently supported?
          </p>
        </div>
        <ModeToggle mode={mode} onChange={setMode} backendUp={!!health.data} />
      </header>

      {mode === "operational" ? <OperationalView /> : mode === "historical" ? <HistoricalView /> : <DemoView backendUp={!!health.data} />}
    </div>
  );
}

function ModeToggle({ mode, onChange, backendUp }: { mode: Mode; onChange: (m: Mode) => void; backendUp: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} title={backendUp ? "Backend reachable" : "Backend unavailable; Operational mode remains selected"}>
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} />
        {backendUp ? "backend online" : "backend unavailable"}
      </span>
      <div className="inline-flex overflow-hidden rounded-lg" style={{ border: "1px solid var(--color-line)" }}>
        {(["operational", "historical", "demo"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => onChange(m)}
            className="px-3 py-1.5 text-sm font-medium capitalize"
            style={mode === m ? { background: "var(--color-accent)", color: "#fff" } : { background: "#fff", color: "var(--color-ink-dim)" }}
          >
            {m === "operational" ? "Operational" : m === "historical" ? "Historical" : "Demo"}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Operational mode never substitutes a diagnostic or scenario for its warmed state. */
function OperationalView() {
  const operational = useQuery({ queryKey: ["valuation", "operational", "NVDAx"], queryFn: fetchOperationalValuation, refetchInterval: 20_000, retry: 0 });
  const runtime = useQuery({ queryKey: ["runtime", "NVDAx"], queryFn: fetchRuntime, refetchInterval: 20_000, retry: 0 });
  const history = useQuery({ queryKey: ["history", "NVDAx", 72], queryFn: () => fetchOperationalHistory(72), refetchInterval: 30_000, retry: 0 });
  const controlPlane = useControlPlaneQueries();
  const [diagnosticRequested, setDiagnosticRequested] = useState(false);
  const [selectedTimestamp, setSelectedTimestamp] = useState<string | null>(null);
  const diagnostic = useQuery({ queryKey: ["valuation", "diagnostic", "NVDAx"], queryFn: fetchLiveDiagnostic, retry: 0, enabled: diagnosticRequested });

  if (operational.isLoading) return <Message>Loading the warmed operational state…</Message>;

  if (operational.isError || !operational.data) {
    return (
      <div className="space-y-6">
        <Message>
          <div className="font-medium text-ink">Operational runtime unavailable</div>
          <p className="mx-auto mt-1 max-w-xl text-sm">
            The warmed operational endpoint has no persisted result to show. Valtide stays in Operational mode and will not substitute a cold-start diagnostic or synthetic scenario.
          </p>
          {runtime.data?.last_error && <p className="mx-auto mt-2 max-w-xl text-xs" style={{ color: "var(--color-inconclusive)" }}>Scheduler: {runtime.data.last_error}</p>}
        </Message>
        <DiagnosticCard requested={diagnosticRequested} onRun={() => setDiagnosticRequested(true)} query={diagnostic} />
        <RegistryPanel {...controlPlane} runtime={runtime.data} mode="operational" />
      </div>
    );
  }

  const latest = operational.data;
  const selected = history.data?.find((result) => result.timestamp === selectedTimestamp) ?? latest;
  const selectedIsLatest = selected.timestamp === latest.timestamp;
  const sync = deriveOnchainSync(latest, controlPlane.controlPlane);

  return (
    <div className="space-y-6">
      <StatusStrip r={latest} provenance="cached" runtime={runtime.data} onchainFresh={controlPlane.controlPlane?.fresh} />
      {!selectedIsLatest && <SelectionNotice label="Selected operational observation" onLatest={() => setSelectedTimestamp(null)} />}
      <ValidationOverview r={selected} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ReferenceComparison r={selected} /></div>
        <PolicyActionPanel
          current={selected.evidence_state}
          policy={controlPlane.controlPlane?.policy}
          evaluation={controlPlane.controlPlane}
          sync={sync}
          policySource={controlPlane.controlPlane ? "X Layer RiskGuard" : "Unavailable — no frontend default"}
          observationKind="operational"
          observationLabel={selectedIsLatest ? "Current operational evidence" : "Selected operational evidence"}
        />
      </div>
      <OperationalTimeline
        results={history.data ?? []}
        selectedTimestamp={selected.timestamp}
        onSelect={setSelectedTimestamp}
        isLoading={history.isLoading}
        isError={history.isError}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ModelEvidence /></div>
        <RegistryPanel {...controlPlane} runtime={runtime.data} sync={sync} mode="operational" />
      </div>
      <DiagnosticCard requested={diagnosticRequested} onRun={() => setDiagnosticRequested(true)} query={diagnostic} />
      <Footer r={latest} label="warmed operational result" />
    </div>
  );
}

function HistoricalView() {
  const replay = useQuery({ queryKey: ["replay", "historical", "NVDAx"], queryFn: fetchHistoricalReplay, staleTime: 10 * 60_000, retry: 0 });
  const controlPlane = useControlPlaneQueries();
  const [index, setIndex] = useState(0);

  if (replay.isLoading) return <Message>Loading the historical panel…</Message>;
  if (replay.isError || !replay.data?.results.length) {
    return <Message><div className="font-medium text-ink">Historical investigation unavailable</div><p className="mx-auto mt-1 max-w-xl text-sm">The provisioned historical panel could not be loaded. Demo data is intentionally not used as a historical fallback.</p></Message>;
  }

  const results = replay.data.results;
  const selected = results[Math.min(index, results.length - 1)];
  const policy = controlPlane.controlPlane?.policy;

  return (
    <div className="space-y-6">
      <div className="rounded-xl px-4 py-3 text-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>
        Historical investigation uses the real point-in-time panel. The X Layer panel below is current deployed state, not historical chain state.
      </div>
      <ValidationOverview r={selected} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ReferenceComparison r={selected} /></div>
        <PolicyActionPanel
          current={selected.evidence_state}
          policy={policy}
          policySource={policy ? "Current X Layer curator policy" : "Unavailable — no frontend default"}
          observationKind="historical"
          observationLabel="Selected historical evidence"
        />
      </div>
      <HistoricalReplay
        results={results}
        index={index}
        setIndex={setIndex}
        playing={false}
        setPlaying={() => undefined}
        title="Historical panel investigation"
        subtitle="Point-in-time replay from the provisioned historical panel. This is research evidence, not current operational history or historical onchain state."
        showPlayback={false}
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ModelEvidence /></div>
        <RegistryPanel {...controlPlane} mode="historical" />
      </div>
      <Footer r={selected} label="historical panel investigation" />
    </div>
  );
}

/** Demo mode: scenario replay only; it is entered explicitly by the user. */
function DemoView({ backendUp }: { backendUp: boolean }) {
  const { data, isLoading } = useQuery({ queryKey: ["demo-replay"], queryFn: () => fetchDemoReplay(), staleTime: Infinity });
  const controlPlane = useControlPlaneQueries(backendUp);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  if (isLoading || !data) return <Message>Loading demo scenario…</Message>;

  const r = data.results[Math.min(index, data.results.length - 1)];
  const provenance: Provenance = data.source === "backend-scenario" ? "demo-scenario" : "demo-fixture";
  const policy = controlPlane.controlPlane?.policy ?? EXAMPLE_DEMO_POLICY;
  const policySource = controlPlane.controlPlane ? "Current X Layer curator policy" : "Example demo policy (not deployed state)";

  return (
    <div className="space-y-6">
      <StatusStrip r={r} provenance={provenance} />
      <ValidationOverview r={r} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><ReferenceComparison r={r} /></div>
        <PolicyActionPanel current={r.evidence_state} policy={policy} policySource={policySource} scenarioMode observationKind="scenario" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><HistoricalReplay results={data.results} index={index} setIndex={setIndex} playing={playing} setPlaying={setPlaying} /></div>
        <RegistryPanel {...controlPlane} mode="demo" />
      </div>
      <ModelEvidence />
      <Footer r={r} label="deterministic scenario replay" />
    </div>
  );
}

function Footer({ r, label }: { r: ValuationResult; label: string }) {
  return <footer className="pt-2 text-center text-xs" style={{ color: "var(--color-muted)" }}>Model {r.model_id} {r.model_version} · reference {r.reference_under_test_source} · {label} · hackathon research prototype, not a production oracle</footer>;
}

function SelectionNotice({ label, onLatest }: { label: string; onLatest: () => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}><span>{label} — the operational status strip and onchain control plane remain current.</span><button onClick={onLatest} className="rounded-md px-2.5 py-1 text-xs font-semibold text-white" style={{ background: "var(--color-accent)" }}>Back to latest</button></div>;
}

function DiagnosticCard({ requested, onRun, query }: { requested: boolean; onRun: () => void; query: { isFetching: boolean; isError: boolean; error: unknown; data?: ValuationResult } }) {
  return <section className="card-shadow rounded-2xl bg-white p-6" style={{ border: "1px solid var(--color-line)" }}><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-base font-semibold text-ink">Cold-start live diagnostic</h2><p className="mt-0.5 max-w-2xl text-sm" style={{ color: "var(--color-ink-dim)" }}>One-off, read-only inference from live market inputs. It does not warm the runtime or publish an attestation.</p></div><button onClick={onRun} disabled={query.isFetching} className="rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" style={{ background: "var(--color-accent)" }}>{query.isFetching ? "Running…" : requested ? "Run again" : "Run live diagnostic"}</button></div>{query.isError && <p className="mt-3 text-sm" style={{ color: "var(--color-inconclusive)" }}>{query.error instanceof ApiError ? query.error.detail : "Diagnostic unavailable."}</p>}{query.data && <div className="mt-4 space-y-4 border-t pt-4" style={{ borderColor: "var(--color-line)" }}><StatusStrip r={query.data} provenance="diagnostic" /><ValidationOverview r={query.data} /></div>}</section>;
}

function useControlPlaneQueries(enabled = true) {
  const onchain = useQuery({ queryKey: ["onchain", "NVDAx"], queryFn: fetchOnchain, refetchInterval: 45_000, retry: 0, enabled });
  const enforcement = useQuery({ queryKey: ["onchain", "NVDAx", "enforcement"], queryFn: fetchOnchainEnforcement, refetchInterval: 45_000, retry: 0, enabled });
  return { controlPlane: onchain.data, enforcement: enforcement.data, isLoading: enabled && (onchain.isLoading || enforcement.isLoading), isError: onchain.isError || enforcement.isError, errorDetail: onchain.error instanceof ApiError ? onchain.error.detail : enforcement.error instanceof ApiError ? enforcement.error.detail : undefined };
}

function Message({ children }: { children: ReactNode }) {
  return <div className="card-shadow rounded-2xl bg-white p-10 text-center" style={{ border: "1px solid var(--color-line)", color: "var(--color-ink-dim)" }}>{children}</div>;
}
