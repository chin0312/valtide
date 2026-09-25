import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  fetchAssets,
  fetchDemoReplay,
  fetchHealth,
  fetchHistoricalReplay,
  fetchOnchain,
  fetchOnchainEnforcement,
  fetchOperationalHistory,
  fetchOperationalValuation,
  fetchRuntime,
} from "./api/client";
import type { AssetInfo, EvidenceState, OnchainControlPlane, OnchainPolicy, PolicyAction, ValuationResult } from "./api/types";
import { EXAMPLE_DEMO_POLICY } from "./components/PolicyActionPanel";
import { ReasonCodes } from "./components/ReasonCodes";
import { RegistryPanel } from "./components/RegistryPanel";
import { Panel } from "./components/ui";
import { Icon } from "./components/Icon";
import { EVIDENCE } from "./lib/evidence";
import { ageLabel, compactUsd, money, pct, sigma, sourceLabel } from "./lib/format";
import { deriveOnchainSync } from "./lib/onchain";
import { clampPosition, mergeObservations, rebasePosition } from "./lib/playback";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ObservationRecord } from "./views/ObservationRecord";
import { ReferenceComparison } from "./views/ReferenceComparison";
import { ModelEvidence } from "./views/ModelEvidence";
import { filterDemoResults, filterHistoricalResults, filterOperationalResults, OPERATIONAL_HISTORY_LIMITS, type DemoRange, type HistoricalRange, type OperationalRange } from "./views/OperationalTimeline";
import { ObservationAudit } from "./components/ObservationAudit";

type Context = "Operational" | "Historical" | "Demo";
const EMPTY_RESULTS: ValuationResult[] = [];

