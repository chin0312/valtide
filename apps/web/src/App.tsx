import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchAssets,
  fetchDemoReplay,
  fetchHealth,
  fetchOnchain,
  fetchOnchainEnforcement,
  fetchOperationalHistory,
  fetchOperationalValuation,
  fetchRuntime,
} from "./api/client";
import type { EvidenceState, OnchainPolicy, PolicyAction, ValuationResult } from "./api/types";
import { EXAMPLE_DEMO_POLICY } from "./components/PolicyActionPanel";
import { ReasonCodes } from "./components/ReasonCodes";
import { RegistryPanel } from "./components/RegistryPanel";
import { Panel } from "./components/ui";
import { EVIDENCE } from "./lib/evidence";
import { ageLabel, compactUsd, money, pct, sigma } from "./lib/format";
import { deriveOnchainSync } from "./lib/onchain";
import { clampPosition } from "./lib/playback";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ObservationRecord } from "./views/ObservationRecord";
import { ReferenceComparison } from "./views/ReferenceComparison";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const backendUp = health.data === true;
  const assets = useQuery({ queryKey: ["assets"], queryFn: fetchAssets, retry: 0, enabled: backendUp, staleTime: 60_000 });
  const operational = useQuery({ queryKey: ["valuation", "operational", "NVDAx"], queryFn: fetchOperationalValuation, refetchInterval: 20_000, retry: 0 });
  const history = useQuery({ queryKey: ["history", "NVDAx", 288], queryFn: () => fetchOperationalHistory(288), refetchInterval: 30_000, retry: 0, enabled: !!operational.data });
  const demo = useQuery({ queryKey: ["demo-replay", "dense"], queryFn: () => fetchDemoReplay(), staleTime: Infinity });
  const runtime = useQuery({ queryKey: ["runtime", "NVDAx"], queryFn: fetchRuntime, refetchInterval: 30_000, retry: 0, enabled: backendUp });
  const onchain = useQuery({ queryKey: ["onchain", "NVDAx"], queryFn: fetchOnchain, refetchInterval: 45_000, retry: 0, enabled: backendUp });
  const enforcement = useQuery({ queryKey: ["onchain", "NVDAx", "enforcement"], queryFn: fetchOnchainEnforcement, refetchInterval: 45_000, retry: 0, enabled: backendUp });
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);

  const operationalResults = useMemo(() => {
    if (!operational.data) return [];
    return history.data?.length ? history.data : [operational.data];
  }, [history.data, operational.data]);
  const isOperational = operationalResults.length > 0;
  const results = isOperational ? operationalResults : demo.data?.results ?? [];

  useEffect(() => {
    if (!results.length) return;
    setPosition(isOperational ? results.length - 1 : 0);
    setPlaying(false);
  }, [isOperational, results.length]);

  if (!results.length) return <Loading />;

  const safePosition = clampPosition(position, results.length);
  const currentIndex = Math.floor(safePosition);
  const current = isOperational ? results[currentIndex] : interpolateResult(results, safePosition);
  const source = isOperational
    ? `Operational · ${results.length} observations`
    : demo.data?.source === "backend-scenario"
      ? `Demo scenario · ${results.length} periods`
      : `Demo fixture · ${results.length} periods`;
  const policy = onchain.data?.policy ?? (isOperational ? undefined : EXAMPLE_DEMO_POLICY);
  const policyAction = policy ? actionFor(policy, current.evidence_state) : null;
  const sync = isOperational ? deriveOnchainSync(operational.data, onchain.data) : undefined;
  const chainError = backendUp
    ? onchain.error instanceof Error ? onchain.error.message : "The deployed contracts could not be read."
    : "Local API not running; demo playback never writes to chain.";

  return (
    <div className="mx-auto min-h-full max-w-[1480px] px-4 py-4 sm:px-6">
      <AppHeader backendUp={backendUp} chainUp={!!onchain.data} source={source} assetCount={assets.data?.length ?? 1} />

      <main className="space-y-4">
        <MetricGrid current={current} isOperational={isOperational} />

        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <HistoricalReplay
            results={results}
            position={position}
            setPosition={setPosition}
            playing={playing}
            setPlaying={setPlaying}
            sourceLabel={source}
            showPlayback={!isOperational}
          />
          <div className="min-w-0 space-y-4">
            <ReferenceComparison r={current} />
            <PolicyCard state={current.evidence_state} action={policyAction} source={onchain.data ? "Deployed X Layer policy" : isOperational ? "Policy unavailable" : "Demo policy mapping"} />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <EvidenceCard result={current} />
          <BasisCard result={current} />
        </div>

        <ObservationRecord results={results} currentIndex={currentIndex} sourceLabelText={source} />

        <RegistryPanel
          controlPlane={onchain.data}
          enforcement={enforcement.data}
          runtime={runtime.data}
          sync={sync}
          mode={isOperational ? "operational" : "demo"}
          isLoading={backendUp && onchain.isLoading}
          isError={!onchain.data}
          errorDetail={chainError}
        />

        <footer className="border-t pt-3 font-mono text-[9px] uppercase tracking-[0.05em]" style={{ borderColor: "var(--color-line-subtle)", color: "var(--color-muted)" }}>
          {current.model_id} {current.model_version} · research prototype · browser read-only
        </footer>
      </main>
    </div>
  );
}

