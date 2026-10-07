export const documentationProfiles = {
  everyone: {
    id: "everyone",
    label: "New to Valtide",
    previewTitle: "Understand a validation result",
    previewBody: "Read Observed xStock, Valtide Fair Value, the Valuation Range, and the Evidence State.",
    action: "Open newcomer guide",
  },
  curators: {
    id: "curators",
    label: "Curators and risk teams",
    previewTitle: "Review a flagged price and policy response",
    previewBody: "Check Model Distance, X-Perp, Reason Codes, and freshness before applying your Policy Action.",
    action: "Open curator guide",
  },
  developers: {
    id: "developers",
    label: "Developers and integrators",
    previewTitle: "Integrate the API and X Layer attestation flow",
    previewBody: "Read asset-scoped API results and verify the matching X Layer attestation and policy.",
    action: "Open developer guide",
  },
  researchers: {
    id: "researchers",
    label: "Researchers",
    previewTitle: "Review the methodology",
    previewBody: "Review model inputs, calibration, historical evidence, and the limits of the current prototype.",
    action: "Open researcher guide",
  },
} as const;

export type DocumentationProfileId = keyof typeof documentationProfiles;
export const documentationProfileList = Object.values(documentationProfiles);
