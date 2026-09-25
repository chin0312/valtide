const assert = require("node:assert/strict");
const test = require("node:test");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
const { load } = require("./load-source.cjs");
const client = load("../src/api/client.ts");
const fixture = require("../src/fixtures/weekend_divergence.json");
const { filterOperationalResults } = load("../src/views/OperationalTimeline.tsx");
const { mergeObservations, rebasePosition } = load("../src/lib/playback.ts");
const { ReasonCodes } = load("../src/components/ReasonCodes.tsx");
const { RegistryPanel } = load("../src/components/RegistryPanel.tsx");
const { ObservationAudit } = load("../src/components/ObservationAudit.tsx");
const App = load("../src/App.tsx").default;
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
    global.fetch = async () => new Response(JSON.stringify({source:"historical"}));
    assert.equal((await client.fetchHistoricalBacktest()).source, "historical");
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

test("Asynchronous polling retains newest results and anchors replay by timestamp", () => {
  const rows = fixture.slice(0,3);
  assert.equal(mergeObservations(rows, fixture[3]).length,4);
  assert.equal(mergeObservations(rows,rows[1]).length,3);
  assert.equal(mergeObservations(fixture,rows[1]).at(-1),fixture.at(-1));
  assert.equal(rebasePosition(1.5,rows,fixture.slice(1)),0.5);
});

function appWith({result, rows, chain, error} = {}) {
  const query = new QueryClient({defaultOptions:{queries:{retry:false,retryOnMount:false}}});
  query.setQueryData(["demo-replay","canonical"],{results:fixture,source:"offline-fixture"});
  if (result) query.setQueryData(["valuation","operational","NVDAx"],result);
  if (rows) query.setQueryData(["history","NVDAx",288],rows);
  if (chain) query.setQueryData(["onchain","NVDAx"],chain);
  if (error) query.getQueryCache().build(query,{queryKey:["valuation","operational","NVDAx"]}).setState({status:"error",error:new Error(error),fetchStatus:"idle"});
  const html = renderToStaticMarkup(h(QueryClientProvider,{client:query},h(App)));
  query.clear();
  return html;
}

test("Cold Operational stays unavailable even when Demo is cached", () => {
  const html = appWith({error:"503 data_unavailable"});
  assert.match(html,/Operational unavailable/);
  assert.doesNotMatch(html,/Demo fixture|Scenario policy|Example demo policy/);
});

test("Operational failure preserves cached evidence with a degraded label", () => {
  const html = appWith({result:fixture[0],error:"offline"});
  assert.match(html,/Operational degraded/);
  assert.match(html,/180.00/);
  assert.doesNotMatch(html,/Demo fixture|Example demo policy/);
});

test("Prior operational evidence is not paired with current enforcement", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"RESTRICT_NEW_RISK",evidence_state:"CHALLENGED",exists:true,fresh:true,network:"Testnet",chain_id:1952,attestation:null};
  const html = appWith({result:fixture[1],rows:fixture.slice(0,2),chain});
  assert.match(html,/Prior observation/);
  assert.match(html,/Current deployed state — not historical chain state/);
  assert.doesNotMatch(html,/Current RiskGuard ·/);
});

test("Current evidence mapping and stale RiskGuard enforcement remain separate", () => {
  const policy = {on_supported:"ALLOW",on_inconclusive:"REQUIRE_REVIEW",on_challenged:"RESTRICT_NEW_RISK",on_stale:"REQUIRE_REVIEW",max_age:900};
  const chain = {policy,policy_action:"REQUIRE_REVIEW",evidence_state:"SUPPORTED",exists:true,fresh:false,network:"Testnet",chain_id:1952,attestation:null};
  const html = appWith({result:fixture[0],chain});
  assert.match(html,/Current evidence · policy mapping/);
  assert.match(html,/Current RiskGuard · stale/);
  assert.match(html,/ALLOW/);
  assert.match(html,/REQUIRE_REVIEW/);
});

test("Null reference, all reasons and unavailable policy remain truthful", () => {
  const result = {...fixture[0],reference_under_test:null,standardized_deviation:null,reference_deviation_pct:null,evidence_state:"INCONCLUSIVE",reason_codes:["COMPARATOR_UNAVAILABLE","TOKEN_DATA_UNAVAILABLE","CALIBRATION_GLOBAL_FALLBACK","UNKNOWN_BACKEND_REASON"]};
  const html = appWith({result});
  assert.doesNotMatch(html,/NaN|challenge threshold not met|Example demo policy/);
  for (const code of result.reason_codes) assert.ok(html.includes(code));
  assert.match(html,/UNAVAILABLE/);
  assert.match(render(ReasonCodes,{codes:result.reason_codes,evidenceState:result.evidence_state}),/Global fallback calibration/);
});

test("Observation and delivery audit survives unavailable X Layer reads", () => {
  const runtime = {scheduler_enabled:true,last_tick_status:"failure",last_tick_attempt_at:"2026-09-25T10:01:00Z",last_error:"source missing",auto_publish_enabled:true,last_publish_status:"failed",last_publish_attempt_at:"2026-09-25T10:02:00Z",last_publish_observation_ts:"2026-09-25T09:55:00Z",last_published_observation_ts:"2026-09-25T09:50:00Z",last_published_at:1790325969,last_publish_tx_hash:"0xFULL_TRANSACTION_HASH",last_publish_error:"delivery failed"};
  const audit = render(ObservationAudit,{result:fixture[0],context:"Operational",runtime});
  for (const label of ["Canonical 5m", "Reference source lag", "Trusted-anchor age", "source provenance", "Model / version", "Last attempt"]) assert.ok(audit.includes(label));
  assert.match(audit,/source missing/);
  const chain = render(RegistryPanel,{isError:true,mode:"historical",runtime});
  assert.doesNotMatch(chain,/DEMO MAPPING/);
  for (const value of [runtime.last_publish_attempt_at,runtime.last_published_observation_ts,runtime.last_publish_tx_hash,runtime.last_publish_error]) assert.ok(chain.includes(value));
});
