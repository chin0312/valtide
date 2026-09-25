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
import { EXAMPLE_DEMO_POLICY, PolicyActionPanel } from "./components/PolicyActionPanel";
import { RegistryPanel } from "./components/RegistryPanel";
import { StatusStrip, type Provenance } from "./components/StatusStrip";
import { deriveOnchainSync } from "./lib/onchain";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ModelEvidence } from "./views/ModelEvidence";
import { filterOperationalResults, OPERATIONAL_HISTORY_LIMITS, OperationalTimeline, type OperationalRange } from "./views/OperationalTimeline";
import { ReferenceComparison } from "./views/ReferenceComparison";
import { ValidationOverview } from "./views/ValidationOverview";

type Mode = "operational" | "historical" | "demo";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const [mode, setMode] = useState<Mode>("operational");

  return (
    <div className="mx-auto min-h-full max-w-[1480px] px-4 py-5 sm:px-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        <div className="flex items-center gap-5">
          <div>
            <div className="eyebrow" style={{ color: "var(--color-accent)" }}>Independent valuation control</div>
            <h1 className="mt-1 text-2xl font-semibold tracking-[-0.04em] text-ink">Valtide</h1>
          </div>
          <div className="hidden h-8 w-px sm:block" style={{ background: "var(--color-line)" }} />
          <div className="hidden sm:block">
            <div className="text-[13px] font-medium text-ink">NVDAx evidence monitor</div>
            <div className="tnum text-[10px] uppercase tracking-[0.06em]" style={{ color: "var(--color-muted)" }}>X Layer · chain 1952 · browser read-only</div>
          </div>
        </div>
        <ModeToggle mode={mode} onChange={setMode} backendUp={!!health.data} />
      </header>

      {mode === "operational" ? <OperationalView /> : mode === "historical" ? <HistoricalView /> : <DemoView backendUp={!!health.data} />}
    </div>
  );
}