function AppHeader({ backendUp, chainUp, source, assetCount }: { backendUp: boolean; chainUp: boolean; source: string; assetCount: number }) {
  return (
    <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
      <div className="flex flex-wrap items-center gap-3 sm:gap-6">
        <h1 className="text-[22px] font-semibold tracking-[-0.04em] text-ink">Valtide</h1>
        <span className="rounded px-3 py-1.5 text-xs font-medium" style={{ background: "var(--color-panel-2)", color: "var(--color-ink)", border: "1px solid var(--color-line)" }}>Overview</span>
        <button disabled className="rounded px-3 py-1.5 text-left disabled:opacity-100" title="The current backend supports NVDAx only" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}>
          <span className="tnum text-xs font-medium text-ink">NVDAx</span>
          <span className="ml-2 text-[10px]" style={{ color: "var(--color-muted)" }}>{assetCount} supported asset</span>
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px]">
        <span className="rounded px-2 py-1 font-mono" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)" }}>{source}</span>
        <ConnectionLabel active={backendUp} activeText="API connected" inactiveText="Demo fallback" />
        <ConnectionLabel active={chainUp} activeText="X Layer read" inactiveText="On-chain unread" />
      </div>
    </header>
  );
}

function ConnectionLabel({ active, activeText, inactiveText }: { active: boolean; activeText: string; inactiveText: string }) {
  return <span className="inline-flex items-center gap-1.5" style={{ color: active ? "var(--color-supported)" : "var(--color-muted)" }}><i className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />{active ? activeText : inactiveText}</span>;
}

function MetricGrid({ current, isOperational }: { current: ValuationResult; isOperational: boolean }) {
  return (
    <section className="grid grid-cols-2 overflow-hidden rounded-[10px] md:grid-cols-3 xl:grid-cols-6" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <Metric label="Reference" value={money(current.reference_under_test)} sub="under test" />
      <Metric label="Valtide fair value" value={money(current.valtide_fair_value)} sub={`${money(current.fair_value_lower)}–${money(current.fair_value_upper)}`} />
      <Metric label="Token market" value={money(current.token_price)} sub={current.token_source ?? (isOperational ? "source unavailable" : "demo scenario")} />
      <Metric label="Deviation" value={pct(current.reference_deviation_pct)} sub={current.evidence_state} accent={EVIDENCE[current.evidence_state].fg} />
      <Metric label="Standardized" value={sigma(current.standardized_deviation)} sub="from fair value" />
      <Metric label="Last trusted" value={money(current.last_trusted_reference)} sub={`${ageLabel(current.reference_age_seconds)} old`} />
    </section>
  );
}

