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
      className={`inline-flex items-center gap-2 rounded-full font-semibold ${
        big ? "px-4 py-1.5 text-base" : "px-3 py-1 text-xs"
      }`}
      style={{ color: s.fg, background: s.soft, border: `1px solid ${s.line}` }}
    >
      <span
        aria-hidden
        className={`inline-flex items-center justify-center rounded-full font-bold text-white ${
          big ? "h-5 w-5 text-xs" : "h-4 w-4 text-[10px]"
        }`}
        style={{ background: s.fg }}
      >
        {s.icon}
      </span>
      {s.label}
    </span>
  );
}
