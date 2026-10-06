const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
const { load } = require("./load-source.cjs");
const client = load("../src/api/client.ts");
const fixture = require("../src/fixtures/weekend_divergence.json");
const { filterOperationalResults, filterHistoricalResults, filterDemoResults, operationalCoverageNotice, OPERATIONAL_HISTORY_MAX } = load("../src/views/OperationalTimeline.tsx");
const { mergeObservations, rebasePosition } = load("../src/lib/playback.ts");
const { ReasonCodes } = load("../src/components/ReasonCodes.tsx");
const { RegistryPanel } = load("../src/components/RegistryPanel.tsx");
const { ReferenceComparison } = load("../src/views/ReferenceComparison.tsx");
const { ObservationAudit } = load("../src/components/ObservationAudit.tsx");
const { assetAvailabilityLabel, assetDisplayName } = load("../src/components/AssetPicker.tsx");
const { Hero } = load("../src/components/Hero.tsx");
const { LandingPage } = load("../src/components/LandingPage.tsx");
const { DocsPage } = load("../src/components/DocsPage.tsx");
const { MethodologyPage } = load("../src/components/MethodologyPage.tsx");
const { InstrumentPassport, passportStatusFor } = load("../src/components/InstrumentPassport.tsx");
const { PolicyFoundry } = load("../src/components/PolicyFoundry.tsx");
const { DEMO_PASSPORT_ADDRESS, MODEL_EVIDENCE_SUMMARY, POLICY_PROPOSAL } = load("../src/fixtures/prototypeData.ts");
const { default: App, consoleContextFromSearch } = load("../src/App.tsx");
const { deliveryStatusLabel, lastUpdatedLabel, pipelineStatusLabel } = load("../src/lib/format.ts");
const { chartDomain, clampViewport, lowerBoundTimestamp, minimumViewportWidth, panViewport, shouldRenderStateDots, sliceChartDataForViewport, upperBoundTimestamp, wheelGestureIntent, wheelZoomScale, zoomSensitivity, zoomViewport } = load("../src/components/EscalationChart.tsx");
const h = React.createElement;
const render = (component, props) => renderToStaticMarkup(h(component, props));

test("Demo returns only the six original backend observations, including original reasons", async () => {
  const original = global.fetch;
  const unusual = fixture.map(row => ({...row, evidence_state: "INCONCLUSIVE", reason_codes: ["CUSTOM_BACKEND_REASON"]}));
  try {
    global.fetch = async () => new Response(JSON.stringify(unusual));
    const response = await client.fetchDemoReplay();
    assert.equal(response.source, "backend-scenario");
    assert.equal(response.results.length, 6);
    assert.deepEqual(response.results, unusual);
    global.fetch = async () => { throw new Error("offline"); };
    const fallback = await client.fetchDemoReplay();
    assert.equal(fallback.source, "offline-fixture");
    assert.deepEqual(fallback.results, fixture);
  } finally { global.fetch = original; }
});

test("Historical rejects absent/wrong provenance and scenario backtest metrics", async () => {
  const original = global.fetch;
  try {
    for (const source of [null, "scenario"]) {
      global.fetch = async () => new Response(JSON.stringify(fixture), {headers: source ? {"X-Valtide-Source": source} : {}});
      await assert.rejects(client.fetchHistoricalReplay(), /Unexpected replay source/);
    }
    global.fetch = async () => new Response(JSON.stringify(fixture), {headers: {"X-Valtide-Source": "historical_panel"}});
    assert.deepEqual((await client.fetchHistoricalReplay()).results, fixture);
    global.fetch = async () => new Response(JSON.stringify({source:"scenario"}));
    await assert.rejects(client.fetchHistoricalBacktest(), /source could not be verified/);
    global.fetch = async () => new Response(JSON.stringify({asset:"NVDAx",source:"historical"}));
    assert.equal((await client.fetchHistoricalBacktest()).source, "historical");
  } finally { global.fetch = original; }
});