function Metric({ label, value, sub, accent }: { label: string; value: string; sub: string; accent?: string }) {
  return <div className="min-w-0 px-4 py-3.5" style={{ borderRight: "1px solid var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-2 truncate text-xl font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>{value}</div><div className="tnum mt-1 truncate text-[10px]" style={{ color: "var(--color-muted)" }}>{sub}</div></div>;
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
    <Panel title="Market basis">
      <dl className="grid grid-cols-2 gap-x-5 gap-y-2 text-xs">
        <StatusRow label="Token move" value={pct(result.observed_token_move_pct)} />
        <StatusRow label="Model move" value={pct(result.model_implied_move_pct)} />
        <StatusRow label="Residual" value={pct(result.residual_premium_discount_pct)} />
        <StatusRow label="Liquidity" value={compactUsd(result.token_liquidity_usd)} />
      </dl>
    </Panel>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return <div className="min-w-0"><dt className="text-[10px]" style={{ color: "var(--color-muted)" }}>{label}</dt><dd className="tnum mt-0.5 truncate text-ink">{value}</dd></div>;
}

function actionFor(policy: OnchainPolicy, state: EvidenceState): PolicyAction {
  if (state === "SUPPORTED") return policy.on_supported;
  if (state === "INCONCLUSIVE") return policy.on_inconclusive;
  return policy.on_challenged;
}

function interpolateResult(results: ValuationResult[], position: number): ValuationResult {
  const lowerIndex = Math.max(0, Math.min(Math.floor(position), results.length - 1));
  const upperIndex = Math.min(lowerIndex + 1, results.length - 1);
  const from = results[lowerIndex];
  const to = results[upperIndex];
  const t = Math.max(0, Math.min(1, position - lowerIndex));
  if (lowerIndex === upperIndex || t === 0) return from;
  const timestamp = new Date(Date.parse(from.timestamp) + (Date.parse(to.timestamp) - Date.parse(from.timestamp)) * t).toISOString();
  return {
    ...from,
    timestamp,
    token_observed_at: from.token_observed_at == null || to.token_observed_at == null ? from.token_observed_at : timestamp,
    reference_under_test_ts: from.reference_under_test_ts == null || to.reference_under_test_ts == null ? from.reference_under_test_ts : timestamp,
    last_trusted_reference: lerp(from.last_trusted_reference, to.last_trusted_reference, t),
    token_price: lerpNullable(from.token_price, to.token_price, t),
    token_volume: lerpNullable(from.token_volume, to.token_volume, t),
    token_volume_usd: lerpNullable(from.token_volume_usd, to.token_volume_usd, t),
    token_liquidity_usd: lerpNullable(from.token_liquidity_usd, to.token_liquidity_usd, t),
    external_constructed_reference: lerpNullable(from.external_constructed_reference, to.external_constructed_reference, t),
    valtide_fair_value: lerp(from.valtide_fair_value, to.valtide_fair_value, t),
    fair_value_lower: lerp(from.fair_value_lower, to.fair_value_lower, t),
    fair_value_upper: lerp(from.fair_value_upper, to.fair_value_upper, t),
    observed_token_move_pct: lerpNullable(from.observed_token_move_pct, to.observed_token_move_pct, t),
    model_implied_move_pct: lerp(from.model_implied_move_pct, to.model_implied_move_pct, t),
    residual_premium_discount_pct: lerpNullable(from.residual_premium_discount_pct, to.residual_premium_discount_pct, t),
    reference_under_test: lerpNullable(from.reference_under_test, to.reference_under_test, t),
    reference_under_test_age_seconds: lerpNullable(from.reference_under_test_age_seconds, to.reference_under_test_age_seconds, t),
    reference_deviation_pct: lerpNullable(from.reference_deviation_pct, to.reference_deviation_pct, t),
    standardized_deviation: lerpNullable(from.standardized_deviation, to.standardized_deviation, t),
    confidence: lerpNullable(from.confidence, to.confidence, t),
    reference_age_seconds: Math.round(lerp(from.reference_age_seconds, to.reference_age_seconds, t)),
  };
}

function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * t;
}

function lerpNullable(from: number | null | undefined, to: number | null | undefined, t: number): number | null {
  if (from == null || to == null) return from ?? null;
  return lerp(from, to, t);
}

function Loading() {
  return <div className="grid min-h-screen place-items-center"><div className="text-sm" style={{ color: "var(--color-muted)" }}>Loading Valtide…</div></div>;
}
