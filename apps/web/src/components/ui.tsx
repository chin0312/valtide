import type { ReactNode } from "react";

export function Panel({
  title,
  subtitle,
  right,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`card-shadow rounded-sm p-5 ${className}`}
      style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}
    >
      {(title || right) && (
        <header className="mb-5 flex items-start justify-between gap-4 border-b pb-4" style={{ borderColor: "var(--color-line-subtle)" }}>
          <div>
            {title && <h2 className="text-[13px] font-medium uppercase tracking-[0.08em] text-ink">{title}</h2>}
            {subtitle && (
              <p className="mt-1 max-w-2xl text-xs" style={{ color: "var(--color-muted)" }}>
                {subtitle}
              </p>
            )}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

// A large, legible figure with a clear label above and optional context below.
export function Figure({
  label,
  value,
  sub,
  accent,
  hint,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: string;
  hint?: string;
}) {
  return (
    <div
      className="min-w-0 px-4 py-4"
      style={{ background: "var(--color-panel)", borderRight: "1px solid var(--color-line-subtle)" }}
    >
      <div className="flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.08em]" style={{ color: "var(--color-muted)" }}>
        {label}
        {hint && (
          <span
            title={hint}
            className="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full text-[9px]"
            style={{ border: "1px solid var(--color-line)", color: "var(--color-muted)" }}
          >
            i
          </span>
        )}
      </div>
      <div className="tnum mt-2 truncate text-[26px] font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>
        {value}
      </div>
      {sub != null && (
        <div className="tnum mt-1 text-xs" style={{ color: "var(--color-ink-dim)" }}>
          {sub}
        </div>
      )}
    </div>
  );
}