export default function App() {
  const [context, setContext] = useState<Context>("Operational");
  const [range, setRange] = useState<OperationalRange>("24H");
  const [historicalRange, setHistoricalRange] = useState<HistoricalRange>("ALL");
  const [demoRange, setDemoRange] = useState<DemoRange>("FULL");
  const isOperational = context === "Operational";
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const backendUp = health.data === true;
  const assets = useQuery({ queryKey: ["assets"], queryFn: fetchAssets, retry: 0, enabled: backendUp, staleTime: 60_000 });
  const operational = useQuery({ queryKey: ["valuation", "operational", "NVDAx"], queryFn: fetchOperationalValuation, refetchInterval: 20_000, retry: 0 });
  const historyLimit = OPERATIONAL_HISTORY_LIMITS[range];
  const history = useQuery({ queryKey: ["history", "NVDAx", historyLimit], queryFn: () => fetchOperationalHistory(historyLimit), refetchInterval: 30_000, retry: 0, enabled: isOperational && !!operational.data });
  const historical = useQuery({ queryKey: ["replay", "historical-panel"], queryFn: fetchHistoricalReplay, staleTime: 60_000, retry: 0, enabled: context === "Historical" });
  const demo = useQuery({ queryKey: ["demo-replay", "canonical"], queryFn: () => fetchDemoReplay(), staleTime: Infinity, enabled: context === "Demo" });
  const runtime = useQuery({ queryKey: ["runtime", "NVDAx"], queryFn: fetchRuntime, refetchInterval: 30_000, retry: 0, enabled: backendUp });
  const onchain = useQuery({ queryKey: ["onchain", "NVDAx"], queryFn: fetchOnchain, refetchInterval: 45_000, retry: 0, enabled: backendUp });
  const enforcement = useQuery({ queryKey: ["onchain", "NVDAx", "enforcement"], queryFn: fetchOnchainEnforcement, refetchInterval: 45_000, retry: 0, enabled: backendUp });
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [followLatest, setFollowLatest] = useState(true);

  const operationalResults = useMemo(() => {
    if (!operational.data) return [];
    return filterOperationalResults(mergeObservations(history.data ?? [], operational.data), range);
  }, [history.data, operational.data, range]);
  const historicalResults = useMemo(() => filterHistoricalResults(historical.data?.results ?? EMPTY_RESULTS, historicalRange), [historical.data, historicalRange]);
  const demoResults = useMemo(() => filterDemoResults(demo.data?.results ?? EMPTY_RESULTS, demoRange), [demo.data, demoRange]);
  const results = isOperational ? operationalResults : context === "Historical" ? historicalResults : demoResults;
  const activeRange = context === "Operational" ? range : context === "Historical" ? historicalRange : demoRange;
  const previous = useRef({ results, context, activeRange });

  useEffect(() => {
    const before = previous.current;
    previous.current = { results, context, activeRange };
    if (before.context !== context || before.activeRange !== activeRange || (!before.results.length && results.length)) {
      setPosition(context === "Demo" ? 0 : Math.max(0, results.length - 1));
      setFollowLatest(isOperational);
      setPlaying(false);
    } else if (isOperational && followLatest) {
      setPosition(results.length - 1);
    } else {
      setPosition((value) => rebasePosition(value, before.results, results));
    }
  }, [context, activeRange, isOperational, results, followLatest]);

  const safePosition = clampPosition(position, results.length);
  const currentIndex = Math.floor(safePosition);
  const current = results[currentIndex];
  const reviewing = isOperational && !!current && !!operational.data && Date.parse(current.timestamp) < Date.parse(operational.data.timestamp);
  const source = isOperational
    ? `Operational · ${results.length} Observations`
    : context === "Historical" ? `Historical Panel · ${results.length} Observations`
    : !demo.data ? "Demo · Loading" : demo.data.source === "backend-scenario"
      ? `Demo Scenario · ${demo.data.results.length} Observations`
      : `Demo Fixture · ${demo.data.results.length} Observations`;
  const controlPlane = onchain.isError ? undefined : onchain.data;
  const policy = controlPlane?.policy ?? (context === "Demo" ? EXAMPLE_DEMO_POLICY : undefined);
  const policyAction = policy && current ? actionFor(policy, current.evidence_state) : null;
  const sync = isOperational ? deriveOnchainSync(operational.data, controlPlane) : undefined;
  const activeQuery = isOperational ? operational : context === "Historical" ? historical : demo;
  const isDegraded = activeQuery.isError || (isOperational && (history.isError || runtime.data?.last_tick_status === "failure"));
  const statusMessage = activeQuery.error instanceof Error ? activeQuery.error.message : "Data unavailable";
  const runtimeNotWarmed = isOperational && (runtime.data?.has_live_result === false || (operational.error instanceof ApiError && operational.error.status === 503));
  const chainError = backendUp
    ? onchain.error instanceof Error ? onchain.error.message : "The deployed contracts could not be read."
    : "Backend unavailable. Showing the last available data.";

  return (
    <div className="mx-auto min-h-full max-w-[1480px] px-4 py-4 sm:px-6">
      <AppHeader backendUp={backendUp} chainUp={!!controlPlane} source={source} assets={assets.data} context={context} onContextChange={setContext} />

      <main className="space-y-4">
        {isDegraded && current && <div role="status" className="rounded px-4 py-3 text-xs text-ink-dim" style={{ background: "var(--color-inconclusive-soft)" }}>{context} degraded · showing last available observations. {history.isError && isOperational ? "History unavailable. " : ""}{activeQuery.isError ? statusMessage : runtime.data?.last_error}</div>}
        {!current ? <Panel title={`${context} ${activeQuery.isLoading ? "loading" : "unavailable"}`}><p role="status" className="text-xs text-ink-dim">{activeQuery.isLoading ? `Loading ${context.toLowerCase()} observations…` : runtimeNotWarmed ? "Runtime not warmed yet." : statusMessage}</p></Panel> : <>
        <MetricGrid current={current} isDemo={context === "Demo"} />

        <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <HistoricalReplay
            results={results}
            position={position}
            setPosition={setPosition}
            playing={playing}
            setPlaying={setPlaying}
            sourceLabel={source}
            onReview={() => setFollowLatest(false)}
            followingLatest={isOperational && followLatest}
            onLatest={isOperational ? () => { setPlaying(false); setFollowLatest(true); setPosition(results.length - 1); } : undefined}
            viewportKey={`${context}:${activeRange}`}
            periodMs={context === "Demo" ? 600 : 120}
            rangeControl={<RangeControls context={context} range={activeRange} onChange={(value) => { if (context === "Operational") setRange(value as OperationalRange); else if (context === "Historical") setHistoricalRange(value as HistoricalRange); else setDemoRange(value as DemoRange); }} />}
          />
          <div className="flex min-w-0 flex-col gap-4">
            <ReferenceComparison r={current} />
            <PolicyCard
              state={current.evidence_state}
              action={policyAction}
              label={context === "Demo" ? controlPlane ? "Scenario · deployed policy mapping" : "Example demo policy · not deployed" : context === "Historical" ? "Historical · current policy mapping" : reviewing ? "Prior observation · current policy mapping" : "Current evidence · policy mapping"}
              source={context === "Demo" ? "Scenario projection only; does not represent deployed state" : context === "Historical" || reviewing ? "Selected evidence under today's policy; not a historical on-chain decision" : "Curator mapping for this evidence; current RiskGuard action is shown separately"}
              enforced={isOperational && !reviewing ? controlPlane : undefined}
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <EvidenceCard result={current} />
          <BasisCard result={current} />
        </div>

        <ObservationRecord results={results} currentIndex={currentIndex} sourceLabelText={source} />
        </>}
        <ObservationAudit result={current} context={context} runtime={runtime.isError ? undefined : runtime.data} controlPlane={controlPlane} />

        {context === "Historical" && <ModelEvidence />}

        <RegistryPanel
          controlPlane={controlPlane}
          enforcement={enforcement.isError ? undefined : enforcement.data}
          runtime={runtime.isError ? undefined : runtime.data}
          sync={sync}
          mode={context === "Demo" ? "demo" : context === "Historical" || reviewing ? "historical" : "operational"}
          isLoading={backendUp && onchain.isLoading}
          isError={!controlPlane}
          errorDetail={chainError}
        />

        <footer className="border-t pt-3 font-mono text-[10px] tracking-[0.05em]" style={{ borderColor: "var(--color-line-subtle)", color: "var(--color-muted)" }}>
          {current ? `${current.model_id} ${current.model_version} · ` : ""}Independent Validation Control
        </footer>
      </main>
    </div>
  );
}

