import type { EvidenceState, ValuationResult } from "../api/types";
import { DASH } from "./format";

export const EVIDENCE_SEMANTICS_V2 = "p1a_xstock_band_with_xperp_review_corroboration_v2";
export const UNIFIED_REFERENCE_PROFILE = "unified_xstock_p1ac_xperp_evidence_v1";

export function isEvidenceStateV2(result: Pick<ValuationResult, "evidence_semantics">): boolean {
  return result.evidence_semantics === EVIDENCE_SEMANTICS_V2;
}

export function isXStockValidation(result: Pick<ValuationResult, "validation_target" | "evidence_semantics" | "reference_profile">): boolean {
  return result.validation_target === "xstock_observed_price"
    || result.reference_profile === "xstock_vs_p1ac_challenger"
    || isEvidenceStateV2(result);
}

export function validationTargetPrice(result: ValuationResult): number | null {
  return isXStockValidation(result) ? result.token_price : result.reference_under_test;
}

export interface EvidenceCopy {
  title: string;
  detail: string;
}

const V2_COPY: Record<EvidenceState, EvidenceCopy> = {
  SUPPORTED: {
    title: "Observed xStock Is Supported",
    detail: "P1a-C places the observed xStock in the SUPPORT band. Required market sources are available and quality checks pass.",
  },
  INCONCLUSIVE: {
    title: "Evidence Is Inconclusive",
    detail: "The signal is in the WATCH band, evidence conflicts, or a required source or quality check prevents a directional conclusion.",
  },
  CHALLENGED: {
    title: "Observed xStock Is Challenged",
    detail: "P1a-C shows REVIEW-level disagreement and exact-time X-Perp corroborates the challenger direction. This does not prove the observed xStock price is wrong.",
  },
};

const LEGACY_XSTOCK_COPY: Record<EvidenceState, EvidenceCopy> = {
  SUPPORTED: {
    title: "Model-Based Challenger Evidence Supports the Observed xStock",
    detail: "P1a-C assimilates this same xStock observation before comparison. This is model-based challenger evidence, not two fully independent observations; disagreement alone does not establish which price is correct.",
  },
  INCONCLUSIVE: {
    title: "Model-Based Challenger Evidence Needs Review",
    detail: "P1a-C assimilates this same xStock observation before comparison. The model-based evidence is not strong or consistent enough for a confident conclusion.",
  },
  CHALLENGED: {
    title: "Model-Based Challenger Evidence Challenges the Observed xStock",
    detail: "P1a-C assimilates this same xStock observation before comparison. This is not an independent-source test and does not prove which price is correct.",
  },
};

export function evidenceCopy(result: ValuationResult): EvidenceCopy {
  if (isEvidenceStateV2(result)) return V2_COPY[result.evidence_state];
  if (result.evidence_semantics) {
    return {
      title: `Recorded ${result.evidence_state.toLowerCase()} evidence`,
      detail: "This earlier observation is shown with the Evidence State and rule metadata recorded at the time. It has not been reclassified by the current Console.",
    };
  }
  if (result.reference_profile === "xstock_vs_p1ac_challenger") return LEGACY_XSTOCK_COPY[result.evidence_state];
  return {
    title: result.evidence_state === "SUPPORTED" ? "Evidence Supports the Reference"
      : result.evidence_state === "CHALLENGED" ? "Evidence Challenges the Reference" : "Evidence Needs Review",
    detail: "This earlier observation is shown with its recorded reference and Evidence State. It has not been reclassified by the current Console.",
  };
}

export function modelDistanceLabel(scoreName: string | null | undefined, score: number | null | undefined): string {
  if (score == null || !Number.isFinite(score)) return DASH;
  if (scoreName === "disagreement_z") return `${score.toFixed(1)}σ`;
  if (scoreName === "disagreement_bps") return `${score.toFixed(1)} bps`;
  return DASH;
}

export function peakModelDistance(results: ValuationResult[]): string {
  const scored = results.flatMap((result) => {
    const detector = result.challenger_detector;
    return detector?.score != null && Number.isFinite(detector.score)
      ? [{ scoreName: detector.score_name, score: Math.abs(detector.score) }]
      : [];
  });
  const scoreNames = new Set(scored.map(({ scoreName }) => scoreName));
  if (!scored.length || scoreNames.size !== 1) return DASH;
  const scoreName = scored[0].scoreName;
  return modelDistanceLabel(scoreName, Math.max(...scored.map(({ score }) => score)));
}

export function modelDependenceNote(result: ValuationResult): string {
  if (isEvidenceStateV2(result)) {
    return "P1a-C assimilates the current xStock observation before emitting its estimate. xStock-versus-P1a-C is model-based challenger evidence, not two fully independent observations. X-Perp/index is separately sourced market evidence; disagreement alone does not establish which price is correct.";
  }
  if (result.reference_profile === UNIFIED_REFERENCE_PROFILE) {
    return "This stored unified-profile observation retains the rule metadata available at the time. Its Evidence State is shown as recorded and is not recomputed by the Console.";
  }
  if (result.reference_profile === "legacy_xperp_vs_p1ac") {
    return "This stored legacy observation evaluates the separate OKX X-Perp index against its recorded P1a-C challenger. Its Evidence State is retained as recorded.";
  }
  if (result.reference_profile === "xstock_vs_p1ac_challenger") {
    return "P1a-C assimilates the current xStock observation before emitting its estimate. This is model-based challenger evidence, not two fully independent observations; disagreement alone does not establish which price is correct.";
  }
  return "This stored observation retains its original reference and Evidence State metadata.";
}
