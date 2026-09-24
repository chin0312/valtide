import type { EvidenceState, OnchainControlPlane, ValuationResult } from "../api/types";

export type OnchainSyncState = "SYNCED" | "BEHIND" | "NO_ATTESTATION" | "MISMATCH" | "UNAVAILABLE";

export interface OnchainSyncStatus {
  state: OnchainSyncState;
  operationalObservedAt: number | null;
  registryObservedAt: number | null;
  operationalEvidenceState: EvidenceState | null;
  registryEvidenceState: EvidenceState | null;
  detail: string;
}

function unixSeconds(timestamp: string): number | null {
  const milliseconds = Date.parse(timestamp);
  return Number.isFinite(milliseconds) ? Math.floor(milliseconds / 1000) : null;
}

/**
 * Compare the warmed operational result with the attestation currently read
 * from the Registry. Freshness answers "can this attestation still be used?";
 * sync answers "does it represent this operational observation?".
 */
export function deriveOnchainSync(
  operational?: ValuationResult,
  controlPlane?: OnchainControlPlane,
): OnchainSyncStatus {
  const operationalObservedAt = operational ? unixSeconds(operational.timestamp) : null;
  const registryObservedAt = controlPlane?.attestation?.observedAt ?? null;
  const operationalEvidenceState = operational?.evidence_state ?? null;
  const registryEvidenceState = controlPlane?.exists ? controlPlane.evidence_state : null;

  if (!operational || !controlPlane) {
    return {
      state: "UNAVAILABLE",
      operationalObservedAt,
      registryObservedAt,
      operationalEvidenceState,
      registryEvidenceState,
      detail: "Operational or Registry state is not available for comparison.",
    };
  }

  if (!controlPlane.exists || !controlPlane.attestation) {
    return {
      state: "NO_ATTESTATION",
      operationalObservedAt,
      registryObservedAt: null,
      operationalEvidenceState,
      registryEvidenceState: null,
      detail: "No Registry attestation exists for this asset/reference pair.",
    };
  }

  if (operationalObservedAt == null || registryObservedAt == null) {
    return {
      state: "MISMATCH",
      operationalObservedAt,
      registryObservedAt,
      operationalEvidenceState,
      registryEvidenceState,
      detail: "The two observations do not expose comparable timestamps.",
    };
  }

  if (registryObservedAt < operationalObservedAt) {
    return {
      state: "BEHIND",
      operationalObservedAt,
      registryObservedAt,
      operationalEvidenceState,
      registryEvidenceState,
      detail: "The Registry attestation is older than the latest operational result.",
    };
  }

  if (registryObservedAt > operationalObservedAt) {
    return {
      state: "MISMATCH",
      operationalObservedAt,
      registryObservedAt,
      operationalEvidenceState,
      registryEvidenceState,
      detail: "The Registry contains a different, newer operational generation.",
    };
  }

  if (registryEvidenceState !== operationalEvidenceState) {
    return {
      state: "MISMATCH",
      operationalObservedAt,
      registryObservedAt,
      operationalEvidenceState,
      registryEvidenceState,
      detail: "Timestamps match, but Registry and operational Evidence States disagree.",
    };
  }

  return {
    state: "SYNCED",
    operationalObservedAt,
    registryObservedAt,
    operationalEvidenceState,
    registryEvidenceState,
    detail: "The Registry attestation represents the current operational result.",
  };
}
