import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  DEMO_REPLAY_QUERY_KEY,
  assetQueryKeys,
  DEFAULT_ASSET,
  fetchDemoReplay,
  fetchAssets,
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
import { ageLabel, compactUsd, money, pct, reasonLabel, sourceLabel } from "./lib/format";
import { deriveOnchainSync } from "./lib/onchain";
import { clampPosition, mergeObservations, rebasePosition } from "./lib/playback";
import { evidenceCopy, modelDistanceLabel } from "./lib/semantics";
import { HistoricalReplay } from "./views/HistoricalReplay";
import { ObservationRecord } from "./views/ObservationRecord";
import { ReferenceComparison } from "./views/ReferenceComparison";
import { ModelEvidence } from "./views/ModelEvidence";
import { filterDemoResults, filterHistoricalResults, filterOperationalResults, operationalCoverageNotice, OPERATIONAL_HISTORY_LIMITS, OPERATIONAL_HISTORY_MAX, type DemoRange, type HistoricalRange, type OperationalRange } from "./views/OperationalTimeline";
import { ObservationAudit } from "./components/ObservationAudit";
import { LandingPage } from "./components/LandingPage";
import { DocsPage } from "./components/DocsPage";
import { MethodologyPage } from "./components/MethodologyPage";
import { LogoMotionPrototype } from "./components/LogoMotionPrototype";
import { AnimatedValtideLogo } from "./components/AnimatedValtideLogo";
import { AssetPicker } from "./components/AssetPicker";
import { InstrumentPassport } from "./components/InstrumentPassport";
import { PolicyFoundry } from "./components/PolicyFoundry";

type Context = "Operational" | "Historical" | "Demo";
const EMPTY_RESULTS: ValuationResult[] = [];

export function consoleContextFromSearch(search: string): Context {
  const requested = new URLSearchParams(search).get("context")?.toLowerCase();
  if (requested === "historical") return "Historical";
  if (requested === "demo") return "Demo";
  return "Operational";
}

export function effectiveContextAsset(context: Context, selectedAsset: string): string {
  return context === "Demo" ? DEFAULT_ASSET : selectedAsset;
}

export default function App() {
  const view = typeof window === "undefined" ? "console" : new URLSearchParams(window.location.search).get("view");
  const showConsole = view === "console";
  const showLogoPrototype = view === "logo";
  const path = typeof window === "undefined" ? "/" : window.location.pathname.replace(/\/+$/, "") || "/";
  useEffect(() => {
    document.title = showLogoPrototype
      ? "Valtide — Animated Logo Prototype"
      : showConsole
      ? "Valtide — Validation Console"
      : path === "/docs" || path.startsWith("/docs/")
        ? "Valtide Docs — Collateral Validation Evidence"
        : path === "/methodology" || path.startsWith("/methodology/")
          ? "Valtide Methodology — Collateral Validation Evidence"
        : "Valtide — Independent Collateral Validation";
  }, [path, showConsole, showLogoPrototype]);
  if (showLogoPrototype) return <LogoMotionPrototype />;
  if (showConsole) return <ValidationConsole />;
  if (path === "/docs" || path.startsWith("/docs/")) return <DocsPage />;
  if (path === "/methodology" || path.startsWith("/methodology/")) return <MethodologyPage />;
  return <LandingPage />;
}