function AppHeader({ backendUp, chainUp, source, assets, context, onContextChange }: { backendUp: boolean; chainUp: boolean; source: string; assets?: AssetInfo[]; context: Context; onContextChange: (context: Context) => void }) {
  return (
    <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
      <div className="flex flex-wrap items-center gap-3 sm:gap-6">
        <h1 className="text-[22px] font-semibold tracking-[-0.04em] text-ink">Valtide</h1>
        <nav aria-label="Evidence context" className="flex gap-1 rounded p-1" style={{ border: "1px solid var(--color-line)" }}>{(["Operational", "Historical", "Demo"] as Context[]).map((option) => <button key={option} aria-pressed={context === option} onClick={() => onContextChange(option)} className="rounded px-2.5 py-1.5 text-xs font-medium" style={{ background: context === option ? "var(--color-panel-2)" : undefined, color: context === option ? "var(--color-ink)" : "var(--color-muted)" }}>{option}</button>)}</nav>
        <AssetSelector assets={assets} />
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px]">
        <span className="rounded px-2 py-1 font-mono" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)" }}>{source}</span>
        <ConnectionLabel active={backendUp} activeText="API Connected" inactiveText="API Unavailable" />
        <ConnectionLabel active={chainUp} activeText="X Layer Read" inactiveText="On-Chain Unread" />
      </div>
    </header>
  );
}

function RangeControls({ context, range, onChange }: { context: Context; range: string; onChange: (range: string) => void }) {
  const options = context === "Operational" ? Object.keys(OPERATIONAL_HISTORY_LIMITS) : context === "Historical" ? ["1H", "6H", "24H", "3D", "7D", "ALL"] : ["5M", "10M", "15M", "FULL"];
  return <div className="flex gap-1" aria-label={`${context} history range`}>{options.map((option) => <button key={option} type="button" aria-pressed={range === option} onClick={() => onChange(option)} className="rounded px-2.5 py-1 font-mono text-[10px] font-medium" style={{ color: range === option ? "var(--color-accent)" : "var(--color-muted)", background: range === option ? "var(--color-accent-soft)" : undefined }}>{option}</button>)}</div>;
}

export function AssetSelector({ assets, initialOpen = false }: { assets?: AssetInfo[]; initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen);
  const [search, setSearch] = useState("");
  const available = new Set((assets ?? []).map((asset) => asset.asset));
  const catalog = [
    { asset: "NVDAx", name: "NVIDIA Tokenized Equity", status: available.has("NVDAx") ? "Available" : "Current Asset" },
    { asset: "SPYx", name: "S&P 500 Tokenized ETF", status: "Coming Soon" },
  ];
  const filtered = catalog.filter((entry) => `${entry.asset} ${entry.name}`.toLowerCase().includes(search.toLowerCase()));

  return <div className="relative">
    <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-haspopup="listbox" className="rounded px-3 py-1.5 text-left" title="Select collateral asset" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}><span className="tnum text-xs font-medium text-ink">NVDAx</span><span className="ml-2 text-[10px]" style={{ color: "var(--color-muted)" }}>⌄</span></button>
    {open && <div className="absolute left-0 top-full z-30 mt-2 w-64 rounded-lg p-2" role="listbox" aria-label="Asset Selector" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
      <input autoFocus value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search Assets…" aria-label="Search Assets" className="mb-2 w-full rounded px-2 py-1.5 text-xs text-ink outline-none" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }} />
      {filtered.map((entry) => <button key={entry.asset} type="button" disabled={entry.asset === "SPYx"} className="flex w-full items-center justify-between rounded px-2 py-2 text-left disabled:cursor-not-allowed disabled:opacity-50" aria-label={`${entry.asset} ${entry.status}`} style={entry.asset === "NVDAx" ? { background: "var(--color-panel-2)" } : undefined}><span><span className="tnum block text-xs text-ink">{entry.asset}</span><span className="block text-[10px] text-muted">{entry.name}</span></span><span className="text-[10px] text-muted">{entry.status}</span></button>)}
    </div>}
  </div>;
}