test("asset-aware request functions and query keys cannot reuse another asset", async () => {
  assert.notDeepEqual(
    client.assetQueryKeys.operational("NVDAx", "legacy_xperp_vs_p1ac"),
    client.assetQueryKeys.operational("SPYx", "xstock_vs_p1ac_challenger"),
  );
  assert.notDeepEqual(
    client.assetQueryKeys.history("NVDAx", 72, "legacy_xperp_vs_p1ac"),
    client.assetQueryKeys.history("SPYx", 72, "xstock_vs_p1ac_challenger"),
  );
  assert.deepEqual(client.assetQueryKeys.historical("NVDAx", "legacy_xperp_vs_p1ac"), [
    "replay", "NVDAx", "historical-panel", "legacy_xperp_vs_p1ac",
  ]);

  const original = global.fetch;
  let requestedUrl;
  try {
    global.fetch = async url => {
      requestedUrl = String(url);
      return new Response(JSON.stringify({...fixture[0], asset:"SPYx", reference_profile:"xstock_vs_p1ac_challenger"}));
    };
    assert.equal((await client.fetchOperationalValuation("SPYx")).asset, "SPYx");
    assert.match(requestedUrl, /\/api\/valuation\/SPYx$/);

    global.fetch = async () => new Response(JSON.stringify(fixture[0]));
    await assert.rejects(client.fetchOperationalValuation("SPYx"), /returned NVDAx for requested asset SPYx/);

    global.fetch = async () => new Response(JSON.stringify({asset:"NVDAx"}));
    await assert.rejects(client.fetchRuntime("SPYx"), /returned NVDAx runtime for SPYx/);
  } finally { global.fetch = original; }
});

test("legacy NVDAx responses are normalized only at the explicit migration boundary", async () => {
  const original = global.fetch;
  const legacyAsset = {
    asset:"NVDAx",token_source:"okx_onchainos",underlying_source:"alpaca",model_available:true,
  };
  try {
    global.fetch = async () => new Response(JSON.stringify([legacyAsset]));
    const assets = await client.fetchAssets();
    assert.equal(assets.length, 1);
    assert.equal(assets[0].asset, "NVDAx");
    assert.equal(assets[0].reference_profile, "legacy_xperp_vs_p1ac");
    assert.equal(assets[0].onchain_binding_configured, true);
    assert.deepEqual(assets[0].readiness_error_codes, []);

    global.fetch = async () => new Response(JSON.stringify({...fixture[0], reference_profile:undefined}));
    assert.equal((await client.fetchOperationalValuation()).reference_profile, "legacy_xperp_vs_p1ac");

    global.fetch = async () => new Response(JSON.stringify({configured:true}));
    assert.equal((await client.fetchOnchain()).asset, "NVDAx");
    await assert.rejects(client.fetchOnchain("SPYx"), /returned no asset control plane for SPYx/);

    global.fetch = async () => new Response(JSON.stringify([{
      asset:"SPYx",token_source:"okx_onchainos",underlying_source:"alpaca",model_available:false,
    }]));
    await assert.rejects(client.fetchAssets(), /omitted readiness identity for asset SPYx/);
  } finally { global.fetch = original; }
});

test("Operational windows use timestamps, exclude the boundary and preserve gaps", () => {
  const latest = Date.parse("2026-09-25T12:00:00Z");
  const row = hours => ({...fixture[0], timestamp:new Date(latest-hours*3600000).toISOString()});
  const rows = [row(168),row(167),row(24),row(23),row(6),row(5),row(1),row(0.5),row(0)];
  for (const [range, expected] of [["1H",2],["6H",4],["24H",6],["7D",8]]) {
    const selected = filterOperationalResults(rows,range);
    assert.equal(selected.length,expected);
    assert.ok(selected.every(record=>rows.includes(record)));
  }
});

test("Operational coverage explains when longer periods have no older records", () => {
  const latest = Date.parse("2026-10-06T09:00:00Z");
  const rows = Array.from({length: 12}, (_, index) => ({...fixture[0], timestamp:new Date(latest-(11-index)*300000).toISOString()}));
  assert.equal(operationalCoverageNotice(rows,"1H"), undefined);
  assert.match(operationalCoverageNotice(rows,"6H"), /no earlier observations are available/i);
  assert.equal(OPERATIONAL_HISTORY_MAX, 2016);
});

test("Asynchronous polling retains newest results and anchors replay by timestamp", () => {
  const rows = fixture.slice(0,3);
  assert.equal(mergeObservations(rows, fixture[3]).length,4);
  assert.equal(mergeObservations(rows,rows[1]).length,3);
  assert.equal(mergeObservations(fixture,rows[1]).at(-1),fixture.at(-1));
  assert.equal(rebasePosition(1.5,rows,fixture.slice(1)),0.5);
});

