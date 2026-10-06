export const documentationProfiles = {
  everyone: {
    id: "everyone",
    label: "New to Valtide",
    previewTitle: "Understand a validation result",
    previewBody: "Follow the reference, interval, Evidence State, reasons, policy, and freshness in the right order.",
    action: "Open newcomer guide",
  },
  curators: {
    id: "curators",
    label: "Curators and risk teams",
    previewTitle: "Investigate and govern",
    previewBody: "Separate evidence from policy, review divergence, and understand freshness before changing exposure.",
    action: "Open curator guide",
  },
  developers: {
    id: "developers",
    label: "Developers and integrators",
    previewTitle: "Consume Valtide evidence",
    previewBody: "Work with the API, ValidationRegistry, RiskGuard, and read-only attestation concepts.",
    action: "Open developer guide",
  },
  researchers: {
    id: "researchers",
    label: "Researchers",
    previewTitle: "Review the methodology",
    previewBody: "Inspect the information set, interval calibration, evaluation evidence, and limits of the current research prototype.",
    action: "Open researcher guide",
  },
} as const;

export type DocumentationProfileId = keyof typeof documentationProfiles;
export const documentationProfileList = Object.values(documentationProfiles);