function ModeToggle({ mode, onChange, backendUp }: { mode: Mode; onChange: (mode: Mode) => void; backendUp: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.05em]" style={{ color: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} title={backendUp ? "Backend reachable" : "Backend unavailable; the selected lane is not substituted"}>
        <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: backendUp ? "var(--color-supported)" : "var(--color-muted)" }} />
        {backendUp ? "backend online" : "backend unavailable"}
      </span>
      <div className="inline-flex overflow-hidden rounded-lg p-1" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
        {(["operational", "historical", "demo"] as Mode[]).map((option) => (
          <button key={option} onClick={() => onChange(option)} className="rounded px-3 py-1.5 text-xs font-medium capitalize" style={mode === option ? { background: "var(--color-accent-soft)", color: "var(--color-accent)" } : { color: "var(--color-muted)" }}>
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

function OperationalView() {
  const operational = useQuery({ queryKey: ["valuation", "operational", "NVDAx"], queryFn: fetchOperationalValuation, refetchInterval: 20_000, retry: 0 });
  const runtime = useQuery({ queryKey: ["runtime", "NVDAx"], queryFn: fetchRuntime, refetchInterval: 20_000, retry: 0 });
  const [historyRange, setHistoryRange] = useState<OperationalRange>("24H");
  const historyLimit = OPERATIONAL_HISTORY_LIMITS[historyRange];
  const history = useQuery({ queryKey: ["history", "NVDAx", historyLimit], queryFn: () => fetchOperationalHistory(historyLimit), refetchInterval: 30_000, retry: 0 });
  const controlPlane = useControlPlaneQueries();
  const [diagnosticRequested, setDiagnosticRequested] = useState(false);
  const [selectedTimestamp, setSelectedTimestamp] = useState<string | null>(null);
  const diagnostic = useQuery({ queryKey: ["valuation", "diagnostic", "NVDAx"], queryFn: fetchLiveDiagnostic, retry: 0, enabled: diagnosticRequested });

  if (operational.isLoading) return <Message>Loading the warmed operational state…</Message>;
  if (operational.isError || !operational.data) {
    return (
      <div className="space-y-4">
        <Message><div className="font-medium text-ink">Operational runtime unavailable</div><p className="mx-auto mt-1 max-w-xl text-xs">No persisted warmed result is available. Operational mode remains selected; Valtide will not substitute a diagnostic or synthetic scenario.</p>{runtime.data?.last_error && <p className="mx-auto mt-2 max-w-xl text-xs" style={{ color: "var(--color-inconclusive)" }}>Scheduler: {runtime.data.last_error}</p>}</Message>
        <DiagnosticDisclosure requested={diagnosticRequested} onRun={() => setDiagnosticRequested(true)} query={diagnostic} />
        <RegistryPanel {...controlPlane} runtime={runtime.data} mode="operational" />
      </div>
    );
  }

  const latest = operational.data;
  const displayHistory = filterOperationalResults(history.data ?? [], historyRange);
  const selected = displayHistory.find((result) => result.timestamp === selectedTimestamp) ?? latest;
  const selectedIsLatest = selected.timestamp === latest.timestamp;
  const sync = deriveOnchainSync(latest, controlPlane.controlPlane);

  return (
    <div className="space-y-4">
      <StatusStrip r={latest} provenance="cached" runtime={runtime.data} onchainFresh={controlPlane.controlPlane?.fresh} />
      {!selectedIsLatest && <SelectionNotice onLatest={() => setSelectedTimestamp(null)} />}
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <ValidationOverview r={selected} />
        <PolicyActionPanel current={selected.evidence_state} policy={controlPlane.controlPlane?.policy} evaluation={selectedIsLatest ? controlPlane.controlPlane : undefined} sync={selectedIsLatest ? sync : undefined} policySource={controlPlane.controlPlane ? "X Layer RiskGuard" : "Unavailable — no frontend default"} observationKind={selectedIsLatest ? "current-operational" : "prior-operational"} observationLabel={selectedIsLatest ? "Current operational evidence" : "Selected operational evidence"} />
      </div>
      <OperationalTimeline results={history.data ?? []} selectedTimestamp={selected.timestamp} onSelect={setSelectedTimestamp} range={historyRange} onRangeChange={(nextRange) => { setHistoryRange(nextRange); setSelectedTimestamp(null); }} onLatest={() => setSelectedTimestamp(null)} isLoading={history.isLoading} isError={history.isError} />
      <ReferenceComparison r={selected} />
      <ModelEvidence />
      <RegistryPanel {...controlPlane} runtime={runtime.data} sync={sync} mode="operational" />
      <DiagnosticDisclosure requested={diagnosticRequested} onRun={() => setDiagnosticRequested(true)} query={diagnostic} />
      <Footer r={latest} label="warmed operational result" />
    </div>
  );
}

function HistoricalView() {
  const replay = useQuery({ queryKey: ["replay", "historical", "NVDAx"], queryFn: fetchHistoricalReplay, staleTime: 10 * 60_000, retry: 0 });
  const controlPlane = useControlPlaneQueries();
  const [index, setIndex] = useState<number | null>(null);

  if (replay.isLoading) return <Message>Loading the historical panel…</Message>;
  if (replay.isError || !replay.data?.results.length) return <Message><div className="font-medium text-ink">Historical investigation unavailable</div><p className="mx-auto mt-1 max-w-xl text-xs">The provisioned historical panel could not be loaded. Demo data is not used as a historical fallback.</p></Message>;

  const results = replay.data.results;
  const selectedIndex = index ?? results.length - 1;
  const selected = results[Math.min(selectedIndex, results.length - 1)];
  const policy = controlPlane.controlPlane?.policy;

  return (
    <div className="space-y-4">
      <LaneNotice>Historical evidence is point-in-time research data. The X Layer provenance below remains current deployed state.</LaneNotice>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <ValidationOverview r={selected} />
        <PolicyActionPanel current={selected.evidence_state} policy={policy} policySource={policy ? "Current X Layer curator policy" : "Unavailable — no frontend default"} observationKind="historical-panel" observationLabel="Selected historical evidence" />
      </div>
      <HistoricalReplay results={results} index={selectedIndex} setIndex={(nextIndex) => setIndex(nextIndex)} playing={false} setPlaying={() => undefined} title="Historical panel investigation" subtitle="Real point-in-time panel data; not operational history or historical onchain state." showPlayback={false} fullTimestamps showLatest onLatest={() => setIndex(results.length - 1)} />
      <ReferenceComparison r={selected} />
      <ModelEvidence />
      <RegistryPanel {...controlPlane} mode="historical" />
      <Footer r={selected} label="historical panel investigation" />
    </div>
  );
}

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
    <div className="space-y-4">
      <StatusStrip r={r} provenance={provenance} />
      <LaneNotice>This is a deterministic 25-minute scenario. It does not publish, control X Layer, or claim historical performance.</LaneNotice>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <ValidationOverview r={r} />
        <PolicyActionPanel current={r.evidence_state} policy={policy} policySource={policySource} observationKind="scenario" />
      </div>
      <HistoricalReplay results={data.results} index={index} setIndex={setIndex} playing={playing} setPlaying={setPlaying} />
      <ReferenceComparison r={r} />
      <ModelEvidence />
      <RegistryPanel {...controlPlane} mode="demo" />
      <Footer r={r} label="deterministic 25-minute scenario" />
    </div>
  );
}

function DiagnosticDisclosure({ requested, onRun, query }: { requested: boolean; onRun: () => void; query: { isFetching: boolean; isError: boolean; error: unknown; data?: ValuationResult } }) {
  return (
    <details className="rounded-lg" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <summary className="flex items-center justify-between px-4 py-3 text-xs" style={{ color: "var(--color-ink-dim)" }}><span>Cold-start live diagnostic · read-only, does not warm or publish</span><span aria-hidden style={{ color: "var(--color-accent)" }}>＋</span></summary>
      <div className="border-t p-4" style={{ borderColor: "var(--color-line-subtle)" }}>
        <button onClick={onRun} disabled={query.isFetching} className="rounded px-4 py-2 text-xs font-medium disabled:opacity-50" style={{ background: "var(--color-accent-soft)", color: "var(--color-accent)", border: "1px solid var(--color-accent)" }}>{query.isFetching ? "Running…" : requested ? "Run again" : "Run live diagnostic"}</button>
        {query.isError && <p className="mt-3 text-xs" style={{ color: "var(--color-inconclusive)" }}>{query.error instanceof ApiError ? query.error.detail : "Diagnostic unavailable."}</p>}
        {query.data && <div className="mt-4"><ValidationOverview r={query.data} /></div>}
      </div>
    </details>
  );
}

function useControlPlaneQueries(enabled = true) {
  const onchain = useQuery({ queryKey: ["onchain", "NVDAx"], queryFn: fetchOnchain, refetchInterval: 45_000, retry: 0, enabled });
  const enforcement = useQuery({ queryKey: ["onchain", "NVDAx", "enforcement"], queryFn: fetchOnchainEnforcement, refetchInterval: 45_000, retry: 0, enabled });
  return { controlPlane: onchain.data, enforcement: enforcement.data, isLoading: enabled && (onchain.isLoading || enforcement.isLoading), isError: onchain.isError || enforcement.isError, errorDetail: onchain.error instanceof ApiError ? onchain.error.detail : enforcement.error instanceof ApiError ? enforcement.error.detail : undefined };
}

function SelectionNotice({ onLatest }: { onLatest: () => void }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2 text-xs" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)", borderLeft: "2px solid var(--color-accent)", color: "var(--color-ink-dim)" }}><span>Inspecting a prior operational observation. Status and X Layer provenance remain current.</span><button onClick={onLatest} className="rounded px-2.5 py-1 font-medium" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)" }}>Back to latest</button></div>;
}

function LaneNotice({ children }: { children: ReactNode }) {
  return <div className="rounded-lg px-4 py-2.5 text-xs" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", borderLeft: "2px solid var(--color-accent)", color: "var(--color-ink-dim)" }}>{children}</div>;
}

function Message({ children }: { children: ReactNode }) {
  return <div className="rounded-[10px] p-10 text-center" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", color: "var(--color-ink-dim)" }}>{children}</div>;
}

function Footer({ r, label }: { r: ValuationResult; label: string }) {
  return <footer className="border-t pt-4 font-mono text-[10px] uppercase tracking-[0.05em]" style={{ borderColor: "var(--color-line-subtle)", color: "var(--color-muted)" }}>Model {r.model_id} {r.model_version} · reference {r.reference_under_test_source} · {label} · research prototype, not a production oracle</footer>;
}