function appWith({result, rows, chain, error, assetList, profile = "legacy_xperp_vs_p1ac"} = {}) {
  const query = new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false}}});
  query.setQueryData(["health"],true);
  query.setQueryData(["assets"],assetList ?? [{
    asset:"NVDAx",token_source:"okx_onchainos",underlying_source:"alpaca",
    reference_profile:profile,registered:true,api_exposed:true,model_available:true,
    quant_artifact_ready:true,historical_data_available:true,live_data_configured:true,
    runtime_ready:true,operational_ready:true,operational_scheduler_enabled:true,
    latest_observation_timestamp:null,latest_observation_age_seconds:null,
    latest_observation_freshness:"unavailable",onchain_binding_configured:true,
    readiness_error_codes:[],
  }]);
  query.setQueryData(["demo-replay","NVDAx","canonical"],{results:fixture,source:"offline-fixture"});
  const operationalKey = client.assetQueryKeys.operational("NVDAx",profile);
  if (result) query.setQueryData(operationalKey,result);
  if (rows) query.setQueryData(client.assetQueryKeys.history("NVDAx",OPERATIONAL_HISTORY_MAX,profile),rows);
  if (chain) query.setQueryData(client.assetQueryKeys.onchain("NVDAx"),{asset:"NVDAx",...chain});
  if (error) query.getQueryCache().build(query,{queryKey:operationalKey}).setState({status:"error",error:new Error(error),fetchStatus:"idle"});
  const html = renderToStaticMarkup(h(QueryClientProvider,{client:query},h(App)));
  query.clear();
  return html;
}

test("Clean divergence hero restores the product framing and opens the validation console", () => {
  const html = render(Hero);
  assert.match(html, /Independent valuation evidence for tokenized collateral/);
  assert.match(html, /When markets disagree/);
  assert.match(html, /evidence supports/);
  assert.match(html, /Valtide protects DeFi from oracle failures/);
  assert.match(html, /independent, cryptographically verified collateral valuation/);
  assert.match(html, /Open validation console/);
  assert.match(html, /See how it works/);
  assert.match(html, /Animated market divergence/);
  assert.match(html, /Independent estimate/);
  assert.match(html, /Token market/);
  assert.doesNotMatch(html, /Run the risk demo|From evidence to protocol response|POSITION (?:OPENED|BLOCKED)/);
  assert.doesNotMatch(html, /RESTRICT_NEW_RISK|NEW EXPOSURE (?:OPEN|REVERTED)/);
  assert.match(html, /11,828/);
  assert.match(html, /94.3%/);
  assert.match(html, /19% tighter/);
  assert.match(html, /aria-describedby="historical-model-evidence-note"/);
  assert.match(html, /role="tooltip"/);
  assert.match(html, /Historical market observations tested/);
  assert.match(html, /Benchmark prices captured/);
  assert.match(html, /90% target/);
  assert.match(html, /Risk ranges vs\. a conventional Gaussian baseline/);
  assert.match(html, /Coverage above target is not automatically better/);
  assert.match(html, /Historical results are not production guarantees or comparisons with oracle providers/);
  assert.match(html, /href="\?view=console"/);
  assert.match(html, /href="\/methodology"/);
  assert.match(html, /href="\/docs"/);
  assert.match(html, /logo-motion-panel--left/);
  assert.match(html, /logo-motion-diamond/);
  assert.match(html, /logo-motion-panel--right/);
});

