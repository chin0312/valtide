import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function Panel({ title, icon, subtitle, right, children, className = "" }: { title?: string; icon?: IconName; subtitle?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card-shadow rounded-[10px] p-5 ${className}`} style={{ background: "var(--color-panel)", border: "1px solid var(--color-line-subtle)" }}>
      {(title || right) && (
        <header className="mb-4 flex items-start justify-between gap-4 border-b pb-3" style={{ borderColor: "var(--color-line-subtle)" }}>
          <div>
            {title && <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em] text-ink">{icon && <Icon name={icon} className="text-ink-dim" />}{title}</h2>}
            {subtitle && <p className="mt-0.5 max-w-3xl text-xs" style={{ color: "var(--color-muted)" }}>{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Figure({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string; hint?: string }) {
  return (
    <div className="min-w-0 px-4 py-3.5" style={{ background: "var(--color-panel-2)", borderRight: "1px solid var(--color-line-subtle)" }}>
      <div className="eyebrow" style={{ color: "var(--color-muted)" }}>{label}</div>
      <div className="tnum mt-2 truncate text-[25px] font-medium tracking-[-0.04em]" style={{ color: accent ?? "var(--color-ink)" }}>{value}</div>
      {sub != null && <div className="tnum mt-1 truncate text-[11px]" style={{ color: "var(--color-ink-dim)" }}>{sub}</div>}
    </div>
  );
}
