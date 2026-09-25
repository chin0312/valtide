import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchDemoReplay,
  fetchHealth,
  fetchOnchain,
  fetchOnchainEnforcement,
  fetchOperationalHistory,
  fetchOperationalValuation,
} from "./api/client";
import type { EvidenceState, OnchainPolicy, PolicyAction, ValuationResult } from "./api/types";
import { EXAMPLE_DEMO_POLICY } from "./components/PolicyActionPanel";
import { ReasonCodes } from "./components/ReasonCodes";
import { RegistryPanel } from "./components/RegistryPanel";
import { Panel } from "./components/ui";
import { EVIDENCE } from "./lib/evidence";
import { dateTimeUTC, money, pct } from "./lib/format";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ReferenceComparison } from "./views/ReferenceComparison";

const ASSET_QUEUE = [
  { symbol: "SPYx", label: "Index equity", status: "Research queue" },
  { symbol: "TSLAx", label: "Single equity", status: "Research queue" },
  { symbol: "AAPLx", label: "Single equity", status: "Research queue" },
];

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const operational = useQuery({ queryKey: ["valuation", "operational", "NVDAx"], queryFn: fetchOperationalValuation, refetchInterval: 20_000, retry: 0 });
  const history = useQuery({ queryKey: ["history", "NVDAx", 288], queryFn: () => fetchOperationalHistory(288), refetchInterval: 30_000, retry: 0, enabled: !!operational.data });
  const demo = useQuery({ queryKey: ["demo-replay", "dense"], queryFn: () => fetchDemoReplay(), staleTime: Infinity });
  const onchain = useQuery({ queryKey: ["onchain", "NVDAx"], queryFn: fetchOnchain, refetchInterval: 45_000, retry: 0, enabled: !!health.data });
  const enforcement = useQuery({ queryKey: ["onchain", "NVDAx", "enforcement"], queryFn: fetchOnchainEnforcement, refetchInterval: 45_000, retry: 0, enabled: !!health.data });
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const operationalResults = useMemo(() => {
    if (!operational.data) return [];
    return history.data?.length ? history.data : [operational.data];
  }, [history.data, operational.data]);
  const isOperational = operationalResults.length > 0;
  const results = isOperational ? operationalResults : demo.data?.results ?? [];

  useEffect(() => {
    if (!results.length) return;
    setIndex(isOperational ? results.length - 1 : 0);
    setPlaying(false);
  }, [isOperational, results.length]);

  if (!results.length) return <Loading />;

  const current = results[Math.min(index, results.length - 1)];
  const source = isOperational
    ? "Operational · 24h"
    : demo.data?.source === "backend-scenario"
      ? "Demo · 1m periods"
      : "Demo fixture · 1m periods";
  const policy = onchain.data?.policy ?? (isOperational ? undefined : EXAMPLE_DEMO_POLICY);
  const policyAction = policy ? actionFor(policy, current.evidence_state) : null;

  return (
    <div className="mx-auto min-h-full max-w-[1480px] px-4 py-4 sm:px-6">
      <AppHeader backendUp={!!health.data} source={source} />

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="order-2 space-y-4 lg:order-1">
          <AssetRail current={current} source={source} />
          <SystemCard backendUp={!!health.data} chainUp={!!onchain.data} timestamp={current.timestamp} />
        </aside>

        <main className="order-1 min-w-0 space-y-4 lg:order-2">
          <MetricGrid current={current} />

          <HistoricalReplay
            results={results}
            index={index}
            setIndex={setIndex}
            playing={playing}
            setPlaying={setPlaying}
            sourceLabel={source}
            showPlayback={!isOperational}
          />

          <div className="grid gap-4 md:grid-cols-3">
            <EvidenceCard result={current} />
            <PolicyCard state={current.evidence_state} action={policyAction} source={onchain.data ? "X Layer policy" : isOperational ? "Policy unavailable" : "Demo policy"} />
            <BasisCard result={current} />
          </div>

          <ReferenceComparison r={current} />

          {onchain.data && <RegistryPanel controlPlane={onchain.data} enforcement={enforcement.data} mode="operational" />}

          <footer className="border-t pt-3 font-mono text-[9px] uppercase tracking-[0.05em]" style={{ borderColor: "var(--color-line-subtle)", color: "var(--color-muted)" }}>
            {current.model_id} {current.model_version} · research prototype · browser read-only
          </footer>
        </main>
      </div>
    </div>
  );
}

function AppHeader({ backendUp, source }: { backendUp: boolean; source: string }) {
  return (
    <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
      <div className="flex items-center gap-6">
        <h1 className="text-[22px] font-semibold tracking-[-0.04em] text-ink">Valtide</h1>
        <span className="rounded px-3 py-1.5 text-xs font-medium" style={{ background: "var(--color-panel-2)", color: "var(--color-ink)", border: "1px solid var(--color-line)" }}>Overview</span>
      </div>
      <div className="flex items-center gap-3 text-[11px]">
        <span className="rounded px-2 py-1 font-mono" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)" }}>{source}</span>
        <span className="inline-flex items-center gap-1.5" style={{ color: backendUp ? "var(--color-supported)" : "var(--color-muted)" }}><i className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />{backendUp ? "Backend online" : "Backend offline"}</span>
      </div>
    </header>
  );
}

