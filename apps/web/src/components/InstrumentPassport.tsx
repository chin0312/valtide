import { useState, type FormEvent } from "react";
import { DEMO_PASSPORT, DEMO_PASSPORT_ADDRESS } from "../fixtures/prototypeData";
import { Panel } from "./ui";

const ADDRESS_PATTERN = /^0x[a-fA-F0-9]{40}$/;

type PassportStatus = "idle" | "invalid" | "unknown" | "resolved";

export function passportStatusFor(candidate: string): PassportStatus {
  const normalized = candidate.trim();
  if (!normalized) return "idle";
  if (!ADDRESS_PATTERN.test(normalized)) return "invalid";
  return normalized.toLowerCase() === DEMO_PASSPORT_ADDRESS.toLowerCase() ? "resolved" : "unknown";
}

export function InstrumentPassport({ initialAddress = "" }: { initialAddress?: string }) {
  const [address, setAddress] = useState(initialAddress);
  const [status, setStatus] = useState<PassportStatus>(() => passportStatusFor(initialAddress));

  function verify(candidate: string) {
    setStatus(passportStatusFor(candidate));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    verify(address);
  }

  function loadDemo() {
    setAddress(DEMO_PASSPORT_ADDRESS);
    setStatus("resolved");
  }

  return (
    <div className="mb-4">
      <Panel
        title="Token Rights Metadata Fixture"
        subtitle="Optional demo of how economic-rights metadata could be reviewed before price evidence."
        right={<span className="rounded px-2 py-1 text-[10px] uppercase tracking-[0.05em] text-muted" style={{ border: "1px solid var(--color-line)" }}>Precomputed · not live</span>}
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="passport-address">X Layer contract address</label>
          <input
            id="passport-address"
            value={address}
            onChange={(event) => { setAddress(event.target.value); setStatus("idle"); }}
            placeholder="Enter an X Layer contract address · 0x…"
            aria-describedby="passport-help passport-feedback"
            aria-invalid={status === "invalid"}
            className="technical-mono min-h-11 min-w-0 flex-1 rounded px-3 py-2 text-sm text-ink outline-none"
            style={{ background: "var(--color-panel-2)", border: `1px solid ${status === "invalid" ? "var(--color-line-strong)" : "var(--color-line)"}` }}
          />
          <button type="submit" className="min-h-11 rounded px-4 text-xs font-semibold" style={{ color: "#071006", background: "var(--color-accent)" }}>Check fixture</button>
          <button type="button" onClick={loadDemo} className="min-h-11 rounded px-4 text-xs font-medium text-ink" style={{ border: "1px solid var(--color-line)" }}>Load demo address</button>
        </form>
        <p id="passport-help" className="mt-2 text-[11px]" style={{ color: "var(--color-muted)" }}>This preloaded fixture illustrates rights metadata. It does not query the address or verify a live token.</p>

        <div id="passport-feedback" aria-live="polite">
          {status === "invalid" && <p role="alert" className="mt-3 rounded px-3 py-2 text-xs text-ink" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line-strong)" }}>Enter 0x followed by exactly 40 hexadecimal characters.</p>}
          {status === "unknown" && <p className="mt-3 rounded px-3 py-2 text-xs text-ink-dim" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>No verified passport fixture for this address. No collateral attributes have been inferred.</p>}
          {status === "resolved" && <PassportCard />}
        </div>
      </Panel>
    </div>
  );
}

function PassportCard() {
  const rows = [
    ["PRICE EXPOSURE", DEMO_PASSPORT.priceExposure, "verified"],
    ["SHAREHOLDER RIGHTS", DEMO_PASSPORT.shareholderRights, "mismatch"],
    ["DIVIDEND TREATMENT", DEMO_PASSPORT.dividendTreatment, "warning"],
    ["REDEMPTION", DEMO_PASSPORT.redemption, "warning"],
  ] as const;

  return (
    <section className="mt-4 rounded p-4" aria-label="Collateral Identity" style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-3" style={{ borderColor: "var(--color-line)" }}>
        <div><div className="eyebrow text-muted">Collateral Identity</div><div className="technical-mono mt-1 text-sm text-ink">{DEMO_PASSPORT.asset} · {DEMO_PASSPORT.network}</div></div>
        <span className="rounded px-2 py-1 text-[10px] font-medium uppercase tracking-[0.04em] text-ink-dim" style={{ border: "1px solid var(--color-line)", background: "var(--color-panel)" }}>RIGHTS PROFILE · DIFFERS FROM A SHARE</span>
      </div>
      <dl className="mt-3 grid gap-2 md:grid-cols-2">
        {rows.map(([label, value]) => <div key={label} className="flex min-w-0 items-center justify-between gap-4 rounded px-3 py-2" style={{ border: "1px solid var(--color-line)" }}><dt className="text-[10px] tracking-[0.05em] text-muted">{label}</dt><dd className="technical-mono break-words text-right text-sm font-semibold text-ink">{label === "PRICE EXPOSURE" ? `${value} · FIXTURE ASSERTION` : value}</dd></div>)}
      </dl>
      <div className="technical-mono mt-3 break-all text-sm" style={{ color: "var(--color-muted)" }}>{DEMO_PASSPORT.address}</div>
      <p className="mt-2 text-[10px] uppercase tracking-[0.05em] text-muted">Precomputed fixture · not live address resolution</p>
    </section>
  );
}