test("Prototype landing uses canonical demo values and preserves product boundaries", () => {
  const html = render(LandingPage);
  for (const value of ["$180.00", "$178.20", "$179.11"]) assert.match(html, new RegExp(value.replace("$", "\\$")));
  assert.match(html, /six-step synthetic incident/);
  assert.match(html, /demonstration data—not live or historical performance/);
  assert.match(html, /Valtide preserves the disagreement/);
  assert.match(html, /A reference separates from the market evidence/);
  assert.match(html, /Valtide says what the evidence supports/);
  assert.match(html, /CURATOR \/ PROTOCOL/);
  assert.match(html, /RESTRICT_NEW_RISK/);
  assert.match(html, /Every conclusion leaves a trail/);
  assert.match(html, /ValidationRegistry/);
  assert.match(html, /Evidence hash/);
  assert.match(html, /browser is read-only/);
  assert.match(html, /X Layer testnet/);
  assert.match(html, /does not custody assets, lend, trade, calculate LTV, or liquidate/);
  assert.match(html, /href="\/methodology"/);
  assert.doesNotMatch(html, /step-explorer|explorer-signal/);
  assert.doesNotMatch(html, /weekend_divergence|P1a-C|Standardized deviation/);
  assert.doesNotMatch(html, /Always-on assets need always-on evidence|Tokenization 2030|\$5\.5T|\$2\.6T/);
  for (const label of ["New to Valtide", "Curators and risk teams", "Developers and integrators", "Researchers"]) assert.match(html, new RegExp(label));
  assert.match(html, /\/docs\?profile=everyone#role-guide/);
  assert.match(html, /aria-label="Documentation by audience"/);
  assert.match(html, /role="tabpanel"/);
});

test("Landing model proof stays synchronized with the checked-in evaluation report", () => {
  const report = require("../../../valtide-quant-service-p1ac/evidence/p1a_c_report.json");
  const selected = report.test.find(row => row.candidate === "P1a-C:session_sym" && row.level === 0.9);
  assert.equal(MODEL_EVIDENCE_SUMMARY.observations, selected.n);
  assert.equal(MODEL_EVIDENCE_SUMMARY.coverage, selected.coverage);
  assert.equal(MODEL_EVIDENCE_SUMMARY.maeBps, selected.MAE_bps);
  assert.equal(MODEL_EVIDENCE_SUMMARY.meanIntervalWidthBps, selected.mean_width_bps);
  const gaussian = report.test.find(row => row.candidate === "P1a-Gaussian" && row.level === 0.9);
  assert.equal(MODEL_EVIDENCE_SUMMARY.gaussianMeanIntervalWidthBps, gaussian.mean_width_bps);
  assert.ok(Math.abs(MODEL_EVIDENCE_SUMMARY.intervalWidthReduction - (1 - selected.mean_width_bps / gaussian.mean_width_bps)) < 1e-12);
});

test("Documentation adapts by role and keeps evidence, policy and scope separate", () => {
  const html = render(DocsPage);
  for (const value of ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED", "Operational", "Historical", "Demo", "NVDAx / NVDA", "SPYx · not operationally onboarded"]) assert.match(html, new RegExp(value));
  assert.match(html, /Evidence describes\. Policy decides\./);
  assert.match(html, /A curator maps that state to a Policy Action/);
  assert.match(html, /complete guide below updates/);
  assert.match(html, /six synthetic observations/);
  assert.doesNotMatch(html, /Follow the interface|See what matters, in the order it matters|Every part of the walkthrough is visible/);
  assert.doesNotMatch(html, /THE BOUNDARY TO REMEMBER|The browser is a read-only observer/);
  assert.match(html, /context product interface example/);
  assert.match(html, /finding product interface example/);
  assert.match(html, /boundary product interface example/);
  assert.match(html, /not audited production lending infrastructure/);
  for (const label of ["New to Valtide", "Curators and risk teams", "Developers and integrators", "Researchers"]) assert.match(html, new RegExp(label));
  assert.match(html, /role="tablist"/);
  assert.match(html, /aria-selected="true"/);
  assert.match(html, /role="tabpanel"/);
  assert.match(html, /Open the demo result/);
  assert.match(html, /href="\/\?view=console&amp;context=demo"/);
  assert.match(html, /NVDAx uses the OKX X-Perp NVDA index/);
  assert.match(html, /Whether an attestation remains valid under both its valid-until time and the policy owner’s maximum age/);
  assert.match(html, /Structured backend explanations for an Evidence State, preserved by the frontend without recomputation/);
  for (const term of ["Evidence context", "Trusted anchor", "Market state"]) assert.match(html, new RegExp(term));
  assert.match(html, /Short examples show how each term appears/);
  assert.match(html, /Also useful for/);
  const profileSource = fs.readFileSync(path.join(__dirname, "../src/components/documentationProfiles.ts"), "utf8");
  for (const profile of ["everyone", "curators", "developers", "researchers"]) assert.match(profileSource, new RegExp(`${profile}:`));
  assert.match(fs.readFileSync(path.join(__dirname, "../src/components/DocsPage.tsx"), "utf8"), /cta: "Read the methodology", href: "\/methodology"/);
});

test("Methodology is a first-class, source-grounded page with one canonical method", () => {
  const html = render(MethodologyPage);
  for (const value of [
    "Public research methodology · v0.3",
    "A validation control—not a lending protocol",
    "One method, four lenses",
    "P1a-C is a causal state-space estimate",
    "SUPPORTED",
    "INCONCLUSIVE",
    "CHALLENGED",
    "11,828",
    "94.3%",
    "X Layer testnet",
  ]) assert.match(html, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(html, /interval quality—not production oracle accuracy/);
  assert.match(html, /xStock and P1a-C are model-based challenger evidence, not two independent observations/);
  assert.match(html, /does not observe an exact true price|does not observe an exact “true” price/);
  assert.match(html, /href="\/docs\?profile=developers#role-guide"/);
  assert.match(html, /docs\/METHODOLOGY\.md/);
});

test("Market Basis is visible without an advanced diagnostics disclosure", () => {
  const html = appWith({ result: fixture[0] });
  assert.match(html, /Market Basis/);
  assert.doesNotMatch(html, /Advanced market diagnostics/);
  const source = fs.readFileSync(path.join(__dirname, "../src/App.tsx"), "utf8");
  assert.doesNotMatch(source, /<summary[^>]*>Advanced market diagnostics<\/summary>/);
});

test("Console deep links select a known evidence context and fail closed to Operational", () => {
  assert.equal(consoleContextFromSearch("?view=console&context=demo"), "Demo");
  assert.equal(consoleContextFromSearch("?view=console&context=historical"), "Historical");
  assert.equal(consoleContextFromSearch("?view=console&context=DEMO"), "Demo");
  assert.equal(consoleContextFromSearch("?view=console"), "Operational");
  assert.equal(consoleContextFromSearch("?view=console&context=unknown"), "Operational");
});

test("Cold Operational stays unavailable even when Demo is cached", () => {
  const html = appWith({error:"503 data_unavailable"});
  assert.match(html,/Operational unavailable/);
  assert.doesNotMatch(html,/Demo Fixture · 6 Observations|Scenario policy|Example demo policy/);
});

test("Validation Console exposes the four catalog identities without implying readiness", () => {
  const base = {
    token_source:"okx_onchainos",underlying_source:"alpaca",registered:true,
    api_exposed:true,model_available:false,quant_artifact_ready:false,
    historical_data_available:false,live_data_configured:true,runtime_ready:false,
    operational_ready:false,operational_scheduler_enabled:false,
    latest_observation_timestamp:null,latest_observation_age_seconds:null,
    latest_observation_freshness:"unavailable",onchain_binding_configured:false,
    readiness_error_codes:["MODEL_FIT_BLOCKED"],
  };
  const catalog = [
    ["NVDAx","legacy_xperp_vs_p1ac"],
    ["SPYx","xstock_vs_p1ac_challenger"],
    ["QQQx","xstock_vs_p1ac_challenger"],
    ["AAPLx","xstock_vs_p1ac_challenger"],
  ].map(([asset,reference_profile]) => ({...base,asset,reference_profile}));
  const html = appWith({assetList:catalog});
  assert.match(html,/aria-haspopup="listbox"/);
  assert.match(html,/aria-label="Search assets"/);
  assert.match(html,/asset-picker__chevron/);
  assert.match(html,/viewBox="0 0 16 16"/);
  assert.doesNotMatch(html,/⌄/);
  for (const asset of ["NVDAx","SPYx","QQQx","AAPLx"]) {
    assert.match(html,new RegExp(`>${asset}<`));
  }
  assert.match(html,/NVIDIA Tokenized Equity/);
  assert.match(html,/S&amp;P 500 Tokenized ETF/);
  assert.match(html,/Coming soon/);
  assert.match(html,/MODEL_FIT_BLOCKED/);
  assert.match(html,/No other asset/);
});

test("Asset picker derives readable names and honest availability labels", () => {
  assert.equal(assetDisplayName("NVDAx"), "NVIDIA Tokenized Equity");
  assert.equal(assetDisplayName("UNKNOWNx"), "Tokenized equity");
  assert.equal(assetAvailabilityLabel(true), "Available");
  assert.equal(assetAvailabilityLabel(false), "Coming soon");
  assert.equal(assetAvailabilityLabel(undefined), "Checking");
});

test("Operational failure preserves cached evidence with a degraded label", () => {
  const html = appWith({result:fixture[0],error:"offline"});
  assert.match(html,/Operational degraded/);
  assert.match(html,/180.00/);
  assert.doesNotMatch(html,/Demo Fixture · 6 Observations|Example demo policy/);
});

test("Prior evidence is not paired with current enforcement", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"RESTRICT_NEW_RISK",evidence_state:"CHALLENGED",exists:true,fresh:true,network:"Testnet",chain_id:1952,attestation:null};
  const html = appWith({result:fixture[1],rows:fixture.slice(0,2),chain});
  assert.match(html,/Prior evidence → current policy/);
  assert.match(html,/Current deployed state — not historical chain state/);
  assert.doesNotMatch(html,/Current RiskGuard ·/);
});

test("Current evidence mapping and stale RiskGuard enforcement remain separate", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"REQUIRE_REVIEW",evidence_state:"SUPPORTED",exists:true,fresh:false,network:"Testnet",chain_id:1952,attestation:{publishedAt:Math.floor(Date.now()/1000)-7200}};
  const html = appWith({result:fixture[0],chain});
  assert.match(html,/Current evidence → policy action/);
  assert.match(html,/Reason/);
  assert.match(html,/Evidence supports the reference/);
  assert.match(html,/RiskGuard data · Stale/);
  assert.match(html,/Last updated 2h ago/);
  assert.match(html,/Technical details/);
  assert.match(html,/Evidence state/);
  assert.match(html,/Mapped policy action/);
  assert.match(html,/RiskGuard state/);
  assert.match(html,/Current RiskGuard action/);
  assert.match(html,/ALLOW/);
  assert.match(html,/REQUIRE_REVIEW/);
  assert.doesNotMatch(html,/Raw policy value/);
});

