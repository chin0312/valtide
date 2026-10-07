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
const consoleV2Fixture = require("../src/fixtures/console_weekend_divergence_v2.json");
const { filterOperationalResults, filterHistoricalResults, filterDemoResults, operationalCoverageNotice, OPERATIONAL_HISTORY_MAX } = load("../src/views/OperationalTimeline.tsx");
const { mergeObservations, rebasePosition } = load("../src/lib/playback.ts");
const { ReasonCodes } = load("../src/components/ReasonCodes.tsx");
const { RegistryPanel } = load("../src/components/RegistryPanel.tsx");
const { ReferenceComparison } = load("../src/views/ReferenceComparison.tsx");
const { ModelEvidence } = load("../src/views/ModelEvidence.tsx");
const { ReferenceNumberLine } = load("../src/components/ReferenceNumberLine.tsx");
const { ObservationAudit } = load("../src/components/ObservationAudit.tsx");
const { assetAvailabilityLabel, assetDisplayName } = load("../src/components/AssetPicker.tsx");
const { ObservationRecord } = load("../src/views/ObservationRecord.tsx");
const { Hero } = load("../src/components/Hero.tsx");
const { LandingPage } = load("../src/components/LandingPage.tsx");
const { DocsPage } = load("../src/components/DocsPage.tsx");
const { MethodologyPage } = load("../src/components/MethodologyPage.tsx");
const { InstrumentPassport, passportStatusFor } = load("../src/components/InstrumentPassport.tsx");
const { PolicyFoundry } = load("../src/components/PolicyFoundry.tsx");
const { DEMO_PASSPORT_ADDRESS, MODEL_EVIDENCE_SUMMARY, POLICY_PROPOSAL } = load("../src/fixtures/prototypeData.ts");
const { default: App, consoleContextFromSearch, effectiveContextAsset } = load("../src/App.tsx");
const { coverageLabel, dateTimeUTC, deliveryStatusLabel, lastUpdatedLabel, modelDisplayName, pipelineStatusLabel, sessionLabel } = load("../src/lib/format.ts");
const { AXIS_MIN, AXIS_MAX, priceToFraction, toBandUnits, unitsToFraction } = load("../src/lib/scale.ts");
const { modelDistanceLabel, peakModelDistance, evidenceCopy, EVIDENCE_SEMANTICS_V2 } = load("../src/lib/semantics.ts");
const { buildChartData, chartDomain, chartIntervalLabel, clampViewport, lowerBoundTimestamp, minimumViewportWidth, panViewport, shouldRenderStateDots, sliceChartDataForViewport, upperBoundTimestamp, VALUATION_CHART_LABELS, wheelGestureIntent, wheelZoomScale, zoomSensitivity, zoomViewport } = load("../src/components/EscalationChart.tsx");
const h = React.createElement;
const render = (component, props) => renderToStaticMarkup(h(component, props));

