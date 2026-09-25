import type { EvidenceState } from "../api/types";
import { EVIDENCE } from "../lib/evidence";

export function EvidenceChip({
  state,
  size = "md",
}: {
  state: EvidenceState;
  size?: "md" | "lg";
}) {
  const s = EVIDENCE[state];
  const big = size === "lg";
  return (
    <span
      role="status"
      aria-label={`Evidence state: ${s.label}`}
      className={`inline-flex items-center gap-2 rounded font-mono font-medium tracking-[0.04em] ${
        big ? "px-3 py-1.5 text-sm" : "px-2 py-1 text-[10px]"
      }`}
      style={{ color: s.fg, background: s.soft, border: `1px solid ${s.line}` }}
    >
      <span
        aria-hidden
        className={`inline-flex items-center justify-center font-bold ${
          big ? "h-4 w-4 text-[11px]" : "h-3 w-3 text-[9px]"
        }`}
        style={{ color: s.fg }}
      >
        {s.icon}
      </span>
      {s.label}
    </span>
  );
}