test("RiskGuard recency uses its publication timestamp and omits unavailable values", () => {
  const now = Date.parse("2026-10-06T12:00:00Z");
  assert.equal(lastUpdatedLabel(now / 1000 - 30, now), "Last updated just now");
  assert.equal(lastUpdatedLabel(now / 1000 - 12 * 60, now), "Last updated 12m ago");
  assert.equal(lastUpdatedLabel(now / 1000 - 2 * 60 * 60, now), "Last updated 2h ago");
  assert.equal(lastUpdatedLabel(now / 1000 - 3 * 24 * 60 * 60, now), "Last updated 3d ago");
  assert.equal(lastUpdatedLabel(null, now), null);
  assert.equal(lastUpdatedLabel(0, now), null);
});

test("Null reference, all reasons and unavailable policy remain truthful", () => {
  const result = {...fixture[0],reference_under_test:null,standardized_deviation:null,reference_deviation_pct:null,evidence_state:"INCONCLUSIVE",reason_codes:["COMPARATOR_UNAVAILABLE","TOKEN_DATA_UNAVAILABLE","CALIBRATION_GLOBAL_FALLBACK","UNKNOWN_BACKEND_REASON"]};
  const html = appWith({result});
  assert.doesNotMatch(html,/NaN|challenge threshold not met|Example demo policy/);
  for (const code of result.reason_codes) assert.ok(html.includes(code));
  assert.match(html,/UNAVAILABLE/);
  assert.match(render(ReasonCodes,{codes:result.reason_codes,evidenceState:result.evidence_state}),/Global fallback calibration/);
});