function AssetRail({ current, source }: { current: ValuationResult; source: string }) {
  const state = EVIDENCE[current.evidence_state];
  return (
    <Panel title="Asset status">
      <div className="rounded-lg p-3" style={{ background: "var(--color-panel-2)", border: `1px solid ${state.line}` }}>
        <div className="flex items-center justify-between"><strong className="tnum text-sm text-ink">NVDAx</strong><span className="font-mono text-[10px] font-medium" style={{ color: state.fg }}>{state.label}</span></div>
        <div className="mt-1 text-[11px]" style={{ color: "var(--color-muted)" }}>{source}</div>
        <div className="tnum mt-3 text-xl font-medium text-ink">{money(current.reference_under_test)}</div>
      </div>
      <div className="mt-3">
        {ASSET_QUEUE.map((asset, index) => (
          <div key={asset.symbol} className="flex items-center justify-between py-3" style={{ borderTop: index === 0 ? undefined : "1px solid var(--color-line-subtle)" }}>
            <div><div className="tnum text-xs font-medium text-ink">{asset.symbol}</div><div className="text-[10px]" style={{ color: "var(--color-muted)" }}>{asset.label}</div></div>
            <span className="text-[10px]" style={{ color: "var(--color-muted)" }}>{asset.status}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SystemCard({ backendUp, chainUp, timestamp }: { backendUp: boolean; chainUp: boolean; timestamp: string }) {
  return (
    <Panel title="System">
      <dl className="space-y-2 text-xs">
        <StatusRow label="Backend" value={backendUp ? "Online" : "Offline"} ok={backendUp} />
        <StatusRow label="X Layer" value={chainUp ? "Connected" : "Unavailable"} ok={chainUp} />
        <StatusRow label="Observed" value={dateTimeUTC(timestamp)} />
      </dl>
    </Panel>
  );
}

function StatusRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return <div className="flex items-center justify-between gap-3"><dt style={{ color: "var(--color-muted)" }}>{label}</dt><dd className="tnum truncate text-right" style={{ color: ok == null ? "var(--color-ink-dim)" : ok ? "var(--color-supported)" : "var(--color-muted)" }}>{value}</dd></div>;
}

function MetricGrid({ current }: { current: ValuationResult }) {
  return (
    <section className="grid grid-cols-2 overflow-hidden rounded-[10px] lg:grid-cols-4" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <Metric label="Reference" value={money(current.reference_under_test)} sub="under test" />
      <Metric label="Valtide fair value" value={money(current.valtide_fair_value)} sub={`${money(current.fair_value_lower)}–${money(current.fair_value_upper)}`} />
      <Metric label="Token market" value={money(current.token_price)} sub="NVDAx" />
      <Metric label="Deviation" value={pct(current.reference_deviation_pct)} sub={current.evidence_state} accent={EVIDENCE[current.evidence_state].fg} />
    </section>
  );
}

function Metric({ label, value, sub, accent }: { label: string; value: string; sub: string; accent?: string }) {
  return <div className="min-w-0 px-4 py-3.5" style={{ borderRight: "1px solid var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-2 truncate text-2xl font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>{value}</div><div className="tnum mt-1 truncate text-[10px]" style={{ color: "var(--color-muted)" }}>{sub}</div></div>;
}

function EvidenceCard({ result }: { result: ValuationResult }) {
  const state = EVIDENCE[result.evidence_state];
  const outside = result.reason_codes.includes("REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL");
  const summary = result.evidence_state === "SUPPORTED"
    ? "Reference remains inside the supported range."
    : result.evidence_state === "INCONCLUSIVE"
      ? `${outside ? "Outside range" : "Mixed evidence"}; challenge threshold not met.`
      : "Reference materially exceeds the supported range.";
  return (
    <Panel title="Evidence">
      <div className="text-2xl font-semibold tracking-[-0.03em]" style={{ color: state.fg }}>{state.label}</div>
      <p className="mt-2 text-xs" style={{ color: "var(--color-ink-dim)" }}>{summary}</p>
      <div className="mt-4"><ReasonCodes codes={result.reason_codes.slice(0, 2)} evidenceState={result.evidence_state} /></div>
    </Panel>
  );
}

function PolicyCard({ state, action, source }: { state: EvidenceState; action: PolicyAction | null; source: string }) {
  return (
    <Panel title="Policy">
      <div className="tnum break-words text-xl font-semibold tracking-[-0.03em] text-ink">{action ?? "—"}</div>
      <div className="tnum mt-3 rounded px-2.5 py-2 text-[10px]" style={{ background: "var(--color-panel-2)", color: "var(--color-ink-dim)", border: "1px solid var(--color-line)" }}>{state} → {action ?? "UNAVAILABLE"}</div>
      <div className="mt-3 text-[10px]" style={{ color: "var(--color-muted)" }}>{source}</div>
    </Panel>
  );
}

function BasisCard({ result }: { result: ValuationResult }) {
  return (
    <Panel title="Price basis">
      <dl className="space-y-2 text-xs">
        <StatusRow label="Token move" value={pct(result.observed_token_move_pct)} />
        <StatusRow label="Model move" value={pct(result.model_implied_move_pct)} />
        <StatusRow label="Residual" value={pct(result.residual_premium_discount_pct)} />
      </dl>
    </Panel>
  );
}

function actionFor(policy: OnchainPolicy, state: EvidenceState): PolicyAction {
  if (state === "SUPPORTED") return policy.on_supported;
  if (state === "INCONCLUSIVE") return policy.on_inconclusive;
  return policy.on_challenged;
}

function Loading() {
  return <div className="grid min-h-screen place-items-center"><div className="text-sm" style={{ color: "var(--color-muted)" }}>Loading Valtide…</div></div>;
}