test("Console Demo accepts only the six-row v2 scenario and uses its independent v2 backup", async () => {
  for (const row of fixture) {
    assert.equal(row.reference_profile, "unified_xstock_p1ac_xperp_evidence_v1");
    assert.equal(row.validation_target, "xstock_observed_price");
    assert.equal(row.evidence_semantics, "p1a_xstock_band_with_xperp_review_corroboration_v2");
    assert.equal(row.xperp_role, "second_market_challenger");
    assert.ok(row.challenger_detector);
  }
  const original = global.fetch;
  const unusual = consoleV2Fixture.map(row => ({...row, reason_codes: ["CUSTOM_BACKEND_REASON"]}));
  assert.deepEqual(consoleV2Fixture.map(row => row.evidence_state), [
    "SUPPORTED", "SUPPORTED", "SUPPORTED", "INCONCLUSIVE", "CHALLENGED", "CHALLENGED",
  ]);
  assert.ok(consoleV2Fixture.every(row => row.asset === "NVDAx"
    && row.reference_profile === "unified_xstock_p1ac_xperp_evidence_v1"
    && row.evidence_semantics === EVIDENCE_SEMANTICS_V2
    && row.validation_target === "xstock_observed_price"
    && row.xperp_role === "second_market_challenger"));
  try {
    global.fetch = async () => new Response(JSON.stringify(unusual));
    const response = await client.fetchDemoReplay();
    assert.equal(response.source, "backend-scenario");
    assert.equal(response.results.length, 6);
    assert.deepEqual(response.results, unusual);
    global.fetch = async () => { throw new Error("offline"); };
    const fallback = await client.fetchDemoReplay();
    assert.equal(fallback.source, "console-backup");
    assert.deepEqual(fallback.results, consoleV2Fixture);
    assert.ok(fallback.results.every(row => row.evidence_semantics === EVIDENCE_SEMANTICS_V2));
    await assert.rejects(client.fetchDemoReplay("SPYx"), /NVDAx-only/);
    assert.deepEqual(client.DEMO_REPLAY_QUERY_KEY, ["demo-replay", "NVDAx", "weekend_divergence", EVIDENCE_SEMANTICS_V2]);
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

test("explicit X Layer binding metadata enables all production assets and missing metadata fails closed", async () => {
  const original = global.fetch;
  const assets = ["NVDAx", "SPYx", "AAPLx"].map(asset => ({
    asset,token_source:"okx_onchainos",underlying_source:"alpaca",
    reference_profile:"unified_xstock_p1ac_xperp_evidence_v1",model_available:true,
    api_exposed:true,onchain_binding_configured:true,
  }));
  try {
    global.fetch = async () => new Response(JSON.stringify(assets));
    const normalized = await client.fetchAssets();
    assert.deepEqual(normalized.map(item => item.asset), ["NVDAx", "SPYx", "AAPLx"]);
    assert.ok(normalized.every(item => item.onchain_binding_configured));

    global.fetch = async () => new Response(JSON.stringify(assets.map(({onchain_binding_configured, ...item}) => item)));
    const withoutBindingMetadata = await client.fetchAssets();
    assert.deepEqual(withoutBindingMetadata.map(item => item.onchain_binding_configured), [false, false, false]);
  } finally { global.fetch = original; }
});

test("onchain and enforcement requests are scoped to each explicitly bound asset", async () => {
  const original = global.fetch;
  const requested = [];
  try {
    global.fetch = async url => {
      const path = new URL(String(url)).pathname;
      requested.push(path);
      const asset = path.match(/\/api\/onchain\/(NVDAx|SPYx|AAPLx)(?:\/enforcement)?$/)?.[1];
      return new Response(JSON.stringify({asset}));
    };
    for (const asset of ["NVDAx", "SPYx", "AAPLx"]) {
      assert.equal((await client.fetchOnchain(asset)).asset, asset);
      assert.equal((await client.fetchOnchainEnforcement(asset)).asset, asset);
      assert.deepEqual(client.assetQueryKeys.onchain(asset), ["onchain", asset]);
      assert.deepEqual(client.assetQueryKeys.enforcement(asset), ["onchain", asset, "enforcement"]);
    }
    assert.deepEqual(requested, [
      "/api/onchain/NVDAx", "/api/onchain/NVDAx/enforcement",
      "/api/onchain/SPYx", "/api/onchain/SPYx/enforcement",
      "/api/onchain/AAPLx", "/api/onchain/AAPLx/enforcement",
    ]);
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
  query.setQueryData(client.DEMO_REPLAY_QUERY_KEY,{results:consoleV2Fixture,source:"console-backup"});
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
  assert.match(html, /Independent reference validation for tokenized equity/);
  assert.match(html, /Take control of your protocol&#x27;s/);
  assert.match(html, /collateral risk/);
  assert.match(html, /Compare the observed xStock price with Valtide Fair Value, a Valuation Range, and separately sourced X-Perp evidence/);
  assert.match(html, /Protocols retain control of the Policy Actions they apply/);
  assert.doesNotMatch(html, /cryptographically verified collateral valuation|enforce their own risk rules/);
  assert.match(html, /Open validation console/);
  assert.match(html, /See how it works/);
  assert.match(html, /Animated market divergence/);
  assert.match(html, /Valtide Fair Value/);
  assert.match(html, /Observed xStock/);
  assert.doesNotMatch(html, /Run the risk demo|From evidence to protocol response|POSITION (?:OPENED|BLOCKED)/);
  assert.doesNotMatch(html, /RESTRICT_NEW_RISK|NEW EXPOSURE (?:OPEN|REVERTED)/);
  assert.match(html, /11,828/);
  assert.match(html, /94.3%/);
  assert.match(html, /19% narrower/);
  assert.match(html, /aria-describedby="historical-model-evidence-note"/);
  assert.match(html, /role="tooltip"/);
  assert.match(html, /NVDAx · P1a-C v0\.2\.0 observations/);
  assert.match(html, /Empirical interval coverage/);
  assert.match(html, /90% target/);
  assert.match(html, /19% narrower/);
  assert.match(html, /Mean interval width · same point estimates/);
  assert.match(html, /This evaluates interval construction—not price accuracy versus raw xStock, three-asset performance, Evidence State accuracy, or production performance/);
  assert.match(html, /not an untouched test set/);
  assert.match(html, /href="\?view=console"/);
  assert.match(html, /href="\/methodology"/);
  assert.match(html, /href="\/docs"/);
  assert.match(html, /logo-motion-panel--left/);
  assert.match(html, /logo-motion-diamond/);
  assert.match(html, /logo-motion-panel--right/);
});

test("Prototype landing uses canonical demo values and preserves product boundaries", () => {
  const html = render(LandingPage);
  const landingSource = fs.readFileSync(path.join(__dirname, "../src/components/LandingPage.tsx"), "utf8");
  for (const value of ["$180.00", "$178.20", "$179.13"]) assert.match(html, new RegExp(value.replace("$", "\\$")));
  assert.match(html, /six-step synthetic incident/);
  assert.match(html, /demonstration data—not live evidence or historical performance/);
  assert.match(html, /Valtide preserves disagreement/);
  assert.match(html, /The Valtide Model uses Observed xStock as an input/);
  assert.match(html, /Underlying Anchor provides model context and is not a same-time Evidence State vote/);
  assert.match(html, /Low Model Disagreement/);
  assert.match(html, /Global Calibration Applied/);
  assert.match(landingSource, /import \{ reasonLabel \} from "\.\.\/lib\/format"/);
  assert.match(landingSource, /reasonLabel\(reason\)/);
  assert.doesNotMatch(landingSource, /const REASON_LABELS/);
  for (const heading of [
    "See a synthetic xStock price beside Valtide Fair Value",
    "Keep the price, estimate, and evidence distinct",
    "Calibrated ranges make uncertainty explicit",
    "Protocol-owned policy, evaluated on X Layer",
  ]) assert.match(html, new RegExp(heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(html, /RiskGuard evaluates the protocol’s configured mapping/);
  assert.match(html, /decides how—and whether—to enforce the returned action/);
  assert.match(html, /CURATOR \/ PROTOCOL/);
  assert.match(html, /RESTRICT_NEW_RISK/);
  assert.match(html, /Every conclusion leaves a trail/);
  assert.match(html, /ValidationRegistry/);
  assert.match(html, /Evidence hash/);
  assert.match(html, /browser is read-only/);
  assert.match(html, /A separate backend scheduler publishes authorized attestations/);
  assert.match(html, /X Layer testnet/);
  assert.match(html, /For NVDAx, SPYx, and AAPLx, the machine interface can publish authorized attestations/);
  assert.match(html, /href="\/\?view=console&amp;context=demo"/);
  assert.match(html, /Inspect this synthetic incident in the Validation Console/);
  assert.match(html, /aria-label="Pause demo playback"/);
  assert.match(html, /Playing the six observations · approximately 1 second per observation/);
  assert.doesNotMatch(html, /verified contract|RiskGuard enforces/i);
  assert.match(html, /does not custody assets, lend, trade, calculate LTV, or liquidate/);
  assert.match(html, /href="\/methodology"/);
  assert.doesNotMatch(html, /step-explorer|explorer-signal/);
  assert.doesNotMatch(html, /weekend_divergence|Standardized deviation/);
  assert.doesNotMatch(html, /Always-on assets need always-on evidence|Tokenization 2030|\$5\.5T|\$2\.6T/);
  for (const label of ["New to Valtide", "Curators and risk teams", "Developers and integrators", "Researchers"]) assert.match(html, new RegExp(label));
  assert.match(html, /\/docs\?profile=everyone#role-guide/);
  assert.match(html, /aria-label="Documentation by audience"/);
  assert.match(html, /role="tabpanel"/);

  assert.match(landingSource, /setInterval\([^]*1000\)/);
  assert.match(landingSource, /prefers-reduced-motion: reduce/);
  assert.match(landingSource, /onFocusCapture=\{\(\) => pauseDemo\("focus"\)\}/);
  assert.match(landingSource, /pauseDemo\("manual"\)/);
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
  for (const value of ["SUPPORTED", "INCONCLUSIVE", "CHALLENGED", "Operational", "Historical", "Demo", "NVDAx / NVDA", "SPYx / SPY", "AAPLx / AAPL", "QQQx retains offline quant"]) assert.match(html, new RegExp(value));
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
  assert.match(html, /Observed xStock/);
  assert.match(html, /tokenized-equity market price being reviewed/);
  assert.match(html, /Public asset selector/);
  assert.match(html, /not exposed through the public HTTP API/);
  assert.doesNotMatch(html, /production unified profile|Production asset selector|production HTTP/);
  assert.match(html, /High Model Disagreement/);
  assert.match(html, /X-Perp Supports Model Challenge/);
  assert.match(html, /Whether an attestation remains valid under both its valid-until time and the policy owner’s maximum age/);
  assert.match(html, /Structured backend explanations for an Evidence State, preserved by the frontend without recomputation/);
  for (const term of ["Evidence context", "Trusted anchor", "Market state"]) assert.match(html, new RegExp(term));
  assert.match(html, /Short examples show how each term appears/);
  assert.match(html, /Also useful for/);
  const profileSource = fs.readFileSync(path.join(__dirname, "../src/components/documentationProfiles.ts"), "utf8");
  const docsSource = fs.readFileSync(path.join(__dirname, "../src/components/DocsPage.tsx"), "utf8");
  assert.match(docsSource, /exposed interval contains 11,828 observations/);
  assert.match(docsSource, /no longer an untouched test set/);
  for (const profile of ["everyone", "curators", "developers", "researchers"]) assert.match(profileSource, new RegExp(`${profile}:`));
  assert.match(fs.readFileSync(path.join(__dirname, "../src/components/DocsPage.tsx"), "utf8"), /cta: "Read the methodology", href: "\/methodology"/);
});

test("Current public X Layer scope names all three bound assets without implying backend publication is browser-driven", () => {
  const landing = render(LandingPage);
  const docs = render(DocsPage);
  const methodology = render(MethodologyPage);
  const docsSource = fs.readFileSync(path.join(__dirname,"../src/components/DocsPage.tsx"),"utf8");
  assert.match(landing,/For NVDAx, SPYx, and AAPLx, the machine interface can publish authorized attestations to the deployed X Layer testnet control plane/);
  assert.match(docsSource,/shared ValidationRegistry and RiskGuard are deployed on X Layer testnet with asset-specific bindings for NVDAx, SPYx, and AAPLx/);
  assert.match(docs,/NVDAx · SPYx · AAPLx · X Layer testnet/);
  for (const html of [landing, docs, methodology]) {
    assert.match(html,/NVDAx · SPYx · AAPLx/);
    assert.doesNotMatch(html,/NVDAx only|Only NVDAx has an X Layer binding/i);
  }
  assert.match(landing,/browser is read-only:[\s\S]*?sign, or submit transactions/);
});

test("Public repository docs match the three-asset backend and current unified profile", () => {
  const repoRoot = path.join(__dirname, "../../..");
  const sources = [
    "apps/api/README.md",
    "docs/ASSET_INTEGRATION_FOUNDATION.md",
    "docs/BACKEND_ARCHITECTURE.md",
    "docs/METHODOLOGY.md",
  ].map((filename) => fs.readFileSync(path.join(repoRoot, filename), "utf8"));
  const combined = sources.join("\n");
  for (const asset of ["NVDAx", "SPYx", "AAPLx"]) assert.match(combined, new RegExp(asset));
  assert.match(combined, /All three have asset-specific publication bindings|three public assets have complete runtime, historical, and X Layer bindings/);
  assert.match(combined, /current unified profile/);
  assert.doesNotMatch(combined, /Only NVDAx(?: currently)? has an X Layer binding|current production profile|Current four-asset blocker|Production asset selector/);
});

test("Methodology is a first-class, source-grounded page with one canonical method", () => {
  const html = render(MethodologyPage);
  for (const value of [
    "Public research methodology · v0.3",
    "A validation control—not a lending protocol",
    "One method, four lenses",
    "The Valtide Model estimates Fair Value with calibrated uncertainty",
    "SUPPORTED",
    "INCONCLUSIVE",
    "CHALLENGED",
    "11,828",
    "94.3%",
    "NVDAx v0.2.0",
    "X Layer testnet",
  ]) assert.match(html, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.match(html, /Interval quality—not production oracle accuracy/);
  assert.match(html, /current unified profile/i);
  assert.doesNotMatch(html, /current production profile/i);
  assert.match(html, /Disagreements are preserved, not averaged away/);
  assert.match(html, /X-Perp is the separate market comparison/);
  assert.match(html, /<details class="methodology-equations">/);
  assert.match(html, /View the P1a-C equations/);
  assert.match(html, /aria-label="Current unified Evidence State rules"/);
  assert.match(html, /Model Distance is within the asset’s supported range/);
  assert.match(html, /Required evidence is missing, stale, ambiguous, or below quality requirements/);
  assert.match(html, /exact-time X-Perp is closer to Valtide Fair Value than to Observed xStock/);
  assert.match(html, /An asset-bound capability authorizes which Evidence States/);
  assert.match(html, /View these states in the Validation Console/);
  assert.match(html, /NVDAx P1a-C v0\.2\.0 produced intervals 19% narrower than the conventional Gaussian baseline while achieving 94\.3% empirical coverage against a 90% target/);
  assert.doesNotMatch(html, /narrower interval reduces false-positive alerts|preventing unnecessary trading restrictions/i);
  assert.match(html, /NVDAx, SPYx, and AAPLx have asset-specific publication bindings/);
  assert.match(html, /The backend scheduler publishes authorized attestations; the browser is read-only/);
  assert.match(html, /X Layer records evidence and evaluates policy—it does not calculate Fair Value/);
  assert.doesNotMatch(html, /unified-v2 results are not published through the legacy binding/);
  assert.match(html, /Explore the current X Layer testnet integration/);
  assert.match(html, /correctness still depends on the underlying sources, model, and validation rule/);
  assert.match(html, /does not observe an exact true price|does not observe an exact “true” price/);
  assert.match(html, /href="\/docs\?profile=developers#role-guide"/);
  assert.match(html, /href="\/\?view=console&amp;context=demo"/);
  assert.match(html, /docs\/METHODOLOGY\.md/);
  for (const path of [
    "docs/METHODOLOGY.md",
    "valtide-quant-service-p1ac/evidence",
    "valtide-quant-service-p1ac/artifacts",
  ]) assert.match(html, new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});

test("Vercel serves first-class documentation routes through the SPA entry point", () => {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "../vercel.json"), "utf8"));
  const rewrites = new Map(config.rewrites.map(({ source, destination }) => [source, destination]));
  for (const route of ["/docs", "/docs/:path*", "/methodology", "/methodology/:path*"]) {
    assert.equal(rewrites.get(route), "/index.html");
  }
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

test("Demo uses canonical NVDAx data, hides selection, and preserves each operational asset selection", () => {
  for (const selectedAsset of ["SPYx", "AAPLx", "NVDAx"]) {
    assert.equal(effectiveContextAsset("Demo", selectedAsset), "NVDAx");
    assert.equal(effectiveContextAsset("Operational", selectedAsset), selectedAsset);
    assert.equal(effectiveContextAsset("Historical", selectedAsset), selectedAsset);
  }

  const originalWindow = global.window;
  global.window = { location: { search: "?view=console&context=demo", pathname: "/" } };
  try {
    const html = appWith({});
    assert.doesNotMatch(html, /asset-picker/);
    assert.match(html, /NVDAx Validation Timeline/);
    assert.match(html, /Demo Backup · 6 Synthetic Steps/);
    assert.match(html, /Demo policy/);
    assert.match(html, /Policy Proposal/);
    assert.equal((html.match(/Advanced: Policy Proposal/g) ?? []).length,1);
    assert.doesNotMatch(html, /Evidence State v2|X Layer Not Configured/);
    assert.doesNotMatch(html, /Research prototype|No transaction capability in this prototype|Demo fixture|backend|fixture/i);
  } finally {
    if (originalWindow === undefined) delete global.window;
    else global.window = originalWindow;
  }
});

test("Advanced Policy Proposal is one Demo-only full-width row after the primary grid", () => {
  const appSource = fs.readFileSync(path.join(__dirname,"../src/App.tsx"),"utf8");
  assert.equal((appSource.match(/Advanced: Policy Proposal/g) ?? []).length,1);
  assert.match(appSource,/<div className="grid items-stretch gap-4 xl:grid-cols-\[minmax\(0,1\.3fr\)_minmax\(0,1fr\)\]">[\s\S]*?<ReferenceComparison r=\{current\} \/>[\s\S]*?<PolicyCard[\s\S]*?<\/div>\s*<\/div>\s*\{context === "Demo" && <details[\s\S]*?Advanced: Policy Proposal[\s\S]*?<PolicyFoundry \/>[\s\S]*?<\/details>\}\s*<div className="grid gap-4 md:grid-cols-2">/);
  assert.doesNotMatch(appSource,/asset\s*===\s*["'](?:NVDAx|SPYx|AAPLx)["']/);
  assert.match(appSource,/assetQueryKeys\.onchain\(contextAsset\), queryFn: \(\) => fetchOnchain\(contextAsset\)[\s\S]*?enabled: backendUp && !!selectedAssetInfo\?\.onchain_binding_configured/);
  assert.match(appSource,/assetQueryKeys\.enforcement\(contextAsset\), queryFn: \(\) => fetchOnchainEnforcement\(contextAsset\)[\s\S]*?enabled: backendUp && !!selectedAssetInfo\?\.onchain_binding_configured/);

  const originalWindow = global.window;
  try {
    global.window = {location:{search:"?view=console&context=operational",pathname:"/"}};
    const operational = appWith({result:fixture[0]});
    assert.doesNotMatch(operational,/Advanced: Policy Proposal/);
    global.window = {location:{search:"?view=console&context=historical",pathname:"/"}};
    const historical = appWith({result:fixture[0]});
    assert.doesNotMatch(historical,/Advanced: Policy Proposal/);
    global.window = {location:{search:"?view=console&context=demo",pathname:"/"}};
    const demo = appWith({});
    assert.equal((demo.match(/Advanced: Policy Proposal/g) ?? []).length,1);
  } finally {
    if (originalWindow === undefined) delete global.window;
    else global.window = originalWindow;
  }
});

test("Detector score formatting preserves units and refuses mixed-unit peaks", () => {
  assert.equal(modelDistanceLabel("disagreement_z", 0.84), "0.8σ");
  assert.equal(modelDistanceLabel("disagreement_bps", 37.24), "37.2 bps");
  assert.equal(modelDistanceLabel("disagreement_bps", 21.06), "21.1 bps");
  assert.equal(modelDistanceLabel("innovation_abs_z", 1.2), "—");
  assert.equal(modelDistanceLabel("disagreement_z", null), "—");
  assert.equal(modelDistanceLabel("disagreement_z", consoleV2Fixture[0].standardized_deviation), "—");
  assert.equal(peakModelDistance(consoleV2Fixture), "4.2σ");
  assert.equal(peakModelDistance([
    consoleV2Fixture[0],
    {...consoleV2Fixture[1], challenger_detector: {...consoleV2Fixture[1].challenger_detector, score_name:"disagreement_bps"}},
  ]), "—");
  assert.equal(peakModelDistance([{...consoleV2Fixture[0], challenger_detector:null}]), "—");
  assert.equal(peakModelDistance([
    {...consoleV2Fixture[0], standardized_deviation:null, challenger_detector:{score_name:"disagreement_bps",score:21.06}},
    {...consoleV2Fixture[1], standardized_deviation:null, challenger_detector:{score_name:"disagreement_bps",score:37.24}},
  ]), "37.2 bps");
});

test("Console Model Distance reads the backend detector score rather than standardized deviation", () => {
  const cases = [
    ["NVDAx", "disagreement_z", 0.84, "0.8σ"],
    ["SPYx", "disagreement_bps", 37.24, "37.2 bps"],
    ["AAPLx", "disagreement_bps", 21.06, "21.1 bps"],
  ];
  for (const [asset, scoreName, score, expected] of cases) {
    const result = {
      ...consoleV2Fixture[0],asset,standardized_deviation:null,
      challenger_detector:{...consoleV2Fixture[0].challenger_detector,score_name:scoreName,score},
    };
    const html = appWith({result,profile:result.reference_profile});
    assert.ok(html.includes(expected), `${asset} should show ${expected}`);
  }
});

test("Peak Model Distance uses the largest compatible detector score and keeps the asset unit", () => {
  const rows = [21.06, 37.24, 12].map((score, index) => ({
    ...consoleV2Fixture[index],standardized_deviation:null,
    challenger_detector:{...consoleV2Fixture[index].challenger_detector,score_name:"disagreement_bps",score},
  }));
  const html = render(ObservationRecord,{results:rows,currentIndex:2,sourceLabelText:"Historical"});
  assert.match(html,/Peak Model Distance[\s\S]*?37\.2 bps/);
});

test("Console metrics and interval markers use human-facing model labels and xStock/X-Perp v2 fields", () => {
  const v2 = consoleV2Fixture[4];
  const html = appWith({result:v2, profile:v2.reference_profile});
  for (const label of ["Observed xStock", "Valtide Fair Value", "X-Perp", "xStock Vs Model", "Model Distance", "Underlying Anchor"]) assert.match(html, new RegExp(label));
  assert.match(html, /2\.9σ/);
  assert.match(html, /xStock ↔ Valtide Model/);
  assert.match(html, /Model Move/);
  assert.match(html, /Valtide Model · v0\.2\.0/);
  assert.match(html, /exact-time X-Perp is closer to P1a-C than to xStock/);
  assert.doesNotMatch(html, /Reference under test|Technical diagnostic/);
  const numberLine = render(ReferenceNumberLine,{r:v2});
  for (const marker of ["Observed xStock", "X-Perp", "Valtide Fair Value", "90% Valuation Range"]) assert.match(numberLine,new RegExp(marker));
  assert.doesNotMatch(numberLine,/Last Trusted Underlying|Underlying Anchor/);
  assert.equal((numberLine.match(/data-price-marker=/g) ?? []).length,3);
  for (const label of ["Observed xStock", "Valtide Fair Value", "X-Perp"]) assert.match(numberLine,new RegExp(`data-price-marker="${label}"`));
  const summary = numberLine.slice(numberLine.indexOf("grid-cols-3"));
  for (const [label,value] of [["Observed xStock",v2.token_price],["Valtide Fair Value",v2.valtide_fair_value],["X-Perp",v2.xperp_index_price]]) {
    assert.match(summary,new RegExp(`${label}[\\s\\S]*?\\$${value.toFixed(2)}`));
    assert.ok(numberLine.includes(`title="${label}: $${value.toFixed(2)}"`), `${label} marker should expose its bound price`);
  }
  assert.equal((summary.match(/class="min-w-0"/g) ?? []).length,3);
  const summaryRows = summary.split('<div class="min-w-0">').slice(1);
  assert.match(summaryRows[0],/background:var\(--color-series-token\);border-radius:50%[\s\S]*Observed xStock/);
  assert.match(summaryRows[1],/background:var\(--color-series-valtide\);border-radius:1px[\s\S]*Valtide Fair Value/);
  assert.match(summaryRows[2],/background:var\(--color-series-reference\);border-radius:1px;rotate:45deg[\s\S]*X-Perp/);
  assert.match(numberLine,/data-price-marker="Observed xStock"[^>]*>\s*<svg[\s\S]*?<circle/);
  assert.match(numberLine,/data-price-marker="Valtide Fair Value"[^>]*>\s*<svg[\s\S]*?<rect/);
  assert.match(numberLine,/data-price-marker="X-Perp"[^>]*>\s*<svg[\s\S]*?<path/);
  assert.match(numberLine,/aria-label="Observed xStock[\s\S]*Valtide Fair Value[\s\S]*X-Perp[\s\S]*90% Valuation Range/);
  assert.match(render(ReferenceNumberLine,{r:{...v2,interval_coverage_target:0.95}}),/95% Valuation Range/);
  assert.equal(coverageLabel(0.9),"90% Valuation Range");
  assert.equal(coverageLabel(0.95),"95% Valuation Range");
  assert.doesNotMatch(numberLine,/X-Perp \/ index|Calibrated Interval/);
  assert.doesNotMatch(numberLine,/Constructed/);
  const markerMarkup = (markup, label) => markup.match(new RegExp(`<div data-price-marker="${label}"[^>]*>[\\s\\S]*?<\\/div>`))?.[0] ?? "";
  const asymmetric = {...v2,token_price:179.5,valtide_fair_value:180,fair_value_lower:179,fair_value_upper:182,xperp_index_price:181};
  const asymmetricMarkup = render(ReferenceNumberLine,{r:asymmetric});
  const fairFraction = priceToFraction(asymmetric.valtide_fair_value,asymmetric);
  const lowerFraction = priceToFraction(asymmetric.fair_value_lower,asymmetric);
  const upperFraction = priceToFraction(asymmetric.fair_value_upper,asymmetric);
  assert.ok(lowerFraction < fairFraction && fairFraction < upperFraction);
  assert.notEqual(fairFraction,(lowerFraction+upperFraction)/2,"asymmetric intervals must preserve Fair Value's proportional position");
  for (const [label,price] of [["Observed xStock",asymmetric.token_price],["Valtide Fair Value",asymmetric.valtide_fair_value],["X-Perp",asymmetric.xperp_index_price]]) {
    assert.ok(markerMarkup(asymmetricMarkup,label).includes(`left:${priceToFraction(price,asymmetric)*100}%`), `${label} must use the shared interval-relative scale`);
  }
  const fairLeft = `${fairFraction*100}%`;
  assert.ok(markerMarkup(asymmetricMarkup,"Valtide Fair Value").includes(`left:${fairLeft}`));
  assert.ok(asymmetricMarkup.includes(`class="absolute top-[32px] h-14 w-px" style="left:${fairLeft};`),"Fair Value line must share the square's raw-price position");
  assert.ok(asymmetricMarkup.includes(`class="absolute top-0 -translate-x-1/2 whitespace-nowrap text-center text-[11px]" style="left:${fairLeft};`),"Fair Value label must share the square and line position");
  const bandMatch = asymmetricMarkup.match(/class="absolute top-\[38px\] h-11 rounded" style="left:([^;]+);width:([^;]+);/);
  assert.ok(bandMatch);
  assert.ok(Math.abs(Number.parseFloat(bandMatch[1])/100-unitsToFraction(-1))<1e-12);
  assert.ok(Math.abs(Number.parseFloat(bandMatch[2])/100-(unitsToFraction(1)-unitsToFraction(-1)))<1e-12);
  const coincident = {...v2,token_price:180,valtide_fair_value:180,fair_value_lower:179,fair_value_upper:181,xperp_index_price:180};
  const coincidentMarkup = render(ReferenceNumberLine,{r:coincident});
  for (const [label,zIndex,shape] of [["Observed xStock",1,"<circle"],["Valtide Fair Value",2,"<rect"],["X-Perp",3,"<path"]]) {
    const item = markerMarkup(coincidentMarkup,label);
    assert.ok(item.includes("left:50%"), `${label} should remain at the shared coincident price`);
    assert.ok(item.includes(`z-index:${zIndex}`), `${label} should retain nested-marker ordering`);
    assert.ok(item.includes(shape), `${label} should retain its distinct marker shape`);
  }
  const legacyXStock = {...v2,evidence_semantics:"p1a_xstock_challenger_xperp_second_market_v1",token_price:179.75,valtide_fair_value:180,xperp_index_price:180.25};
  for (const evidence_semantics of ["p1a_xstock_challenger_xperp_second_market_v1",EVIDENCE_SEMANTICS_V2]) {
    for (const evidence_state of ["SUPPORTED","INCONCLUSIVE","CHALLENGED"]) {
      const historicalOrOperational = {...legacyXStock,evidence_semantics,evidence_state};
      const compatibleMarkup = render(ReferenceNumberLine,{r:historicalOrOperational});
      assert.equal((compatibleMarkup.match(/data-price-marker=/g) ?? []).length,3);
      for (const [label,value] of [["Observed xStock",historicalOrOperational.token_price],["Valtide Fair Value",historicalOrOperational.valtide_fair_value],["X-Perp",historicalOrOperational.xperp_index_price]]) {
        assert.match(compatibleMarkup,new RegExp(`data-price-marker="${label}"`));
        assert.match(compatibleMarkup.slice(compatibleMarkup.indexOf("grid-cols-3")),new RegExp(`${label}[\\s\\S]*?\\$${value.toFixed(2)}`));
      }
      assert.match(compatibleMarkup,/aria-label="Observed xStock[\s\S]*Valtide Fair Value[\s\S]*X-Perp/);
    }
  }
  const nullPrices = render(ReferenceNumberLine,{r:{...v2,token_price:null,xperp_index_price:null}});
  assert.doesNotMatch(nullPrices,/data-price-marker="Observed xStock"|data-price-marker="X-Perp"/);
  assert.match(nullPrices,/data-price-marker="Valtide Fair Value"/);
  const chart = buildChartData([v2]);
  assert.equal(chart[0].token,v2.token_price);
  assert.equal(chart[0].fair,v2.valtide_fair_value);
  assert.equal(chart[0].xperp,v2.xperp_index_price);
  assert.deepEqual(chart[0].band,[v2.fair_value_lower,v2.fair_value_upper]);
  assert.equal(Object.hasOwn(chart[0],"last_trusted_reference"),false);
  assert.deepEqual(VALUATION_CHART_LABELS,{fair:"Valtide Fair Value",token:"Observed xStock",xperp:"X-Perp"});
  assert.equal(chartIntervalLabel([v2]),"90% Valuation Range");
  assert.equal(chartIntervalLabel([{...v2,interval_coverage_target:0.95}]),"95% Valuation Range");
  assert.equal(chartIntervalLabel([v2,{...v2,interval_coverage_target:0.95}]),"Valuation Range");
  assert.equal(buildChartData([{...v2,xperp_index_price:null,reference_under_test:999}])[0].xperp,null);
  assert.equal(buildChartData([{...v2,evidence_semantics:"legacy_v1",xperp_index_price:null,reference_under_test:201.25}])[0].xperp,201.25);
  const missingCurrentXperp = {...v2,xperp_index_price:null,xperp_index_source:null,reference_under_test:999,reference_under_test_source:"legacy_alias"};
  assert.doesNotMatch(render(ReferenceNumberLine,{r:missingCurrentXperp}),/\$999\.00/);
  const missingCurrentXperpApp = appWith({result:missingCurrentXperp,profile:v2.reference_profile});
  assert.doesNotMatch(missingCurrentXperpApp,/\$999\.00/);
  assert.match(missingCurrentXperpApp,/X-Perp<\/div><div[^>]*>—<\/div><div[^>]*>—<\/div>/);

  const xstockInside = render(ReferenceComparison,{r:{...v2,token_price:100,xperp_index_price:120, fair_value_lower:99,fair_value_upper:101}});
  assert.match(xstockInside,/Observed xStock is within the valuation range/);
  const xstockOutside = render(ReferenceComparison,{r:{...v2,token_price:102,xperp_index_price:100, fair_value_lower:99,fair_value_upper:101}});
  assert.match(xstockOutside,/Observed xStock is outside the valuation range/);
  assert.match(xstockInside,/Range View/);
  assert.equal((xstockInside.match(/Evidence State also considers model disagreement, data quality, and X-Perp confirmation\./g) ?? []).length,1);
  assert.doesNotMatch(xstockInside,/P1a-C|SUPPORT|WATCH|REVIEW|not two fully independent observations/);
});

test("Range View uses fixed interval-relative geometry independent of absolute prices and timeline span", () => {
  const base = consoleV2Fixture[0];
  const observations = [
    {...base,timestamp:"2026-10-01T12:00:00Z",valtide_fair_value:100,fair_value_lower:99,fair_value_upper:101,token_price:100.4,xperp_index_price:99.8,interval_coverage_target:0.9},
    {...base,timestamp:"2026-10-01T12:05:00Z",valtide_fair_value:200,fair_value_lower:199,fair_value_upper:201,token_price:201.5,xperp_index_price:199.3,interval_coverage_target:0.95},
    {...base,timestamp:"2026-10-01T12:10:00Z",valtide_fair_value:503,fair_value_lower:500,fair_value_upper:510,token_price:499,xperp_index_price:508,interval_coverage_target:0.9},
  ];
  const markerBlock = (markup,label) => markup.match(new RegExp(`<div data-price-marker="${label}"[^>]*>[\\s\\S]*?<\\/div>`))?.[0] ?? "";
  const markerFraction = (markup,label) => {
    const match = markerBlock(markup,label).match(/left:([^;]+);/);
    assert.ok(match,`${label} marker should have an interval-relative position`);
    return Number.parseFloat(match[1])/100;
  };
  const rangePosition = (markup) => {
    const match = markup.match(/class="absolute top-\[38px\] h-11 rounded" style="left:([^;]+);width:([^;]+);/);
    assert.ok(match,"valuation band should use fixed interval-relative boundaries");
    return {left:Number.parseFloat(match[1])/100,width:Number.parseFloat(match[2])/100};
  };
  const close = (actual,expected,message) => assert.ok(Math.abs(actual-expected)<1e-12,message);
  const expectedBand = {left:unitsToFraction(-1),width:unitsToFraction(1)-unitsToFraction(-1)};
  const rendered = observations.map((r) => render(ReferenceNumberLine,{r}));

  for (let index=0; index<observations.length; index++) {
    const r = observations[index];
    const markup = rendered[index];
    for (const [label,price] of [["Observed xStock",r.token_price],["Valtide Fair Value",r.valtide_fair_value],["X-Perp",r.xperp_index_price]]) {
      close(markerFraction(markup,label),priceToFraction(price,r),`${label} uses the shared interval-relative mapping`);
    }
    close(toBandUnits(r.fair_value_lower,r),-1,"lower maps to interval unit -1");
    close(toBandUnits(r.fair_value_upper,r),1,"upper maps to interval unit +1");
    const bandPosition = rangePosition(markup);
    close(bandPosition.left,expectedBand.left,"band left edge is fixed");
    close(bandPosition.width,expectedBand.width,"band visual width is fixed");
    assert.match(markup,new RegExp(`${Math.round(r.interval_coverage_target*100)}% Valuation Range`));
  }
  close(markerFraction(rendered[0],"Valtide Fair Value"),markerFraction(rendered[1],"Valtide Fair Value"),"same relative interval position across an absolute price shift is intentional");
  assert.match(rendered[0],/Valtide Fair Value <span[^>]*>\$100\.00/);
  assert.match(rendered[1],/Valtide Fair Value <span[^>]*>\$200\.00/);

  const asymmetric = {...base,token_price:179.5,valtide_fair_value:180,fair_value_lower:179,fair_value_upper:182,xperp_index_price:181};
  const asymmetricMarkup = render(ReferenceNumberLine,{r:asymmetric});
  const lower = priceToFraction(asymmetric.fair_value_lower,asymmetric);
  const fair = priceToFraction(asymmetric.valtide_fair_value,asymmetric);
  const upper = priceToFraction(asymmetric.fair_value_upper,asymmetric);
  assert.ok(lower < fair && fair < upper);
  assert.notEqual(fair,(lower+upper)/2,"asymmetric bounds preserve Fair Value's proportional position");
  close(markerFraction(asymmetricMarkup,"Valtide Fair Value"),fair);
  close(markerFraction(asymmetricMarkup,"Observed xStock"),priceToFraction(asymmetric.token_price,asymmetric));
  close(markerFraction(asymmetricMarkup,"X-Perp"),priceToFraction(asymmetric.xperp_index_price,asymmetric));
  close(rangePosition(asymmetricMarkup).left,expectedBand.left);
  close(rangePosition(asymmetricMarkup).width,expectedBand.width);

  const ascending = {...base,token_price:179,valtide_fair_value:180,xperp_index_price:181,fair_value_lower:178,fair_value_upper:182};
  assert.ok(priceToFraction(ascending.token_price,ascending)<priceToFraction(ascending.valtide_fair_value,ascending));
  assert.ok(priceToFraction(ascending.valtide_fair_value,ascending)<priceToFraction(ascending.xperp_index_price,ascending));
  const descending = {...ascending,token_price:181,xperp_index_price:179};
  assert.ok(priceToFraction(descending.token_price,descending)>priceToFraction(descending.valtide_fair_value,descending));
  assert.ok(priceToFraction(descending.valtide_fair_value,descending)>priceToFraction(descending.xperp_index_price,descending));

  const outside = {...base,token_price:182,valtide_fair_value:180,xperp_index_price:180.5,fair_value_lower:179,fair_value_upper:181};
  const outsideMarkup = render(ReferenceNumberLine,{r:outside});
  const outsideBand = rangePosition(outsideMarkup);
  assert.ok(markerFraction(outsideMarkup,"Observed xStock")>outsideBand.left+outsideBand.width,"out-of-range price stays outside the band");
  assert.ok(markerFraction(outsideMarkup,"Observed xStock")<1,"clamping applies only at the viewport boundary");

  const coincident = {...base,token_price:180,valtide_fair_value:180,xperp_index_price:180,fair_value_lower:179,fair_value_upper:181};
  const coincidentMarkup = render(ReferenceNumberLine,{r:coincident});
  const coincidentFractions = ["Observed xStock","Valtide Fair Value","X-Perp"].map((label) => markerFraction(coincidentMarkup,label));
  assert.deepEqual(coincidentFractions,[0.5,0.5,0.5]);
  assert.equal((coincidentMarkup.match(/data-price-marker=/g)??[]).length,3);

  for (const invalid of [
    {...coincident,fair_value_lower:180,fair_value_upper:180},
    {...coincident,fair_value_lower:181,fair_value_upper:179},
  ]) {
    const invalidMarkup = render(ReferenceNumberLine,{r:invalid});
    assert.doesNotMatch(invalidMarkup,/NaN|Infinity/);
    assert.match(invalidMarkup,/style="left:50%;width:0%;/);
    assert.equal(priceToFraction(invalid.valtide_fair_value,invalid),0.5);
  }

  const legacyFallback = {...ascending,evidence_semantics:"p1a_xstock_challenger_xperp_second_market_v1",xperp_index_price:null,reference_under_test:184};
  assert.equal(priceToFraction(184,legacyFallback),markerFraction(render(ReferenceNumberLine,{r:legacyFallback}),"X-Perp"));

  const selected = {...observations[0]};
  const distant = {...selected,fair_value_lower:1,fair_value_upper:1_000_000,token_price:800_000,xperp_index_price:900_000};
  const selectedMarkup = render(ReferenceComparison,{r:selected});
  assert.equal(render(ReferenceComparison,{r:selected,domainResults:[selected,distant]}),selectedMarkup,"unrelated timeline rows cannot alter the selected-observation Range View");
  const appSource = fs.readFileSync(path.join(__dirname,"../src/App.tsx"),"utf8");
  assert.match(appSource,/<ReferenceComparison r=\{current\} \/>/);
  assert.doesNotMatch(appSource,/domainResults=/);
});

test("Equal-height Timeline card alignment keeps the chart fixed and Policy Proposal independent", () => {
  const appSource = fs.readFileSync(path.join(__dirname,"../src/App.tsx"),"utf8");
  const replaySource = fs.readFileSync(path.join(__dirname,"../src/views/HistoricalReplay.tsx"),"utf8");
  const chartSource = fs.readFileSync(path.join(__dirname,"../src/components/EscalationChart.tsx"),"utf8");
  assert.match(appSource,/grid items-stretch gap-4 xl:grid-cols-\[minmax\(0,1\.3fr\)_minmax\(0,1fr\)\]/);
  assert.match(replaySource,/className="flex min-w-0 flex-col"/);
  assert.doesNotMatch(replaySource,/className="flex h-full min-w-0 flex-col"/);
  assert.match(replaySource,/<div className="flex w-full flex-1 items-center">\s*<EscalationChart[\s\S]*?<\/div>/);
  assert.match(replaySource,/className="mt-auto flex flex-wrap items-center gap-3 border-t pt-3"/);
  const chartRoot = chartSource.match(/className="([^"]*h-\[320px\][^"]*)"/)?.[1];
  assert.ok(chartRoot,"EscalationChart root retains an explicit fixed height");
  assert.match(chartRoot,/^h-\[320px\] min-h-\[280px\] w-full xl:h-\[360px\]$/);
  assert.doesNotMatch(chartRoot,/(?:^|\s)(?:flex-1|h-full|grow)(?:\s|$)/);
  assert.doesNotMatch(chartSource,/(?:^|\s)(?:flex-1|h-full|grow)(?:\s|$)/);
  assert.match(appSource,/\{context === "Demo" && <details[\s\S]*?Advanced: Policy Proposal[\s\S]*?<PolicyFoundry \/>[\s\S]*?<\/details>\}/);
  assert.match(appSource,/<\/div>\s*\{context === "Demo" && <details[\s\S]*?Advanced: Policy Proposal[\s\S]*?<\/details>\}\s*<div className="grid gap-4 md:grid-cols-2">/);
});

test("Current semantic copy is shared and old explicit rule generations stay recorded", () => {
  const current = evidenceCopy(consoleV2Fixture[0]);
  assert.equal(current.title,"Observed xStock is supported");
  assert.equal(current.detail,"Model disagreement is low, exact-time X-Perp is available, and required quality checks pass.");
  assert.equal(evidenceCopy(consoleV2Fixture[3]).detail,"The result is in the watch band, or a required market check is unavailable, stale, ambiguous, or below the quality threshold.");
  assert.equal(evidenceCopy(consoleV2Fixture[4]).detail,"Model disagreement is high, and exact-time X-Perp is closer to P1a-C than to xStock. Review the price before using it in a risk decision.");
  const oldRecord = {...consoleV2Fixture[0], evidence_state:"CHALLENGED", reason_codes:["OLD_RECORDED_REASON"], evidence_semantics:"p1a_xstock_challenger_xperp_second_market_v1"};
  const old = evidenceCopy(oldRecord);
  assert.match(old.title,/Recorded challenged evidence/);
  assert.match(old.detail,/not been reclassified/);
  assert.equal(oldRecord.evidence_state,"CHALLENGED");
  assert.deepEqual(oldRecord.reason_codes,["OLD_RECORDED_REASON"]);
});

test("Cold Operational never falls back to cached Demo evidence", () => {
  const html = appWith({error:"503 data_unavailable"});
  assert.match(html,/Operational (?:Loading|Unavailable)/);
  assert.doesNotMatch(html,/Demo Fixture · 6 Observations|Scenario policy|Example demo policy/);
});

test("Validation Console exposes only the three API-enabled production assets", () => {
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
    ["NVDAx","unified_xstock_p1ac_xperp_evidence_v1"],
    ["SPYx","unified_xstock_p1ac_xperp_evidence_v1"],
    ["AAPLx","unified_xstock_p1ac_xperp_evidence_v1"],
  ].map(([asset,reference_profile]) => ({...base,asset,reference_profile}));
  catalog.push({...base,asset:"QQQx",reference_profile:"xstock_vs_p1ac_challenger",api_exposed:false});
  catalog.push({...base,asset:"TSLAx",reference_profile:"xstock_vs_p1ac_challenger",api_exposed:false});
  const html = appWith({assetList:catalog});
  assert.match(html,/aria-haspopup="listbox"/);
  assert.match(html,/aria-label="Search Assets"/);
  assert.match(html,/aria-label="Available Assets"/);
  assert.match(html,/asset-picker__chevron/);
  assert.match(html,/viewBox="0 0 16 16"/);
  assert.doesNotMatch(html,/⌄/);
  for (const asset of ["NVDAx","SPYx","AAPLx"]) {
    assert.match(html,new RegExp(`>${asset}<`));
  }
  assert.doesNotMatch(html, />QQQx</);
  assert.doesNotMatch(html, />TSLAx</);
  assert.match(html,/NVIDIA Tokenized Equity/);
  assert.match(html,/S&amp;P 500 Tokenized ETF/);
  assert.match(html,/Coming Soon/);
  assert.match(html,/Model fit blocked/);
  assert.match(html,/Operational Readiness Issue:/);
  assert.doesNotMatch(html,/No other asset|readiness is partial/);
});

test("Asset picker derives readable names and honest availability labels", () => {
  assert.equal(assetDisplayName("NVDAx"), "NVIDIA Tokenized Equity");
  assert.equal(assetDisplayName("UNKNOWNx"), "Tokenized Equity");
  assert.equal(assetAvailabilityLabel(true), "Available");
  assert.equal(assetAvailabilityLabel(false), "Coming Soon");
  assert.equal(assetAvailabilityLabel(undefined), "Checking");
});

test("Historical evidence summary uses the selected asset backtest without deriving new states", () => {
  const query = new QueryClient({defaultOptions:{queries:{retry:false}}});
  const asset = "SPYx";
  const profile = "unified_xstock_p1ac_xperp_evidence_v1";
  query.setQueryData(client.assetQueryKeys.backtest(asset, profile), {
    asset,source:"historical",n_observations:4110,
    evidence_state_counts:{SUPPORTED:4009,INCONCLUSIVE:30,CHALLENGED:71},
    n_evaluable:3000,mae:1.2,rmse:2.1,interval_coverage:0.9,
    window_start:"2026-09-21T00:00:00Z",window_end:"2026-10-05T06:25:00Z",
    model_id:"P1a-C",model_version:"0.3.0",note:"Retrospective diagnostics.",
  });
  const html = renderToStaticMarkup(h(QueryClientProvider,{client:query},h(ModelEvidence,{asset,profile})));
  query.clear();
  for (const label of [
    "Selected Historical Evidence", "Evidence States Across Historical Observations",
    "Observations", "Observations With A Contemporaneous Benchmark", "Benchmark Coverage",
    "Advanced Point-Error Diagnostics", "Mean Absolute Error", "Root Mean Squared Error",
  ]) assert.ok(html.includes(label), `missing ${label}`);
  assert.match(html,/SUPPORTED 4009/);
  assert.match(html,/INCONCLUSIVE 30/);
  assert.match(html,/CHALLENGED 71/);
  assert.doesNotMatch(html,/James|research dashboard|Threshold Selection/);
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
  assert.match(html,/Current policy mapping/);
  assert.match(html,/Current deployed state — not historical chain state/);
  assert.doesNotMatch(html,/Current RiskGuard ·/);
});

test("Current evidence mapping and stale RiskGuard enforcement remain separate", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"REQUIRE_REVIEW",evidence_state:"SUPPORTED",exists:true,fresh:false,network:"Testnet",chain_id:1952,attestation:{publishedAt:Math.floor(Date.now()/1000)-7200}};
  const html = appWith({result:fixture[0],chain});
  assert.match(html,/Current policy mapping/);
  assert.match(html,/Reason/);
  assert.match(html,/Observed xStock is supported/);
  assert.match(html,/RiskGuard status/);
  assert.match(html,/Evidence state/);
  assert.match(html,/Policy mapping/);
  assert.match(html,/Enforced action/);
  const policyStart = html.indexOf(">Policy action</h2>");
  const policyEnd = html.indexOf("</section>", policyStart);
  assert.ok(policyStart >= 0 && policyEnd > policyStart);
  assert.doesNotMatch(html.slice(policyStart, policyEnd),/Technical Details/);
  assert.match(html,/ALLOW/);
  assert.match(html,/REQUIRE_REVIEW/);
  assert.doesNotMatch(html,/Raw policy value/);
});

test("Evidence and policy panels use consistent sentence case", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"MONITOR",on_challenged:"REQUIRE_REVIEW",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"ALLOW",evidence_state:"SUPPORTED",exists:true,fresh:true,network:"Testnet",chain_id:1952,attestation:null};
  for (const [state,action] of [
    ["SUPPORTED","Allow new borrowing"],
    ["INCONCLUSIVE","Continue monitoring"],
    ["CHALLENGED","Pause and review"],
  ]) {
    const html = appWith({result:{...fixture[0],evidence_state:state},chain});
    assert.ok(html.includes(action), `missing action ${action}`);
    assert.match(html,/Current finding/);
    assert.match(html,/Policy action/);
  }
  const html = appWith({result:fixture[0],chain});
  for (const phrase of ["Publication Status","Valuation Range","Range View","Peak Model Distance","Observation Details","Source Provenance","Market State"]) assert.ok(html.includes(phrase), `missing ${phrase}`);
});

test("Policy action exposes its core rows without a disclosure and keeps missing policy non-alarming", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"REQUIRE_REVIEW",evidence_state:"SUPPORTED",exists:true,fresh:true,network:"Testnet",chain_id:1952,attestation:null};
  const bound = appWith({result:consoleV2Fixture[0],profile:consoleV2Fixture[0].reference_profile,chain});
  for (const row of ["Evidence state", "Policy mapping", "RiskGuard status", "Enforced action"]) assert.match(bound, new RegExp(row));
  const policyStart = bound.indexOf(">Policy action</h2>");
  const policyEnd = bound.indexOf("</section>", policyStart);
  assert.ok(policyStart >= 0 && policyEnd > policyStart);
  assert.doesNotMatch(bound.slice(policyStart, policyEnd),/Technical Details/);

  const noBindingAsset = {
    asset:"NVDAx",token_source:"okx_onchainos",underlying_source:"alpaca",
    reference_profile:consoleV2Fixture[0].reference_profile,registered:true,api_exposed:true,
    model_available:true,quant_artifact_ready:true,historical_data_available:true,
    live_data_configured:true,runtime_ready:true,operational_ready:true,
    operational_scheduler_enabled:true,latest_observation_timestamp:consoleV2Fixture[0].timestamp,
    latest_observation_age_seconds:0,latest_observation_freshness:"fresh",
    onchain_binding_configured:false,readiness_error_codes:[],
  };
  const unbound = appWith({result:consoleV2Fixture[0],profile:consoleV2Fixture[0].reference_profile,assetList:[noBindingAsset]});
  assert.match(unbound,/No policy connected/);
  assert.match(unbound,/No curator policy is connected for this asset\./);
  assert.doesNotMatch(unbound,/X Layer Connected|X Layer Unavailable|X Layer Not Configured|Optional Protocol Deployment|Not Configured|Registry Attestation/);
  assert.equal(render(RegistryPanel,{bindingConfigured:false}),"");
});

test("RegistryPanel is asset-agnostic across the three API-bound production assets", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const vaults = {
    NVDAx:"0x1111111111111111111111111111111111111111",
    SPYx:"0x2222222222222222222222222222222222222222",
    AAPLx:"0x3333333333333333333333333333333333333333",
  };
  for (const [asset,demo_vault] of Object.entries(vaults)) {
    const controlPlane = {
      asset,policy,policy_action:"ALLOW",evidence_state:"SUPPORTED",exists:true,fresh:true,
      network:"X Layer Testnet",chain_id:1952,attestation:null,publication_compatible:true,
      configured:true,deployed:true,registry:`registry-${asset}`,risk_guard:`guard-${asset}`,
      demo_vault,asset_id:`id-${asset}`,reference_id:`reference-${asset}`,model_version:"0.3.0",registry_fresh:true,
    };
    const runtime = {asset,auto_publish_enabled:true,last_publish_status:"published",last_publish_error:null};
    const enforcement = {asset,exists:true,fresh:true,expected_revert:false,reverted:false,returned_action_code:0,passed:true};
    const html = render(RegistryPanel,{controlPlane,runtime,enforcement,bindingConfigured:true});
    for (const label of ["X Layer Testnet","ValidationRegistry","RiskGuard","DemoVault","Automatic Publishing","Publication Compatibility","Delivery Status","Enabled","Compatible","Published"]) assert.ok(html.includes(label),`${asset} panel missing ${label}`);
    const ownVault = `${demo_vault.slice(0,8)}…${demo_vault.slice(-6)}`;
    assert.ok(html.includes(ownVault),`${asset} panel should show its API-provided DemoVault`);
    for (const [otherAsset,otherVault] of Object.entries(vaults)) {
      if (otherAsset === asset) continue;
      assert.ok(!html.includes(`${otherVault.slice(0,8)}…${otherVault.slice(-6)}`),`${asset} panel must not show ${otherAsset}'s DemoVault`);
    }
    assert.doesNotMatch(html,/Read Only/);
  }
});

test("Observation Details humanizes current timestamps and separates operational health from history", () => {
  const result = {
    ...consoleV2Fixture[0],
    timestamp:"2026-10-06T17:20:00Z",
    token_observed_at:"2026-10-06T17:20:00Z",
    xperp_index_ts:"2026-10-06T17:20:00Z",
    source_provenance:{token_source:"okx_onchainos",underlying_source:"alpaca",scenario:"weekend_divergence"},
  };
  const runtime = {scheduler_enabled:true,last_tick_status:"success",last_tick_attempt_at:"2026-10-06T17:20:05Z",last_result_timestamp:"2026-10-06T17:20:00Z",last_error:null};
  const controlPlane = {fresh:true};
  const operational = render(ObservationAudit,{result,context:"Operational",runtime,controlPlane});
  assert.match(operational,/Observation Details · Operational · 2026-10-06 17:20 UTC/);
  for (const label of ["Observation Time","xStock Source","xStock Observed","X-Perp Source","X-Perp Observed","X-Perp Age","Underlying Anchor","Underlying Source","Anchor Age","Observation Age","Model","Current RiskGuard Status","Feed Status","Latest Observation","Token Source","Scenario"]) assert.match(operational,new RegExp(label));
  assert.match(operational,/Valtide Model · v0\.2\.0/);
  assert.match(operational,/2026-10-06 17:20 UTC/);
  assert.match(operational,/weekend_divergence/);
  assert.doesNotMatch(operational,/2026-10-06T17:20:00Z|P1a-C|Calibration|Evidence Rule|Last Update Attempt|Feed Error/);
  assert.match(operational,/Underlying Anchor[\s\S]*\$180\.00/);
  assert.match(operational,/Underlying Source[\s\S]*alpaca/);
  assert.match(operational,/Anchor Age[\s\S]*18h/);

  const withoutUnderlyingSource = render(ObservationAudit,{result:{...result,source_provenance:{scenario:"weekend_divergence"}},context:"Historical"});
  assert.match(withoutUnderlyingSource,/Underlying Source[\s\S]*—/);
  const missingCurrentXperp = render(ObservationAudit,{result:{...result,xperp_index_source:null,xperp_index_ts:null,reference_under_test_source:"legacy_alias",reference_under_test_ts:"2026-10-05T00:00:00Z"},context:"Historical"});
  assert.match(missingCurrentXperp,/X-Perp Source[\s\S]*—/);
  assert.doesNotMatch(missingCurrentXperp,/legacy_alias|2026-10-05 00:00 UTC/);

  const failedRuntime = {...runtime,last_tick_status:"failure",last_error:"feed timeout"};
  const failed = render(ObservationAudit,{result,context:"Operational",runtime:failedRuntime});
  assert.match(failed,/Last Update Attempt/);
  assert.match(failed,/Feed Error/);
  assert.match(failed,/feed timeout/);

  const historical = render(ObservationAudit,{result,context:"Historical",runtime,controlPlane});
  const demo = render(ObservationAudit,{result,context:"Demo",runtime,controlPlane});
  assert.match(historical,/Observation Details · Historical · 2026-10-06 17:20 UTC/);
  assert.match(demo,/Observation Details · Demo · 17:20 UTC/);
  for (const view of [historical,demo]) assert.doesNotMatch(view,/Feed Status|Latest Observation|Current RiskGuard Status|Last Update Attempt|Feed Error/);

  const oldV1 = render(ObservationAudit,{result:{...result,evidence_semantics:"p1a_xstock_challenger_xperp_second_market_v1"},context:"Historical"});
  assert.match(oldV1,/Classification Version/);
  assert.match(oldV1,/Earlier Rule/);
  assert.doesNotMatch(oldV1,/p1a_xstock_challenger_xperp_second_market_v1|Evidence Rule|Calibration/);
});

test("Human model, session and reason labels preserve underlying identifiers", () => {
  assert.equal(modelDisplayName("0.3.0"),"Valtide Model · v0.3.0");
  assert.equal(modelDisplayName(null),"Valtide Model");
  assert.equal(sessionLabel("regular"),"Regular Session");
  assert.equal(sessionLabel("premarket"),"Extended Hours");
  assert.equal(sessionLabel("afterhours"),"Extended Hours");
  assert.equal(sessionLabel("overnight"),"Overnight");
  assert.equal(sessionLabel("closed"),"Market Closed");
  assert.equal(dateTimeUTC("2026-10-06T17:20:00Z"),"2026-10-06 17:20 UTC");

  const cases = [
    ["P1A_XSTOCK_SUPPORT_BAND","Low Model Disagreement"],
    ["P1A_XSTOCK_WATCH_BAND","Moderate Model Disagreement"],
    ["P1A_XSTOCK_REVIEW_BAND","High Model Disagreement"],
    ["XPERP_CORROBORATES_XSTOCK","X-Perp Supports xStock"],
    ["XPERP_CORROBORATES_P1A","X-Perp Supports Model Challenge"],
    ["P1A_XSTOCK_DETECTOR_UNAVAILABLE","Model Disagreement Signal Unavailable"],
    ["P1A_XSTOCK_SUPPORT_NOT_PROMOTED","Support Signal Not Enabled"],
    ["P1A_XSTOCK_CHALLENGE_NOT_PROMOTED","Challenge Signal Not Enabled"],
    ["CALIBRATION_GLOBAL_FALLBACK","Global Calibration Applied"],
  ];
  for (const [code,label] of cases) {
    const html = render(ReasonCodes,{codes:[code],evidenceState:"INCONCLUSIVE"});
    assert.match(html,new RegExp(`title="${code}"`));
    assert.match(html,new RegExp(label));
  }
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
  assert.match(html,/No policy connected/);
  assert.match(render(ReasonCodes,{codes:result.reason_codes,evidenceState:result.evidence_state}),/Global Calibration Applied/);
});

test("Valuation Range is concise and does not repeat model-dependence methodology", () => {
  const xstock = render(ReferenceComparison, {
    r: {...fixture[0], reference_profile:"xstock_vs_p1ac_challenger"},
  });
  assert.match(xstock, /Observed xStock is within the valuation range/);
  assert.match(xstock, /Evidence State also considers model disagreement, data quality, and X-Perp confirmation\./);
  assert.doesNotMatch(xstock, /Model-based challenger evidence|P1a-C assimilates|not two fully independent observations|SUPPORT|WATCH|REVIEW/);

  const legacy = render(ReferenceComparison, {
    r: {...fixture[0], reference_profile:"legacy_xperp_vs_p1ac", validation_target:"reference_under_test", evidence_semantics:"legacy_reference_under_test_v1"},
  });
  assert.match(legacy, /Reference is within the valuation range/);
  assert.doesNotMatch(legacy, /Observed xStock/);
});

test("Decision summary uses concise current language and preserves old recorded states", () => {
  const xstock = appWith({
    result: {...consoleV2Fixture[0], reference_profile:"unified_xstock_p1ac_xperp_evidence_v1"},
    profile:"unified_xstock_p1ac_xperp_evidence_v1",
  });
  assert.match(xstock, /Observed xStock is supported/);
  assert.match(xstock, /Model disagreement is low, exact-time X-Perp is available, and required quality checks pass\./);
  assert.doesNotMatch(xstock, /SUPPORT band|not two fully independent observations/);
  assert.match(xstock, /Evidence assessment/);
  assert.doesNotMatch(xstock, /Current finding · Operational/);

  const legacy = appWith({result: {...fixture[0], reference_profile:"legacy_xperp_vs_p1ac", validation_target:"reference_under_test", evidence_semantics:"legacy_reference_under_test_v1"}});
  assert.match(legacy, /Recorded supported evidence/);
  assert.match(legacy, /has not been reclassified by the current Console/);
  assert.match(legacy, /Current policy mapping/);
});

test("Observation and delivery audit survives unavailable X Layer reads", () => {
  const runtime = {scheduler_enabled:true,last_tick_status:"failure",last_tick_attempt_at:"2026-09-25T10:01:00Z",last_error:"source missing",auto_publish_enabled:true,last_publish_status:"failed",last_publish_attempt_at:"2026-09-25T10:02:00Z",last_publish_observation_ts:"2026-09-25T09:55:00Z",last_published_observation_ts:"2026-09-25T09:50:00Z",last_published_at:1790325969,last_publish_tx_hash:"0xFULL_TRANSACTION_HASH",last_publish_error:"delivery failed"};
  const audit = render(ObservationAudit,{result:fixture[0],context:"Operational",runtime});
  for (const label of ["Observation Details · Operational · 2026-09-19 14:00 UTC", "X-Perp Age", "Underlying Anchor", "Underlying Source", "Anchor Age", "Source Provenance", "Model", "Last Update Attempt", "Feed Status", "Latest Observation"]) assert.ok(audit.includes(label));
  assert.match(audit,/source missing/);
  assert.match(audit,/2026-09-25 10:01 UTC/);
  assert.doesNotMatch(audit,/2026-09-19T14:00:00Z|Calibration|Evidence Rule|Operational Feed Error/);
  const chain = render(RegistryPanel,{isError:true,mode:"historical",runtime});
  assert.doesNotMatch(chain,/DEMO MAPPING/);
  for (const value of ["2026-09-25 10:02 UTC","2026-09-25 09:50 UTC",runtime.last_publish_tx_hash,runtime.last_publish_error,"Read Only"]) assert.ok(chain.includes(value));
});

test("Historical ranges use timestamps and Demo ranges never add observations", () => {
  assert.equal(filterHistoricalResults(fixture, "ALL").length, 6);
  const historicalRows = [...fixture, { ...fixture[0], timestamp: "2026-09-10T14:00:00Z" }];
  assert.equal(filterHistoricalResults(historicalRows, "7D").length, 6);
  assert.equal(filterDemoResults(fixture, "FULL").length, 6);
  assert.equal(filterDemoResults(fixture, "15M").length, 3);
  assert.ok(filterDemoResults(fixture, "10M").every((row) => fixture.includes(row)));
});

test("Instrument Passport validates addresses and resolves only the labelled Demo address", () => {
  assert.equal(passportStatusFor(""), "idle");
  assert.equal(passportStatusFor("0xnot-an-address"), "invalid");
  assert.equal(passportStatusFor("0x2222222222222222222222222222222222222222"), "unknown");
  assert.equal(passportStatusFor(DEMO_PASSPORT_ADDRESS), "resolved");
  const invalid = render(InstrumentPassport, { initialAddress: "0xnot-an-address" });
  assert.match(invalid, /exactly 40 hexadecimal characters/);
  const unknown = render(InstrumentPassport, { initialAddress: "0x2222222222222222222222222222222222222222" });
  assert.match(unknown, /No demo metadata is available/);
  assert.doesNotMatch(unknown, /SHAREHOLDER RIGHTS/);
  const resolved = render(InstrumentPassport, { initialAddress: DEMO_PASSPORT_ADDRESS });
  for (const value of ["Price Exposure", "VERIFIED", "Demo Assertion", "Shareholder Rights", "NONE", "BALANCE ADJUSTMENT", "xSTOCKS WITHDRAWAL", "Rights Profile · Differs From A Share"]) assert.match(resolved, new RegExp(value, "i"));
  assert.match(resolved, /Demo Data · No Live Address Lookup/);
  assert.match(resolved, /type="submit"/);
  for (const value of ["Token Rights Metadata", "Demo Data", "Check Address", "Load Demo Address", "Collateral Identity", "Dividend Treatment", "Redemption"]) assert.match(resolved, new RegExp(value));
  assert.doesNotMatch(resolved, /fixture|precomputed|example metadata/i);
});

test("Policy Foundry renders a deterministic diff and read-only approval boundary", () => {
  const html = render(PolicyFoundry);
  for (const value of ["Policy Proposal", "deterministic demo policy for review", "900s", "600s", "REQUIRE_REVIEW", "MONITOR", "RESTRICT_NEW_RISK", "Unsigned Calldata", "Reference ABI", "Review Only · No Transaction Submission", "This demo does not sign or submit transactions."]) assert.match(html, new RegExp(value, "i"));
  assert.doesNotMatch(html, /Agent Council|ABI SHAPE VERIFIED|Human Approval Required/);
  assert.match(html, /Not Deployed/);
  assert.doesNotMatch(html, /fixture|prototype|--example/i);
  assert.match(POLICY_PROPOSAL.calldata, /^0xf5b39423[0-9a-f]{320}$/);
});

test("Machine publication statuses use the requested display casing", () => {
  assert.equal(pipelineStatusLabel("published"), "Published");
  assert.equal(deliveryStatusLabel("published"), "Published");
  assert.equal(deliveryStatusLabel("failed"), "Failed");
});

test("Historical observation audit is labelled as historical evidence", () => {
  const audit = render(ObservationAudit, { result: fixture[0], context: "Historical", runtime:{scheduler_enabled:true,last_tick_status:"success",last_result_timestamp:"2026-10-06T17:20:00Z"}, controlPlane:{fresh:true} });
  assert.match(audit, /Observation Details · Historical · 2026-09-19 14:00 UTC/);
  assert.doesNotMatch(audit, /Feed Status|Latest Operational Observation|Current RiskGuard Status|Last Update Attempt|Feed Error|2026-09-19T14:00:00Z/);
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