test("xStock comparison is labelled model-based evidence, not independent observations", () => {
  const xstock = render(ReferenceComparison, {
    r: {...fixture[0], reference_profile:"xstock_vs_p1ac_challenger"},
  });
  assert.match(xstock, /Model-based challenger evidence/);
  assert.match(xstock, /P1a assimilates this same xStock observation/);
  assert.match(xstock, /not two fully independent observations/);

  const legacy = render(ReferenceComparison, {
    r: {...fixture[0], reference_profile:"legacy_xperp_vs_p1ac"},
  });
  assert.match(legacy, /separate OKX X-Perp index/);
  assert.doesNotMatch(legacy, /xStock observation/);
});

test("Decision summary explains xStock dependence while retaining the legacy profile", () => {
  const xstock = appWith({
    result: {...fixture[0], reference_profile:"xstock_vs_p1ac_challenger"},
    profile:"xstock_vs_p1ac_challenger",
  });
  assert.match(xstock, /Model-based challenger evidence supports the observed xStock price/);
  assert.match(xstock, /not two fully independent observations/);
  assert.match(xstock, /Current finding/);
  assert.doesNotMatch(xstock, /Current finding · Operational/);

  const legacy = appWith({result: {...fixture[0], reference_profile:"legacy_xperp_vs_p1ac"}});
  assert.match(legacy, /Available independent evidence/);
});

test("Observation and delivery audit survives unavailable X Layer reads", () => {
  const runtime = {scheduler_enabled:true,last_tick_status:"failure",last_tick_attempt_at:"2026-09-25T10:01:00Z",last_error:"source missing",auto_publish_enabled:true,last_publish_status:"failed",last_publish_attempt_at:"2026-09-25T10:02:00Z",last_publish_observation_ts:"2026-09-25T09:55:00Z",last_published_observation_ts:"2026-09-25T09:50:00Z",last_published_at:1790325969,last_publish_tx_hash:"0xFULL_TRANSACTION_HASH",last_publish_error:"delivery failed"};
  const audit = render(ObservationAudit,{result:fixture[0],context:"Operational",runtime});
  for (const label of ["5-minute operational observation", "Reference source lag", "Trusted-anchor age", "Source provenance", "Model and version", "Last attempt"]) assert.ok(audit.includes(label));
  assert.match(audit,/source missing/);
  const chain = render(RegistryPanel,{isError:true,mode:"historical",runtime});
  assert.doesNotMatch(chain,/DEMO MAPPING/);
  for (const value of [runtime.last_publish_attempt_at,runtime.last_published_observation_ts,runtime.last_publish_tx_hash,runtime.last_publish_error]) assert.ok(chain.includes(value));
});