function ValidationConsole() {
  const [context, setContext] = useState<Context>(() => consoleContextFromSearch(typeof window === "undefined" ? "" : window.location.search));
  const [selectedAsset, setSelectedAsset] = useState<string>(DEFAULT_ASSET);
  const [range, setRange] = useState<OperationalRange>("24H");
  const [historicalRange, setHistoricalRange] = useState<HistoricalRange>("ALL");
  const [demoRange, setDemoRange] = useState<DemoRange>("FULL");
  const isOperational = context === "Operational";
  const contextAsset = effectiveContextAsset(context, selectedAsset);
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 });
  const backendUp = health.data === true;
  const assets = useQuery({ queryKey: assetQueryKeys.assets, queryFn: fetchAssets, refetchInterval: 60_000, retry: 0 });
  const selectedAssetInfo = assets.data?.find((item) => item.asset === contextAsset);
  const profile = selectedAssetInfo?.reference_profile ?? "profile-unresolved";
  const operational = useQuery({ queryKey: assetQueryKeys.operational(contextAsset, profile), queryFn: () => fetchOperationalValuation(contextAsset), refetchInterval: 20_000, retry: 0, enabled: isOperational && backendUp });
  const history = useQuery({ queryKey: assetQueryKeys.history(contextAsset, OPERATIONAL_HISTORY_MAX, profile), queryFn: () => fetchOperationalHistory(contextAsset, OPERATIONAL_HISTORY_MAX), refetchInterval: 5 * 60_000, retry: 0, enabled: isOperational && !!operational.data });
  const historical = useQuery({ queryKey: assetQueryKeys.historical(contextAsset, profile), queryFn: () => fetchHistoricalReplay(contextAsset), staleTime: Infinity, retry: 0, enabled: context === "Historical" && backendUp });
  const demo = useQuery({ queryKey: DEMO_REPLAY_QUERY_KEY, queryFn: () => fetchDemoReplay(DEFAULT_ASSET), staleTime: Infinity, retry: 0, enabled: context === "Demo" });
  const runtime = useQuery({ queryKey: assetQueryKeys.runtime(contextAsset), queryFn: () => fetchRuntime(contextAsset), refetchInterval: 30_000, retry: 0, enabled: backendUp });
  const onchain = useQuery({ queryKey: assetQueryKeys.onchain(contextAsset), queryFn: () => fetchOnchain(contextAsset), refetchInterval: 45_000, retry: 0, enabled: backendUp && !!selectedAssetInfo?.onchain_binding_configured });
  const enforcement = useQuery({ queryKey: assetQueryKeys.enforcement(contextAsset), queryFn: () => fetchOnchainEnforcement(contextAsset), refetchInterval: 45_000, retry: 0, enabled: backendUp && !!selectedAssetInfo?.onchain_binding_configured });
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [followLatest, setFollowLatest] = useState(true);

  const allOperationalResults = useMemo(() => {
    if (!operational.data) return [];
    return mergeObservations(history.data ?? [], operational.data);
  }, [history.data, operational.data]);
  const operationalResults = useMemo(() => filterOperationalResults(allOperationalResults, range), [allOperationalResults, range]);
  const historicalResults = useMemo(() => filterHistoricalResults(historical.data?.results ?? EMPTY_RESULTS, historicalRange), [historical.data, historicalRange]);
  const demoResults = useMemo(() => filterDemoResults(demo.data?.results ?? EMPTY_RESULTS, demoRange), [demo.data, demoRange]);
  const results = isOperational ? operationalResults : context === "Historical" ? historicalResults : demoResults;
  const activeRange = context === "Operational" ? range : context === "Historical" ? historicalRange : demoRange;
  const previous = useRef({ results, context, activeRange, selectedAsset });

  useEffect(() => {
    const before = previous.current;
    previous.current = { results, context, activeRange, selectedAsset };
    if (before.selectedAsset !== selectedAsset || before.context !== context || before.activeRange !== activeRange || (!before.results.length && results.length)) {
      setPosition(context === "Demo" ? 0 : Math.max(0, results.length - 1));
      setFollowLatest(isOperational);
      setPlaying(false);
    } else if (isOperational && followLatest) {
      setPosition(results.length - 1);
    } else {
      setPosition((value) => rebasePosition(value, before.results, results));
    }
  }, [context, activeRange, isOperational, results, followLatest, selectedAsset]);

  const safePosition = clampPosition(position, results.length);
  const currentIndex = Math.floor(safePosition);
  const current = results[currentIndex];
  const reviewing = isOperational && !!current && !!operational.data && Date.parse(current.timestamp) < Date.parse(operational.data.timestamp);
  const source = isOperational
    ? `Operational · ${results.length} observations`
    : context === "Historical" ? `Historical · ${results.length} observations`
    : !demo.data ? "Demo · Loading" : demo.data.source === "backend-scenario"
      ? `Demo Scenario · ${demo.data.results.length} Synthetic Steps`
      : `Demo Backup · ${demo.data.results.length} Synthetic Steps`;
  const controlPlane = onchain.isError ? undefined : onchain.data;
  const policy = context === "Demo" ? EXAMPLE_DEMO_POLICY : controlPlane?.policy ?? null;
  const policyAction = policy && current ? actionFor(policy, current.evidence_state) : null;
  const sync = isOperational ? deriveOnchainSync(operational.data, controlPlane) : undefined;
  const activeQuery = isOperational ? operational : context === "Historical" ? historical : demo;
  const isDegraded = activeQuery.isError || (isOperational && (history.isError || runtime.data?.last_tick_status === "failure"));
  const statusMessage = activeQuery.error instanceof Error ? activeQuery.error.message : "Data unavailable";
  const runtimeNotWarmed = isOperational && (runtime.data?.has_live_result === false || (operational.error instanceof ApiError && operational.error.status === 503));
  const chainError = !selectedAssetInfo?.onchain_binding_configured
    ? `X Layer is not configured for ${contextAsset}. Offchain validation remains available.`
    : backendUp
    ? onchain.error instanceof Error ? onchain.error.message : "The deployed contracts could not be read."
    : "Backend unavailable. Showing the last available data.";

  return (
    <div id="validation-console" className="mx-auto min-h-full max-w-[1480px] px-4 py-4 sm:px-6">
      <AppHeader
        backendUp={backendUp}
        chainUp={!!controlPlane}
        chainConfigured={!!selectedAssetInfo?.onchain_binding_configured}
        source={source}
        context={context}
        onContextChange={setContext}
        assets={assets.data ?? []}
        selectedAsset={contextAsset}
        onAssetChange={(asset) => {
          setSelectedAsset(asset);
          setPosition(0);
          setPlaying(false);
          setFollowLatest(true);
        }}
      />
      {selectedAssetInfo && selectedAssetInfo.readiness_error_codes.length > 0 && <div role="status" className="mb-4 rounded px-3 py-2 text-xs" style={{ color: "var(--color-ink-dim)", background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-line-subtle)" }}>
        Operational Readiness Issue: {selectedAssetInfo.readiness_error_codes.map(reasonLabel).join(" · ")}
      </div>}

      <main className="space-y-4">
        {isDegraded && current && <div role="status" className="rounded px-4 py-3 text-xs text-ink-dim" style={{ background: "var(--color-inconclusive-soft)" }}>{context} degraded · showing last available observations. {history.isError && isOperational ? "History unavailable. " : ""}{activeQuery.isError ? statusMessage : runtime.data?.last_error}</div>}
        {!current ? <Panel title={`${context} ${activeQuery.isLoading ? "Loading" : "Unavailable"}`}><p role="status" className="text-xs text-ink-dim">{activeQuery.isLoading ? `Loading ${contextAsset} ${context.toLowerCase()} observations…` : runtimeNotWarmed ? "Runtime not warmed yet." : statusMessage}</p></Panel> : <>
        <DecisionSummary current={current} action={policyAction} />
        <MetricGrid current={current} isDemo={context === "Demo"} observationCount={results.length} />

        <div className="grid items-stretch gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <HistoricalReplay
            asset={contextAsset}
            results={results}
            position={position}
            setPosition={setPosition}
            playing={playing}
            setPlaying={setPlaying}
            sourceLabel={source}
            onReview={() => setFollowLatest(false)}
            followingLatest={isOperational && followLatest}
            onLatest={isOperational ? () => { setPlaying(false); setFollowLatest(true); setPosition(results.length - 1); } : undefined}
            viewportKey={`${contextAsset}:${profile}:${context}:${activeRange}`}
            periodMs={context === "Demo" ? 600 : 120}
            coverageNotice={isOperational ? operationalCoverageNotice(allOperationalResults, range) : undefined}
            onReset={() => {
              setPlaying(false);
              if (context === "Operational") {
                setRange("24H");
                setFollowLatest(true);
                setPosition(Math.max(0, allOperationalResults.length - 1));
              } else if (context === "Historical") {
                setHistoricalRange("ALL");
                setPosition(Math.max(0, (historical.data?.results.length ?? 1) - 1));
              } else {
                setDemoRange("FULL");
                setPosition(0);
              }
            }}
            rangeControl={<RangeControls context={context} range={activeRange} onChange={(value) => { if (context === "Operational") setRange(value as OperationalRange); else if (context === "Historical") setHistoricalRange(value as HistoricalRange); else setDemoRange(value as DemoRange); }} />}
          />
          <div className="flex min-w-0 flex-col gap-4">
            <ReferenceComparison r={current} />
            <PolicyCard
              state={current.evidence_state}
              action={policyAction}
              label={context === "Demo" ? "Demo Policy" : "Current Policy Mapping"}
              source={context === "Demo" ? "Demo policy only; it is not a deployed policy or action" : context === "Historical" || reviewing ? "Selected evidence under today's policy; not a historical onchain decision" : "Curator mapping for this evidence; current RiskGuard action is shown separately"}
              enforced={isOperational && !reviewing ? controlPlane : undefined}
            />
            {context === "Demo" && <details className="rounded-[10px]" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
              <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-ink">Advanced: Policy Proposal</summary>
              <div className="border-t p-3" style={{ borderColor: "var(--color-line-subtle)" }}><PolicyFoundry /></div>
            </details>}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <EvidenceCard result={current} />
          <BasisCard result={current} />
        </div>

        <ObservationRecord results={results} currentIndex={currentIndex} sourceLabelText={source} />
        </>}
        <ObservationAudit result={current} context={context} runtime={runtime.isError ? undefined : runtime.data} controlPlane={controlPlane} />

        {context === "Demo" && <details className="rounded-[10px]" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
          <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-ink">Demo: Token Rights Metadata</summary>
          <div className="border-t p-3" style={{ borderColor: "var(--color-line-subtle)" }}><InstrumentPassport /></div>
        </details>}

        {context === "Historical" && <ModelEvidence asset={contextAsset} profile={profile} />}

        {selectedAssetInfo?.onchain_binding_configured && <RegistryPanel
          controlPlane={controlPlane}
          enforcement={enforcement.isError ? undefined : enforcement.data}
          runtime={runtime.isError ? undefined : runtime.data}
          sync={sync}
          bindingConfigured={!!selectedAssetInfo?.onchain_binding_configured}
          mode={context === "Demo" ? "demo" : context === "Historical" || reviewing ? "historical" : "operational"}
          isLoading={backendUp && onchain.isLoading}
          isError={!controlPlane}
          errorDetail={chainError}
        />}

      </main>
    </div>
  );
}