function ConnectionLabel({ active, activeText, inactiveText }: { active: boolean; activeText: string; inactiveText: string }) {
  return <span className="inline-flex items-center gap-1.5" style={{ color: active ? "var(--color-supported)" : "var(--color-muted)" }}><i className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />{active ? activeText : inactiveText}</span>;
}

function MetricGrid({ current, isDemo }: { current: ValuationResult; isDemo: boolean }) {
  return (
    <section className="grid grid-cols-2 overflow-hidden rounded-[10px] md:grid-cols-3 xl:grid-cols-6" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <Metric label="Reference Under Test" value={money(current.reference_under_test)} sub="Under Test" />
      <Metric label="Valtide Fair Value" value={money(current.valtide_fair_value)} sub={`${money(current.fair_value_lower)}–${money(current.fair_value_upper)}`} />
      <Metric label="Token Market" value={money(current.token_price)} sub={current.token_source ? sourceLabel(current.token_source) : isDemo ? "Demo Scenario" : "Source Unavailable"} />
      <Metric label="Deviation" value={pct(current.reference_deviation_pct)} sub={current.evidence_state} accent={EVIDENCE[current.evidence_state].fg} />
      <Metric label="Standardized" value={sigma(current.standardized_deviation)} sub="From Fair Value" />
      <Metric label="Last Trusted" value={money(current.last_trusted_reference)} sub={`${ageLabel(current.reference_age_seconds)} Old`} />
    </section>
  );
}

function Metric({ label, value, sub, accent }: { label: string; value: string; sub: string; accent?: string }) {
  return <div className="min-w-0 px-4 py-3.5" style={{ borderRight: "1px solid var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-2 truncate text-xl font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>{value}</div><div className="tnum mt-1 truncate text-[10px]" style={{ color: "var(--color-muted)" }}>{sub}</div></div>;
}

function EvidenceCard({ result }: { result: ValuationResult }) {
  const state = EVIDENCE[result.evidence_state];
  return (
    <Panel title="Evidence" icon="evidence">
      <div className="text-2xl font-semibold tracking-[-0.03em]" style={{ color: state.fg }}>{state.label}</div>
      <div className="mt-4"><ReasonCodes codes={result.reason_codes} evidenceState={result.evidence_state} /></div>
    </Panel>
  );
}

function PolicyCard({ state, action, source, label, enforced }: { state?: EvidenceState; action: PolicyAction | null; source: string; label: string; enforced?: OnchainControlPlane }) {
  return (
    <Panel title="Policy" icon="shield" right={<span title={source} className="inline-flex items-center gap-1.5 text-[10px] text-muted"><Icon name="chain" size={14} />{label}</span>}>
      <div className="tnum break-words text-xl font-semibold tracking-[-0.03em] text-ink">{action ?? "—"}</div>
      <div className="tnum mt-3 flex items-center gap-2 rounded px-2.5 py-2 text-[10px]" style={{ background: "var(--color-panel-2)", color: "var(--color-ink-dim)", border: "1px solid var(--color-line)" }}>{state ?? "UNREAD"}<Icon name="arrow" size={12} />{action ?? "UNAVAILABLE"}</div>
      {enforced && <div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] text-ink-dim"><span>Current RiskGuard · {enforced.fresh ? "FRESH" : "STALE"}</span><strong className="text-ink">{enforced.policy_action}</strong></div>}
    </Panel>
  );
}

function BasisCard({ result }: { result: ValuationResult }) {
  return (
    <Panel title="Market Basis" icon="basis">
      <dl className="grid grid-cols-2 gap-x-5 gap-y-2 text-xs">
        <StatusRow label="Token Move" value={pct(result.observed_token_move_pct)} icon="coin" />
        <StatusRow label="Model Move" value={pct(result.model_implied_move_pct)} icon="model" />
        <StatusRow label="Residual" value={pct(result.residual_premium_discount_pct)} icon="residual" />
        <StatusRow label={result.token_liquidity_usd == null ? "5m Token Volume" : "Liquidity"} value={compactUsd(result.token_liquidity_usd ?? result.token_volume_usd)} icon="depth" />
      </dl>
    </Panel>
  );
}

function StatusRow({ label, value, icon }: { label: string; value: string; icon: "coin" | "model" | "residual" | "depth" }) {
  return <div className="min-w-0"><dt className="text-[10px]" style={{ color: "var(--color-muted)" }}>{label}</dt><dd className="tnum mt-1 flex items-center gap-2 truncate text-lg font-medium leading-tight text-ink"><Icon name={icon} size={15} className="text-ink-dim" />{value}</dd></div>;
}

function actionFor(policy: OnchainPolicy, state: EvidenceState): PolicyAction {
  if (state === "SUPPORTED") return policy.on_supported;
  if (state === "INCONCLUSIVE") return policy.on_inconclusive;
  return policy.on_challenged;
}