test("Historical ranges use timestamps and Demo ranges never add observations", () => {
  assert.equal(filterHistoricalResults(fixture, "ALL").length, 6);
  const historicalRows = [...fixture, { ...fixture[0], timestamp: "2026-09-10T14:00:00Z" }];
  assert.equal(filterHistoricalResults(historicalRows, "7D").length, 6);
  assert.equal(filterDemoResults(fixture, "FULL").length, 6);
  assert.equal(filterDemoResults(fixture, "15M").length, 3);
  assert.ok(filterDemoResults(fixture, "10M").every((row) => fixture.includes(row)));
});

test("Instrument Passport validates addresses and resolves only the labelled fixture", () => {
  assert.equal(passportStatusFor(""), "idle");
  assert.equal(passportStatusFor("0xnot-an-address"), "invalid");
  assert.equal(passportStatusFor("0x2222222222222222222222222222222222222222"), "unknown");
  assert.equal(passportStatusFor(DEMO_PASSPORT_ADDRESS), "resolved");
  const invalid = render(InstrumentPassport, { initialAddress: "0xnot-an-address" });
  assert.match(invalid, /exactly 40 hexadecimal characters/);
  const unknown = render(InstrumentPassport, { initialAddress: "0x2222222222222222222222222222222222222222" });
  assert.match(unknown, /No verified passport fixture/);
  assert.doesNotMatch(unknown, /SHAREHOLDER RIGHTS/);
  const resolved = render(InstrumentPassport, { initialAddress: DEMO_PASSPORT_ADDRESS });
  for (const value of ["Price exposure", "VERIFIED", "FIXTURE ASSERTION", "Shareholder rights", "NONE", "BALANCE ADJUSTMENT", "xSTOCKS WITHDRAWAL", "Rights profile", "differs from a share"]) assert.match(resolved, new RegExp(value, "i"));
  assert.match(resolved, /not live address resolution/i);
  assert.match(resolved, /type="submit"/);
});

test("Policy Foundry renders a deterministic diff and read-only approval boundary", () => {
  const html = render(PolicyFoundry);
  for (const value of ["Precomputed policy proposal", "not generated live", "900s", "600s", "REQUIRE_REVIEW", "MONITOR", "RESTRICT_NEW_RISK", "Unsigned calldata", "No transaction capability in this prototype"]) assert.match(html, new RegExp(value, "i"));
  assert.doesNotMatch(html, /Agent Council|ABI SHAPE VERIFIED|Human Approval Required/);
  assert.match(html, /Not deployed/i);
  assert.match(POLICY_PROPOSAL.calldata, /^0xf5b39423[0-9a-f]{320}$/);
});

test("Machine publication statuses use the requested display casing", () => {
  assert.equal(pipelineStatusLabel("published"), "PUBLISHED");
  assert.equal(deliveryStatusLabel("published"), "Published");
  assert.equal(deliveryStatusLabel("failed"), "Failed");
});

test("Historical observation audit is labelled as historical evidence", () => {
  const audit = render(ObservationAudit, { result: fixture[0], context: "Historical" });
  assert.match(audit, /Historical observation/);
  assert.doesNotMatch(audit, /5-minute operational observation/);
});

test("Chart viewport zooms around an anchor and pans within the full domain", () => {
  const timestamps = [0, 300_000, 600_000, 900_000, 1_200_000, 1_500_000];
  const full = chartDomain(timestamps);
  const minimum = minimumViewportWidth(timestamps);
  const zoomed = zoomViewport(full, full, 750_000, 0.5, minimum);
  assert.ok(zoomed[1] - zoomed[0] < full[1] - full[0]);
  assert.equal((zoomed[0] + zoomed[1]) / 2, 750_000);
  const offCenterZoom = zoomViewport(full, full, 300_000, 0.5, minimum);
  assert.ok(Math.abs((300_000 - offCenterZoom[0]) / (offCenterZoom[1] - offCenterZoom[0]) - 0.2) < 1e-9);
  assert.equal(zoomViewport(zoomed, full, 750_000, 4, minimum).join(), full.join());

  const panned = panViewport(zoomed, full, 500_000, minimum);
  assert.equal(panned[1] - panned[0], zoomed[1] - zoomed[0]);
  assert.ok(panned[0] >= full[0] && panned[1] <= full[1]);
  assert.deepEqual(panViewport(zoomed, full, -10_000_000, minimum), [full[0], full[0] + (zoomed[1] - zoomed[0])]);
  assert.deepEqual(clampViewport(full, full, minimum), full);
});