function AppHeader({ backendUp, chainUp, chainConfigured, source, context, onContextChange, assets, selectedAsset, onAssetChange }: {
  backendUp: boolean;
  chainUp: boolean;
  chainConfigured: boolean;
  source: string;
  context: Context;
  onContextChange: (context: Context) => void;
  assets: AssetInfo[];
  selectedAsset: string;
  onAssetChange: (asset: string) => void;
}) {
  const assetOptions = assets.filter((item) => item.api_exposed);
  return (
    <header className="mb-4 flex flex-wrap items-center justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
      <div className="flex flex-wrap items-center gap-3 sm:gap-6">
        <a href="./" className="flex items-center gap-2.5 text-[22px] font-semibold tracking-[-0.04em] text-ink no-underline"><AnimatedValtideLogo className="valtide-logo-motion" /><span>Valtide</span></a>
        <nav aria-label="Evidence context" className="flex gap-1 rounded p-1" style={{ border: "1px solid var(--color-line)" }}>{(["Operational", "Historical", "Demo"] as Context[]).map((option) => <button key={option} aria-pressed={context === option} onClick={() => onContextChange(option)} className="rounded px-2.5 py-1.5 text-xs font-medium" style={{ background: context === option ? "var(--color-panel-2)" : undefined, color: context === option ? "var(--color-ink)" : "var(--color-muted)" }}>{option}</button>)}</nav>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px]">
        {context !== "Demo" && assetOptions.length > 0 && <AssetPicker assets={assetOptions} selectedAsset={selectedAsset} onChange={onAssetChange} />}
        <span className="rounded px-2 py-1 font-mono" style={{ color: "var(--color-accent)", background: "var(--color-accent-soft)" }}>{source}</span>
        <ConnectionLabel active={backendUp} activeText="API Connected" inactiveText="API Unavailable" />
        {chainConfigured && <ConnectionLabel active={chainUp} activeText="X Layer Connected" inactiveText="X Layer Unavailable" />}
      </div>
    </header>
  );
}

