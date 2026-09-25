import { INTERNAL_REASON_CODES, reasonLabel } from "../lib/format";

const IMPORTANT = new Set(["REFERENCE_UNDER_TEST_OUTSIDE_INTERVAL", "COMPARATOR_UNAVAILABLE", "TOKEN_UNIT_SUSPECT", "STALE_REFERENCE"]);

export function ReasonCodes({ codes: allCodes }: { codes: string[] }) {
  const codes = allCodes.filter((c) => !INTERNAL_REASON_CODES.has(c));
  if (!codes.length)
    return (
      <span className="text-sm" style={{ color: "var(--color-ink-dim)" }}>
        No signals recorded.
      </span>
    );
  return (
    <ul className="flex flex-wrap gap-2">
      {codes.map((c) => {
        const key = IMPORTANT.has(c);
        return (
          <li
            key={c}
            title={c}
            className="rounded-sm px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.04em]"
            style={{
              background: key ? "var(--color-panel-2)" : "transparent",
              color: key ? "var(--color-ink)" : "var(--color-ink-dim)",
              border: "1px solid var(--color-line)",
            }}
          >
            {reasonLabel(c)}
          </li>
        );
      })}
    </ul>
  );
}
