import { POLICY_DIFF_ROWS, POLICY_PROPOSAL } from "../fixtures/prototypeData";
import { Panel } from "./ui";

export function PolicyFoundry() {
  return (
    <Panel
      title="Precomputed policy proposal"
      subtitle="Deterministic demo fixture · shown for review, not generated live."
      right={<span className="rounded px-2 py-1 text-[10px] uppercase tracking-[0.05em] text-muted" style={{ border: "1px solid var(--color-line)" }}>Not deployed</span>}
    >
      <div className="policy-terminal technical-mono rounded p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-3" style={{ borderColor: "rgba(184,199,194,.18)" }}>
          <span style={{ color: "var(--color-accent)" }}>$ valtide policy-proposal --fixture nvda-weekend</span>
          <span className="text-[10px] uppercase tracking-[0.06em]" style={{ color: "var(--color-muted)" }}>Read-only</span>
        </div>
        <div className="mt-3 grid grid-cols-[minmax(92px,.65fr)_minmax(0,1fr)_18px_minmax(0,1fr)] gap-x-2 border-b pb-2 text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)", borderColor: "rgba(184,199,194,.12)" }}>
          <span>Rule</span><span>Current</span><span /><span>Proposed</span>
        </div>
        <div>
          {POLICY_DIFF_ROWS.map((row) => <div key={row.label} className="grid grid-cols-[minmax(92px,.65fr)_minmax(0,1fr)_18px_minmax(0,1fr)] gap-x-2 border-b py-2" style={{ borderColor: "rgba(184,199,194,.09)" }}><span className="text-[10px]" style={{ color: "var(--color-muted)" }}>{row.label}</span><span className="break-words text-xs text-ink-dim">{row.current}</span><span aria-hidden style={{ color: row.changed ? "var(--color-accent)" : "var(--color-muted)" }}>→</span><strong className="break-words text-xs" style={{ color: row.changed ? "var(--color-accent)" : "var(--color-ink-dim)" }}>{row.proposed}</strong></div>)}
        </div>

        <div className="mt-4">
          <div className="mb-2 flex items-center justify-between gap-3"><span className="text-[10px] uppercase tracking-[0.05em]" style={{ color: "var(--color-muted)" }}>Unsigned calldata</span><span className="text-[10px] text-muted">Checked-in ABI fixture</span></div>
          <code className="block max-h-28 overflow-auto break-all rounded p-3 text-xs leading-5" style={{ color: "var(--color-series-valtide)", background: "#030506", border: "1px solid rgba(145,185,202,.25)" }}>{POLICY_PROPOSAL.calldata}</code>
        </div>
        <p className="mt-3 text-[11px] leading-5" style={{ color: "var(--color-muted)" }}>The calldata format matches the checked-in ABI fixture. It has not been simulated, signed, or submitted. The browser has no publisher key, vault-owner key, signing capability, or transaction-submission tool.</p>
      </div>

      <div role="note" className="mt-3 rounded px-4 py-3 text-center text-xs font-semibold uppercase tracking-[0.04em] text-ink-dim" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>No transaction capability in this prototype</div>
    </Panel>
  );
}
