import type { ValuationResult } from "../api/types";
import { money, sigma } from "../lib/format";
import { referenceOutsideBand, toBandUnits, unitsToFraction } from "../lib/scale";

interface Marker {
  key: string;
  label: string;
  price: number | null;
  color: string;
  lane: number; // fixed vertical lane so labels never collide, even at same x
  emphasize?: boolean;
}

// Plotted relative to the model's calibrated interval (FRONTEND_PLAN §4A): the range
// is a fixed visual width so the reference visibly crosses the edge as it
// diverges — a raw-price axis would hide the whole story inside a $0.90 window.
export function ReferenceNumberLine({ r }: { r: ValuationResult }) {
  const markers: Marker[] = [
    { key: "rut", label: "Reference under test", price: r.reference_under_test, lane: 2, emphasize: true, color: referenceOutsideBand(r) ? "var(--color-challenged)" : "var(--color-ink)" },
    { key: "token", label: "Tokenized market", price: r.token_price, lane: 1, color: "var(--color-token)" },
    { key: "trusted", label: "Last trusted price", price: r.last_trusted_reference, lane: -1, color: "var(--color-ink-dim)" },
    { key: "ext", label: "Constructed reference", price: r.external_constructed_reference, lane: -2, color: "#7c3aed" },
  ].filter((m) => m.price != null);

  const bandL = unitsToFraction(-1) * 100;
  const bandR = unitsToFraction(1) * 100;
  const AXIS_Y = 150;

  return (
    <div className="w-full">
      <div className="relative h-72 select-none">
        {/* the model's 90% calibrated interval — the only filled region */}
        <div
          className="absolute rounded-lg"
          style={{
            left: `${bandL}%`,
            width: `${bandR - bandL}%`,
            top: AXIS_Y - 24,
            height: 48,
            background: "var(--color-supported-soft)",
            border: "1px solid var(--color-supported-line)",
          }}
        />
        <BoundaryLine leftPct={bandL} axisY={AXIS_Y} />
        <BoundaryLine leftPct={bandR} axisY={AXIS_Y} />
        <div className="absolute left-0 right-0 h-px" style={{ top: AXIS_Y, background: "var(--color-line)" }} />

        <UnitTick u={0} axisY={AXIS_Y} label="fair value" strong />
        <UnitTick u={-1} axisY={AXIS_Y} label="range edge" />
        <UnitTick u={1} axisY={AXIS_Y} label="range edge" />

        {markers.map((m) => (
          <MarkerPin key={m.key} m={m} r={r} axisY={AXIS_Y} leftPct={unitsToFraction(toBandUnits(m.price as number, r)) * 100} />
        ))}
      </div>
      <p className="mt-2 text-center text-xs" style={{ color: "var(--color-ink-dim)" }}>
        Shaded band = Valtide's 90% calibrated interval. A reference outside it is a diagnostic signal, not a universal price verdict.
      </p>
    </div>
  );
}

function BoundaryLine({ leftPct, axisY }: { leftPct: number; axisY: number }) {
  return (
    <div
      className="absolute w-px"
      style={{ left: `${leftPct}%`, top: axisY - 32, height: 64, background: "var(--color-supported-line)" }}
    />
  );
}

function UnitTick({ u, axisY, label, strong }: { u: number; axisY: number; label: string; strong?: boolean }) {
  return (
    <div className="absolute flex flex-col items-center" style={{ left: `${unitsToFraction(u) * 100}%`, top: axisY + 6, transform: "translateX(-50%)" }}>
      <div className="w-px" style={{ height: 8, background: strong ? "var(--color-supported)" : "var(--color-line)" }} />
      <span className="mt-1 text-[11px]" style={{ color: strong ? "var(--color-supported)" : "var(--color-muted)" }}>{label}</span>
    </div>
  );
}

function MarkerPin({ m, r, axisY, leftPct }: { m: Marker; r: ValuationResult; axisY: number; leftPct: number }) {
  const isRut = m.key === "rut";
  const z = isRut ? r.standardized_deviation : null;
  const LABEL_H = 34;
  const above = m.lane > 0;
  const magnitude = Math.abs(m.lane);
  const labelY = axisY + (above ? -1 : 1) * (magnitude * 40 + 8) - (above ? LABEL_H : 0);
  const stemTop = above ? labelY + LABEL_H : axisY;
  const stemH = above ? axisY - (labelY + LABEL_H) : labelY - axisY;
  return (
    <div className="absolute" style={{ left: `${leftPct}%`, top: 0, transform: "translateX(-50%)" }}>
      <div className="absolute w-px" style={{ left: "50%", top: stemTop, height: Math.max(0, stemH), background: m.color, opacity: 0.3 }} />
      <div
        className="absolute rounded-full"
        style={{
          left: "50%",
          top: axisY,
          transform: "translate(-50%,-50%)",
          width: m.emphasize ? 18 : 13,
          height: m.emphasize ? 18 : 13,
          background: m.color,
          boxShadow: m.emphasize ? `0 0 0 5px ${isRut && referenceOutsideBand(r) ? "var(--color-challenged-soft)" : "rgba(0,0,0,0.06)"}` : "none",
          border: "2px solid white",
          zIndex: 10,
        }}
      />
      <div className="absolute w-36 text-center" style={{ left: "50%", top: labelY, transform: "translateX(-50%)" }}>
        <div className={`text-xs ${m.emphasize ? "font-semibold" : "font-medium"}`} style={{ color: m.color }}>
          {m.label}
        </div>
        <div className="tnum text-xs font-medium text-ink">
          {money(m.price)}
          {isRut && z != null ? <span style={{ color: m.color }}> · {sigma(z)}</span> : null}
        </div>
      </div>
    </div>
  );
}
