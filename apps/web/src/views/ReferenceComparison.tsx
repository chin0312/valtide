import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";
import { referenceOutsideBand } from "../lib/scale";

// Makes disagreement obvious by plotting every price on one confidence-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const outside = referenceOutsideBand(r);
  return (
    <Panel title="How the prices compare" subtitle="Every price shown against Valtide's confidence range">
      <ReferenceNumberLine r={r} />
      <p
        className="mt-3 rounded-sm px-3 py-2 text-xs"
        style={{
          background: "var(--color-panel-2)",
          color: "var(--color-ink-dim)",
          border: "1px solid var(--color-line)",
        }}
      >
        {r.reference_under_test == null
          ? "No reference price is available at this step, so there is nothing to compare."
          : outside
            ? "The reference price falls outside the model's confidence range."
            : "The reference price falls inside the model's confidence range."}
      </p>
    </Panel>
  );
}
