import type { ValuationResult } from "../api/types";
import { ReferenceNumberLine } from "../components/ReferenceNumberLine";
import { Panel } from "../components/ui";
import { referenceOutsideBand } from "../lib/scale";

// Makes disagreement obvious by plotting every price on an interval-relative
// axis. No composite score hides the outlier.
export function ReferenceComparison({ r }: { r: ValuationResult }) {
  const outside = referenceOutsideBand(r);
  return (
    <Panel title="How the prices compare" subtitle="Every price shown against Valtide's calibrated challenger interval">
      <ReferenceNumberLine r={r} />
      <p
        className="mt-3 rounded-lg px-3 py-2 text-sm"
        style={{
          background: outside ? "var(--color-challenged-soft)" : "var(--color-supported-soft)",
          color: outside ? "var(--color-challenged)" : "var(--color-supported)",
          border: `1px solid ${outside ? "var(--color-challenged-line)" : "var(--color-supported-line)"}`,
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
