import { Panel } from "../components/ui";

// X Layer machine interface. Publication returns 503 until contracts deploy; we
// explain what it will do rather than showing a cryptic status.
export function RegistryPanel() {
  return (
    <Panel title="Share the verdict onchain" subtitle="So lending protocols can act on it automatically">
      <ol className="space-y-2.5">
        <Step n={1} done>Valtide produces the verdict (above)</Step>
        <Step n={2}>Publish it to the X Layer registry onchain</Step>
        <Step n={3}>Protocols read the verdict and apply their own policy — no trust in Valtide's servers needed</Step>
      </ol>

      <div
        className="mt-4 flex items-center gap-2.5 rounded-lg px-3 py-2.5"
        style={{ background: "var(--color-inconclusive-soft)", border: "1px solid var(--color-inconclusive-line)" }}
      >
        <span className="inline-flex h-2 w-2 rounded-full" style={{ background: "var(--color-inconclusive)" }} aria-hidden />
        <span className="text-sm" style={{ color: "var(--color-inconclusive)" }}>
          <strong>Preview</strong> — the X Layer contracts aren't deployed yet, so publishing is disabled.
        </span>
      </div>

      <button
        disabled
        className="mt-3 w-full cursor-not-allowed rounded-lg py-2 text-sm font-medium"
        style={{ background: "var(--color-panel-2)", color: "var(--color-muted)", border: "1px solid var(--color-line)" }}
      >
        Publish onchain (coming soon)
      </button>
    </Panel>
  );
}

function Step({ n, children, done }: { n: number; children: React.ReactNode; done?: boolean }) {
  return (
    <li className="flex items-start gap-3 text-sm">
      <span
        className="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full text-xs font-bold"
        style={
          done
            ? { background: "var(--color-supported)", color: "#fff" }
            : { background: "var(--color-panel-2)", color: "var(--color-ink-dim)", border: "1px solid var(--color-line)" }
        }
      >
        {done ? "✓" : n}
      </span>
      <span style={{ color: "var(--color-ink-dim)" }}>{children}</span>
    </li>
  );
}
