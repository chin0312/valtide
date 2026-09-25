import { Panel } from "../components/ui";

// X Layer machine interface. Publication returns 503 until contracts deploy; we
// explain what it will do rather than showing a cryptic status.
export function RegistryPanel() {
  return (
    <Panel title="Onchain provenance" subtitle="Evidence computed; publication awaits deployment">
      <ol className="grid grid-cols-2 overflow-hidden rounded-sm" style={{ border: "1px solid var(--color-line)" }}>
        <Step n={1} done>Model run</Step>
        <Step n={2}>Attested</Step>
        <Step n={3}>Registry</Step>
        <Step n={4}>Risk guard</Step>
      </ol>

      <div
        className="mt-4 flex items-center gap-2.5 rounded-sm px-3 py-2.5"
        style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}
      >
        <span className="inline-flex h-2 w-2 rounded-full" style={{ background: "var(--color-muted)" }} aria-hidden />
        <span className="text-xs" style={{ color: "var(--color-ink-dim)" }}>
          <strong>Preview</strong> — the X Layer contracts aren't deployed yet, so publishing is disabled.
        </span>
      </div>

      <button
        disabled
        className="mt-3 w-full cursor-not-allowed rounded-sm py-2 text-xs font-medium"
        style={{ background: "var(--color-panel-2)", color: "var(--color-muted)", border: "1px solid var(--color-line)" }}
      >
        Publish onchain (coming soon)
      </button>
    </Panel>
  );
}

function Step({ n, children, done }: { n: number; children: React.ReactNode; done?: boolean }) {
  return (
    <li className="flex items-center gap-2 px-3 py-2.5 text-xs" style={{ borderRight: "1px solid var(--color-line-subtle)", borderBottom: "1px solid var(--color-line-subtle)" }}>
      <span
        className="inline-flex h-4 w-4 flex-none items-center justify-center rounded-full font-mono text-[9px] font-medium"
        style={
          done
            ? { background: "var(--color-accent-soft)", color: "var(--color-accent)", border: "1px solid var(--color-accent)" }
            : { background: "var(--color-panel-2)", color: "var(--color-ink-dim)", border: "1px solid var(--color-line)" }
        }
      >
        {done ? "✓" : n}
      </span>
      <span style={{ color: "var(--color-ink-dim)" }}>{children}</span>
    </li>
  );
}
