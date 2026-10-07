import { useEffect, useRef, type ReactNode } from "react";
import { MODEL_EVIDENCE_SUMMARY } from "../fixtures/prototypeData";
import { AnimatedValtideLogo } from "./AnimatedValtideLogo";

type LineName = "reference" | "valtide" | "token";
type Point = { x: number; y: number };
type Lines = Record<LineName, Point[]>;

const COLORS: Record<LineName, string> = {
  reference: "#d8dee6",
  valtide: "#91b9ca",
  token: "#1dd3b0",
};

function MetricInfo({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <span className="valtide-hero__proof-info">
      <button type="button" aria-label={label} aria-describedby={id}>i</button>
      <span id={id} role="tooltip" className="valtide-hero__proof-tooltip">{children}</span>
    </span>
  );
}

export function Hero() {
  const heroRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const referenceLabelRef = useRef<HTMLDivElement>(null);
  const valtideLabelRef = useRef<HTMLDivElement>(null);
  const tokenLabelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const hero = heroRef.current;
    const canvas = canvasRef.current;
    const referenceLabel = referenceLabelRef.current;
    const valtideLabel = valtideLabelRef.current;
    const tokenLabel = tokenLabelRef.current;
    if (!hero || !canvas || !referenceLabel || !valtideLabel || !tokenLabel) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const labels: Record<LineName, HTMLDivElement> = { reference: referenceLabel, valtide: valtideLabel, token: tokenLabel };
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let lineHeadX = 0;
    let frame = 0;
    let visible = true;
    let disposed = false;
    let gap = 0.24;

    function smoothstep(value: number) {
      const x = Math.max(0, Math.min(1, value));
      return x * x * (3 - 2 * x);
    }

    function envelope(value: number) {
      const x = Math.max(0, Math.min(1, (value - 0.12) / 0.82));
      return x * x * (3 - 2 * x);
    }

    function valuesAt(position: number, time: number) {
      const baseline = height * 0.8
        + Math.sin(position * 6.1 + time * 0.00025) * 7
        + Math.sin(position * 15.3 - time * 0.00042) * 3;
      const divergence = Math.min(height * 0.24, 185) * gap * envelope(position);
      const reference = baseline - divergence * 0.42;
      const token = baseline + divergence * 0.58 + Math.sin(position * 11.8 - time * 0.00048) * 3;
      const valtide = reference + (token - reference) * 0.48 + Math.sin(position * 8.4 + time * 0.00034) * 2;
      return { reference, valtide, token };
    }

    function sample(time: number): Lines {
      const count = Math.max(100, Math.ceil(lineHeadX / 8));
      const lines: Lines = { reference: [], valtide: [], token: [] };
      for (let index = 0; index <= count; index += 1) {
        const position = index / count;
        const values = valuesAt(position, time);
        (Object.keys(lines) as LineName[]).forEach((name) => lines[name].push({ x: position * lineHeadX, y: values[name] }));
      }
      return lines;
    }

    function trace(points: Point[], reverse = false) {
      const sequence = reverse ? [...points].reverse() : points;
      sequence.forEach((point, index) => index === 0 ? context!.moveTo(point.x, point.y) : context!.lineTo(point.x, point.y));
    }

    function drawLine(points: Point[], color: string, weight: number) {
      const stroke = context!.createLinearGradient(0, 0, lineHeadX, 0);
      stroke.addColorStop(0, `${color}12`);
      stroke.addColorStop(.24, `${color}5c`);
      stroke.addColorStop(.4, `${color}24`);
      stroke.addColorStop(.7, `${color}2c`);
      stroke.addColorStop(.84, `${color}a8`);
      stroke.addColorStop(1, color);
      context!.save();
      context!.beginPath();
      trace(points);
      context!.strokeStyle = stroke;
      context!.lineWidth = weight;
      context!.lineCap = "round";
      context!.lineJoin = "round";
      context!.shadowColor = `${color}44`;
      context!.shadowBlur = 7;
      context!.stroke();
      context!.restore();
    }

    function draw(time: number) {
      context!.clearRect(0, 0, width, height);
      const lines = sample(time);
      const tension = smoothstep((gap - .34) / .46);
      const fill = context!.createLinearGradient(0, 0, lineHeadX, 0);
      fill.addColorStop(0, "rgba(29, 211, 176, 0)");
      fill.addColorStop(.38, `rgba(29, 211, 176, ${.01 + tension * .018})`);
      fill.addColorStop(.72, `rgba(138, 98, 184, ${.025 + tension * .09})`);
      fill.addColorStop(1, `rgba(213, 122, 222, ${.06 + tension * .22})`);
      context!.beginPath();
      trace(lines.reference);
      trace(lines.token, true);
      context!.closePath();
      context!.fillStyle = fill;
      context!.fill();

      context!.save();
      context!.strokeStyle = `rgba(213, 122, 222, ${.04 + tension * .22})`;
      context!.lineWidth = 1;
      for (let index = Math.floor(lines.reference.length * .38); index < lines.reference.length - 3; index += 5) {
        const top = lines.reference[index];
        const bottom = lines.token[Math.min(lines.token.length - 1, index + (index % 2 ? 1 : -1))];
        context!.beginPath();
        context!.moveTo(top.x, top.y + 3);
        context!.lineTo(bottom.x, bottom.y - 3);
        context!.stroke();
      }
      context!.restore();

      drawLine(lines.reference, COLORS.reference, 2.1);
      drawLine(lines.valtide, COLORS.valtide, 2.7);
      drawLine(lines.token, COLORS.token, 2.3);

      const endpoints = valuesAt(1, time);
      const ordered: LineName[] = ["reference", "valtide", "token"];
      const positions = ordered.map((name) => endpoints[name]);
      const spacing = width < 760 ? 21 : 25;
      positions[1] = Math.max(positions[1], positions[0] + spacing);
      positions[2] = Math.max(positions[2], positions[1] + spacing);
      if (positions[2] > height - 20) {
        const shift = positions[2] - (height - 20);
        positions[0] -= shift;
        positions[1] -= shift;
        positions[2] -= shift;
      }
      ordered.forEach((name, index) => {
        labels[name].style.left = `${lineHeadX + 15}px`;
        labels[name].style.top = `${positions[index]}px`;
        const endpoint = lines[name][lines[name].length - 1];
        context!.beginPath();
        context!.moveTo(endpoint.x, endpoint.y);
        context!.lineTo(lineHeadX + 18, positions[index]);
        context!.strokeStyle = `${COLORS[name]}88`;
        context!.lineWidth = 1;
        context!.stroke();
      });
    }

    function resize() {
      const bounds = canvas!.parentElement?.getBoundingClientRect() ?? hero!.getBoundingClientRect();
      width = bounds.width;
      height = Math.max(220, bounds.height);
      lineHeadX = width * (width < 760 ? .72 : .84);
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas!.width = Math.round(width * ratio);
      canvas!.height = Math.round(height * ratio);
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      context!.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw(prefersReducedMotion ? 0 : performance.now());
    }

    function animate(time: number) {
      if (disposed) return;
      if (visible) {
        const cycle = (Math.sin(time * .00052 - 1.35) + 1) * .5;
        gap = .22 + smoothstep(cycle) * .66;
        draw(time);
      }
      frame = requestAnimationFrame(animate);
    }

    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; }, { threshold: .04 });
    resizeObserver.observe(hero);
    intersectionObserver.observe(hero);
    resize();
    if (prefersReducedMotion) {
      gap = .76;
      draw(0);
    } else {
      frame = requestAnimationFrame(animate);
    }

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
    };
  }, []);

  return (
    <section ref={heroRef} className="valtide-hero" aria-labelledby="valtide-hero-title">
      <MarketingHeader />

      <div className="valtide-hero__copy">
        <p className="valtide-hero__eyebrow">Independent reference validation for tokenized equity</p>
        <h1 id="valtide-hero-title">Take control of your protocol's<br /><span className="valtide-hero__title-accent">collateral risk.</span></h1>
        <p className="valtide-hero__lede">Compare the observed xStock price with Valtide Fair Value, a Valuation Range, and separately sourced X-Perp evidence. Protocols retain control of the Policy Actions they apply.</p>
        <div className="valtide-hero__actions">
          <a className="valtide-hero__action" href="?view=console">Open validation console <span aria-hidden="true">↗</span></a>
          <a className="valtide-hero__secondary" href="#incident">See how it works <span aria-hidden="true">↓</span></a>
        </div>
      </div>

      <div className="valtide-hero__motion" aria-label="Animated market divergence">
        <canvas ref={canvasRef} aria-hidden="true" />
        <div ref={referenceLabelRef} className="valtide-hero__label valtide-hero__label--reference" aria-hidden="true"><i /><span>X-Perp evidence</span></div>
        <div ref={valtideLabelRef} className="valtide-hero__label valtide-hero__label--valtide" aria-hidden="true"><i /><span>Valtide Fair Value</span></div>
        <div ref={tokenLabelRef} className="valtide-hero__label valtide-hero__label--token" aria-hidden="true"><i /><span>Observed xStock</span></div>
      </div>

      <div className="valtide-hero__proof" aria-label="NVDAx historical interval study">
        <div className="valtide-hero__proof-intro">
          <span className="valtide-hero__proof-heading">NVDAx historical interval study <MetricInfo id="historical-model-evidence-note" label="About this exposed NVDAx interval study">Exposed historical/development interval study for NVDAx using Valtide Model P1a-C v0.2.0, June–September 2026. Across 11,828 observations, intervals targeted 90% and showed 94.3% empirical coverage; mean interval width was 19% narrower than a conventional Gaussian range using the same point estimates. This evaluates interval construction—not price accuracy versus raw xStock, three-asset performance, Evidence State accuracy, or production performance. The exposed period is not an untouched test set.</MetricInfo></span>
        </div>
        <div><strong>{MODEL_EVIDENCE_SUMMARY.observations.toLocaleString("en-US")}</strong><span>NVDAx · P1a-C v0.2.0 observations</span></div>
        <div><strong>{(MODEL_EVIDENCE_SUMMARY.coverage * 100).toFixed(1)}%</strong><span>Empirical interval coverage</span><small>{(MODEL_EVIDENCE_SUMMARY.coverageTarget * 100).toFixed(0)}% target · NVDAx</small></div>
        <div><strong>{(MODEL_EVIDENCE_SUMMARY.intervalWidthReduction * 100).toFixed(0)}% narrower</strong><span>Mean interval width · same point estimates</span></div>
      </div>
    </section>
  );
}

export function MarketingHeader({ page = false }: { page?: boolean }) {
  return <header className={`valtide-hero__nav${page ? " valtide-hero__nav--page" : ""}`}>
    <a className="valtide-hero__brand" href="/" aria-label="Valtide home">
      <AnimatedValtideLogo className="valtide-logo-motion valtide-logo-motion--hero" />
      <span>Valtide</span>
    </a>
    <nav aria-label="Primary navigation">
      <a href="/#incident">Product</a>
      <a href="/methodology">Methodology</a>
      <a href="/docs">Docs</a>
    </nav>
    <a className="valtide-hero__nav-action" href="/?view=console">Open console <span aria-hidden="true">↗</span></a>
  </header>;
}
