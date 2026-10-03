import type { OnchainPolicy, PolicyAction } from "../api/types";

export interface InstrumentPassportData {
  address: string;
  asset: string;
  network: string;
  priceExposure: "VERIFIED";
  shareholderRights: "NONE";
  dividendTreatment: "BALANCE ADJUSTMENT";
  redemption: "xSTOCKS WITHDRAWAL";
  collateralMatch: "INCONCLUSIVE";
}

export interface PolicyProposal {
  current: OnchainPolicy;
  proposed: OnchainPolicy;
  calldata: `0x${string}`;
}

export interface PolicyDiffRow {
  label: string;
  current: string;
  proposed: string;
  changed: boolean;
}

export const DEMO_PASSPORT_ADDRESS = "0x1111111111111111111111111111111111111111";

export const DEMO_PASSPORT: InstrumentPassportData = {
  address: DEMO_PASSPORT_ADDRESS,
  asset: "NVDAx",
  network: "X Layer",
  priceExposure: "VERIFIED",
  shareholderRights: "NONE",
  dividendTreatment: "BALANCE ADJUSTMENT",
  redemption: "xSTOCKS WITHDRAWAL",
  collateralMatch: "INCONCLUSIVE",
};

const CURRENT_POLICY: OnchainPolicy = {
  max_age: 900,
  on_supported: "ALLOW",
  on_inconclusive: "REQUIRE_REVIEW",
  on_challenged: "RESTRICT_NEW_RISK",
  on_stale: "REQUIRE_REVIEW",
};

const PROPOSED_POLICY: OnchainPolicy = {
  max_age: 600,
  on_supported: "ALLOW",
  on_inconclusive: "MONITOR",
  on_challenged: "RESTRICT_NEW_RISK",
  on_stale: "RESTRICT_NEW_RISK",
};

// ABI encoding of DemoCollateralVault.configurePolicy((600, ALLOW, MONITOR,
// RESTRICT_NEW_RISK, RESTRICT_NEW_RISK)). The selector is verified in tests.
export const POLICY_PROPOSAL: PolicyProposal = {
  current: CURRENT_POLICY,
  proposed: PROPOSED_POLICY,
  calldata: "0xf5b3942300000000000000000000000000000000000000000000000000000000000002580000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000030000000000000000000000000000000000000000000000000000000000000003",
};

const actionRows: Array<[string, PolicyAction, PolicyAction]> = [
  ["SUPPORTED", CURRENT_POLICY.on_supported, PROPOSED_POLICY.on_supported],
  ["INCONCLUSIVE", CURRENT_POLICY.on_inconclusive, PROPOSED_POLICY.on_inconclusive],
  ["CHALLENGED", CURRENT_POLICY.on_challenged, PROPOSED_POLICY.on_challenged],
  ["STALE", CURRENT_POLICY.on_stale, PROPOSED_POLICY.on_stale],
];

export const POLICY_DIFF_ROWS: PolicyDiffRow[] = [
  { label: "MAX AGE", current: `${CURRENT_POLICY.max_age}s`, proposed: `${PROPOSED_POLICY.max_age}s`, changed: true },
  ...actionRows.map(([label, current, proposed]) => ({ label, current, proposed, changed: current !== proposed })),
];

export const MODEL_EVIDENCE_SUMMARY = {
  model: "P1a-C v0.2.0",
  observations: 11_828,
  coverage: 0.9431,
  coverageTarget: 0.9,
  maeBps: 6.752,
  meanIntervalWidthBps: 37.0569,
  gaussianMeanIntervalWidthBps: 45.8905,
  intervalWidthReduction: 1 - (37.0569 / 45.8905),
  period: "June–September 2026",
  source: "valtide-quant-service-p1ac/evidence/p1a_c_report.json",
} as const;

export const CITI_MARKET_CONTEXT = {
  currentMarket: "$17B",
  baseCase2030: "$5.5T",
  publicEquityDemand: "$2.6T",
  sourceLabel: "Citi Institute · Tokenization 2030",
  sourceUrl: "https://www.citigroup.com/global/insights/tokenization-2030",
} as const;