test("Chart wheel zoom is smooth and bounded", () => {
  const fullWidth = 7 * 24 * 60 * 60 * 1000;
  const wide = wheelZoomScale(-12, 0, fullWidth, fullWidth);
  const narrow = wheelZoomScale(-12, 0, 60 * 60 * 1000, fullWidth);
  assert.ok(wide < 1);
  assert.ok(narrow < 1);
  assert.ok(Math.abs(Math.log(wide)) > Math.abs(Math.log(narrow)));
  assert.ok(wheelZoomScale(12, 0, fullWidth, fullWidth) > 1);
  assert.ok(wheelZoomScale(-100_000, 0, fullWidth, fullWidth) >= Math.exp(-1.68));
  assert.ok(wheelZoomScale(100_000, 0, fullWidth, fullWidth) <= Math.exp(1.68));
  assert.ok(zoomSensitivity(60 * 60 * 1000, fullWidth) < zoomSensitivity(fullWidth, fullWidth));
});

test("Chart wheel intent batches dominant axes without changing semantic data", () => {
  assert.equal(wheelGestureIntent(2, 12), "zoom");
  assert.equal(wheelGestureIntent(18, 4), "pan");
  const source = fs.readFileSync(path.join(__dirname, "../src/components/EscalationChart.tsx"), "utf8");
  assert.match(source, /requestAnimationFrame\(flushWheelInput\)/);
  assert.match(source, /cancelAnimationFrame\(wheelFrameRef\.current\)/);
});

test("Chart renders only the viewport plus continuity boundaries", () => {
  const point = (sourceIndex, ts) => ({ sourceIndex, ts, band: [1, 2], fair: 1.5, rut: 1.6, token: 1.4, state: "SUPPORTED" });
  const points = [
    point(0, 0),
    point(1, 300_000),
    point(null, 450_000),
    point(2, 600_000),
    point(3, 900_000),
    point(4, 1_200_000),
  ];
  assert.equal(lowerBoundTimestamp(points, 500_000), 3);
  assert.equal(upperBoundTimestamp(points, 850_000), 4);
  const sliced = sliceChartDataForViewport(points, [500_000, 850_000]);
  assert.deepEqual(sliced.map(({ sourceIndex }) => sourceIndex), [null, 2, 3]);
  assert.deepEqual(sliceChartDataForViewport(points, [0, 1_200_000]), points);
  assert.deepEqual(sliceChartDataForViewport(points, [-100, 100]), [points[0], points[1]]);
  assert.deepEqual(sliceChartDataForViewport(points, [1_100_000, 1_300_000]), [points[4], points[5]]);
  const densePoints = Array.from({ length: 2_017 }, (_, index) => point(index, index * 300_000));
  const denseWindow = sliceChartDataForViewport(densePoints, [1_000 * 300_000, 1_011 * 300_000]);
  assert.equal(denseWindow.length, 14);
  assert.equal(denseWindow[0].sourceIndex, 999);
  assert.equal(denseWindow.at(-1).sourceIndex, 1_012);
  assert.match(fs.readFileSync(path.join(__dirname, "../src/components/EscalationChart.tsx"), "utf8"), /<ComposedChart\s+data=\{renderData\}/);
});

test("Dense evidence markers are a rendering-only level of detail", () => {
  assert.equal(shouldRenderStateDots(4, 400), true);
  assert.equal(shouldRenderStateDots(100, 400), false);
  assert.equal(shouldRenderStateDots(2_017, 1_000), false);
  assert.equal(shouldRenderStateDots(1, 0), true);
});

test("Pointer drag uses one animation-frame update per pending gesture", () => {
  const source = fs.readFileSync(path.join(__dirname, "../src/components/EscalationChart.tsx"), "utf8");
  assert.match(source, /requestAnimationFrame\(\(\) => \{[\s\S]*flushDragViewport\(\)/);
  assert.match(source, /cancelAnimationFrame\(dragFrameRef\.current\)/);
  assert.match(source, /data=\{renderData\}/);
});

test("Rendered chart clips both axes to the computed viewport", () => {
  const source = fs.readFileSync(path.join(__dirname, "../src/components/EscalationChart.tsx"), "utf8");
  assert.match(source, /<XAxis[^>]*domain=\{viewportDomain\}[^>]*allowDataOverflow/);
  assert.match(source, /<YAxis[^>]*domain=\{\[min - pad, max \+ pad\]\}[^>]*allowDataOverflow/);
  assert.match(source, /addEventListener\("wheel", handleWheel, \{ passive: false \}\)/);
});
