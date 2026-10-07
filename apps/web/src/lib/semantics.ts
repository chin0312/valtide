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
    title: "Observed xStock is supported",
    detail: "Model disagreement is low, exact-time X-Perp is available, and required quality checks pass.",
  },
  INCONCLUSIVE: {
    title: "Evidence is inconclusive",
    detail: "The result is in the watch band, or a required market check is unavailable, stale, ambiguous, or below the quality threshold.",
  },
  CHALLENGED: {
    title: "Observed xStock is challenged",
    detail: "Model disagreement is high, and exact-time X-Perp is closer to P1a-C than to xStock. Review the price before using it in a risk decision.",
  },
};

const LEGACY_XSTOCK_COPY: Record<EvidenceState, EvidenceCopy> = {
  SUPPORTED: {
    title: "Model-based challenger evidence supports the observed xStock",
    detail: "This earlier model-based result is shown as recorded and has not been reclassified.",
  },
  INCONCLUSIVE: {
    title: "Model-based challenger evidence needs review",
    detail: "This earlier model-based result is shown as recorded and has not been reclassified.",
  },
  CHALLENGED: {
    title: "Model-based challenger evidence challenges the observed xStock",
    detail: "This earlier model-based result is shown as recorded and has not been reclassified.",
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
    title: result.evidence_state === "SUPPORTED" ? "Evidence supports the reference"
      : result.evidence_state === "CHALLENGED" ? "Evidence challenges the reference" : "Evidence needs review",
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