function RangeControls({ context, range, onChange }: { context: Context; range: string; onChange: (range: string) => void }) {
  const options = context === "Operational" ? Object.keys(OPERATIONAL_HISTORY_LIMITS) : context === "Historical" ? ["1H", "6H", "24H", "3D", "7D", "ALL"] : ["5M", "10M", "15M", "FULL"];
  return <div className="flex gap-1" aria-label={`${context} history range`}>{options.map((option) => <button key={option} type="button" aria-pressed={range === option} onClick={() => onChange(option)} className="rounded px-2.5 py-1 font-mono text-[10px] font-medium" style={{ color: range === option ? "var(--color-accent)" : "var(--color-muted)", background: range === option ? "var(--color-accent-soft)" : undefined }}>{option}</button>)}</div>;
}

function ConnectionLabel({ active, activeText, inactiveText }: { active: boolean; activeText: string; inactiveText: string }) {
  return <span className="inline-flex items-center gap-1.5" style={{ color: active ? "var(--color-supported)" : "var(--color-muted)" }}><i className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />{active ? activeText : inactiveText}</span>;
}

function DecisionSummary({ current, action }: { current: ValuationResult; action: PolicyAction | null }) {
  const finding = evidenceCopy(current);
  return <section className="grid gap-4 rounded-[10px] p-5 md:grid-cols-[minmax(0,1fr)_minmax(220px,.45fr)]" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)", borderLeft: `3px solid ${EVIDENCE[current.evidence_state].fg}` }}>
    <div><div className="eyebrow" style={{ color: "var(--color-muted)" }}>Current Finding</div><h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-ink">{finding.title}</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-ink-dim">{finding.detail}</p></div>
    <div className="md:border-l md:pl-4" style={{ borderColor: "var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>Policy Action</div><div className="mt-2 text-lg font-semibold text-ink">{plainAction(action)}</div></div>
  </section>;
}

function MetricGrid({ current, isDemo, observationCount }: { current: ValuationResult; isDemo: boolean; observationCount: number }) {
  const unified = current.validation_target === "xstock_observed_price" || current.reference_profile === "unified_xstock_p1ac_xperp_evidence_v1";
  return (
    <section aria-label={`${observationCount} observations in the selected window; classification count, not performance`} className="grid grid-cols-2 overflow-hidden rounded-[10px] md:grid-cols-3 xl:grid-cols-6" style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      <Metric label="Observed xStock" value={money(current.token_price)} sub={current.token_source ? sourceLabel(current.token_source) : isDemo ? "Demo Scenario" : "Source unavailable"} />
      <Metric label="Valtide Fair Value" value={money(current.valtide_fair_value)} sub={`${money(current.fair_value_lower)}–${money(current.fair_value_upper)} · ${Math.round(current.interval_coverage_target * 100)}% Valuation Range`} />
      <Metric label="X-Perp" value={money(current.xperp_index_price ?? current.reference_under_test)} sub={sourceLabel(current.xperp_index_source ?? current.reference_under_test_source)} />
      <Metric label="xStock Vs Model" value={pct(current.xstock_vs_p1ac_deviation_pct ?? current.residual_premium_discount_pct)} sub={current.evidence_state} accent={EVIDENCE[current.evidence_state].fg} />
      <Metric label="Model Distance" value={modelDistanceLabel(current.challenger_detector?.score_name, current.challenger_detector?.score)} sub="xStock ↔ Valtide Model" />
      <Metric label="Last Trusted Underlying" value={money(current.last_trusted_reference)} sub={ageLabel(current.reference_age_seconds) === "—" ? "—" : `Updated ${ageLabel(current.reference_age_seconds)} Ago`} />
    </section>
  );
}

function Metric({ label, value, sub, accent }: { label: string; value: string; sub: string; accent?: string }) {
  return <div className="min-w-0 px-4 py-3.5" style={{ borderRight: "1px solid var(--color-line-subtle)" }}><div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div><div className="tnum mt-2 truncate text-xl font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>{value}</div><div className="tnum mt-1 truncate text-[10px]" style={{ color: "var(--color-muted)" }}>{sub}</div></div>;
}

function EvidenceCard({ result }: { result: ValuationResult }) {
  const state = EVIDENCE[result.evidence_state];
  return (
    <Panel title="Evidence Assessment" icon="evidence">
      <div className="text-2xl font-semibold tracking-[-0.03em]" style={{ color: state.fg }}>{state.label}</div>
      <div className="mt-4"><ReasonCodes codes={result.reason_codes} evidenceState={result.evidence_state} /></div>
    </Panel>
  );
}

function PolicyCard({ state, action, source, label, enforced }: { state?: EvidenceState; action: PolicyAction | null; source: string; label: string; enforced?: OnchainControlPlane }) {
  return (
    <Panel title="Policy Action" icon="shield" right={<span title={source} className="inline-flex items-center gap-1.5 text-[10px] text-muted"><Icon name="chain" size={14} />{label}</span>}>
      <div className="break-words text-xl font-semibold tracking-[-0.03em] text-ink">{plainAction(action)}</div>
      <div className="mt-3">
        <div className="eyebrow text-muted">Reason</div>
        <div className="mt-1 text-sm text-ink-dim">{plainEvidenceReason(state)}</div>
      </div>
      {!action && <p className="mt-3 text-xs text-ink-dim">No curator policy is connected for this asset.</p>}
      <dl className="mt-3 grid gap-2 rounded px-3 py-3 text-xs" style={{ border: "1px solid var(--color-line)" }}>
        <PolicyDetail label="Evidence State" value={state ?? "—"} />
        <PolicyDetail label="Policy Mapping" value={action ? plainAction(action) : "No Policy Connected"} />
        {enforced && <PolicyDetail label="RiskGuard Status" value={enforced.fresh ? "Fresh" : "Stale"} />}
        {enforced && <PolicyDetail label="Enforced Action" value={plainAction(enforced.policy_action)} />}
      </dl>
    </Panel>
  );
}

function PolicyDetail({ label, value }: { label: string; value: string }) {
  return <div className="flex flex-wrap items-baseline justify-between gap-2"><dt className="text-muted">{label}</dt><dd className="technical-mono text-right text-ink">{value}</dd></div>;
}

function plainEvidenceReason(state?: EvidenceState): string {
  if (state === "SUPPORTED") return "Observed xStock Is Supported";
  if (state === "INCONCLUSIVE") return "Evidence Is Inconclusive";
  if (state === "CHALLENGED") return "Observed xStock Is Challenged";
  return "Evidence Is Unavailable";
}

function BasisCard({ result }: { result: ValuationResult }) {
  return (
    <Panel title="Market Basis" icon="basis">
      <dl className="grid grid-cols-2 gap-x-5 gap-y-2 text-xs">
        <StatusRow label="xStock Move" value={pct(result.observed_token_move_pct)} icon="coin" />
        <StatusRow label="Model Move" value={pct(result.model_implied_move_pct)} icon="model" />
        <StatusRow label="Premium / Discount" value={pct(result.residual_premium_discount_pct)} icon="residual" />
        <StatusRow label={result.token_liquidity_usd == null ? "5m xStock Volume" : "Liquidity"} value={compactUsd(result.token_liquidity_usd ?? result.token_volume_usd)} icon="depth" />
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

function plainAction(action: PolicyAction | null): string {
  if (action === "ALLOW") return "Allow New Borrowing";
  if (action === "MONITOR") return "Continue Monitoring";
  if (action === "REQUIRE_REVIEW") return "Pause And Review";
  if (action === "RESTRICT_NEW_RISK") return "Restrict New Borrowing";
  return "No Policy Connected";
}
