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
      className={`card-shadow rounded-2xl bg-white p-6 ${className}`}
      style={{ border: "1px solid var(--color-line)" }}
    >
      {(title || right) && (
        <header className="mb-5 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {subtitle && (
              <p className="mt-0.5 text-sm" style={{ color: "var(--color-ink-dim)" }}>
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
      className="rounded-xl px-4 py-3.5"
      style={{ background: "var(--color-panel-2)", border: "1px solid var(--color-line)" }}
    >
      <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--color-ink-dim)" }}>
        {label}
        {hint && (
          <span
            title={hint}
            className="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full text-[9px]"
            style={{ background: "var(--color-line)", color: "var(--color-ink-dim)" }}
          >
            i
          </span>
        )}
      </div>
      <div className="tnum mt-1.5 text-3xl font-semibold" style={{ color: accent ?? "var(--color-ink)" }}>
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
