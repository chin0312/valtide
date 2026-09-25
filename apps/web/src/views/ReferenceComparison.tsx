import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";
import { referenceOutsideBand } from "../lib/scale";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const outside = referenceOutsideBand(r);
  return (
    <Panel title="Reference comparison" subtitle="A band-relative view keeps small but decision-relevant differences legible.">
      <ReferenceNumberLine r={r} />
      <p
        className="mt-3 rounded-lg px-3 py-2 text-xs"
        style={{
          background: "var(--color-panel-2)",
          color: "var(--color-ink-dim)",
          border: "1px solid var(--color-line)",
          borderLeft: `2px solid ${outside ? "var(--color-challenged)" : "var(--color-supported)"}`,
        }}
      >
        {r.reference_under_test == null
          ? "No reference price is available at this step, so there is nothing to compare."
          : outside
            ? "The reference under test is outside Valtide's calibrated challenger interval. This is evidence for review, not proof that the reference is wrong."
            : "The reference under test is inside Valtide's calibrated challenger interval."}
      </p>
    </Panel>
  );
}
