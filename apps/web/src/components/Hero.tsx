import { useEffect, useRef } from "react";

type LineName = "real" | "valtide" | "token";
type Point = { x: number; y: number };
type Lines = Record<LineName, Point[]>;

const COLORS = {
  real: "#d8dee6",
  valtide: "#91b9ca",
  token: "#1dd3b0",
  calm: [29, 211, 176],
  tension: [213, 122, 222],
} as const;

export function Hero() {
  const heroRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const realLabelRef = useRef<HTMLDivElement>(null);
  const valtideLabelRef = useRef<HTMLDivElement>(null);
  const tokenLabelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const heroNode = heroRef.current;
    const canvasNode = canvasRef.current;
    const realLabelNode = realLabelRef.current;
    const valtideLabelNode = valtideLabelRef.current;
    const tokenLabelNode = tokenLabelRef.current;
    if (!heroNode || !canvasNode || !realLabelNode || !valtideLabelNode || !tokenLabelNode) return;

    const drawingNode = canvasNode.getContext("2d");
    if (!drawingNode) return;
    const hero: HTMLElement = heroNode;
    const canvas: HTMLCanvasElement = canvasNode;
    const drawing: CanvasRenderingContext2D = drawingNode;
    const realLabel: HTMLDivElement = realLabelNode;
    const valtideLabel: HTMLDivElement = valtideLabelNode;
    const tokenLabel: HTMLDivElement = tokenLabelNode;

    const labels: Record<LineName, HTMLDivElement> = { real: realLabel, valtide: valtideLabel, token: tokenLabel };
    const labelPositions: Record<LineName, number | null> = { real: null, valtide: null, token: null };
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let lineHeadX = 0;
    let gap = 0.18;
    let pointerGap = 0.18;
    let lastPointerMove = -Infinity;
    let lastFrame = performance.now();
    let animationFrame = 0;
    let visible = true;
    let disposed = false;

    function clamp(value: number, minimum = 0, maximum = 1) {
      return Math.max(minimum, Math.min(maximum, value));
    }

    function smoothstep(value: number) {
      const x = clamp(value);
      return x * x * (3 - 2 * x);
    }

    function mixColor(from: readonly number[], to: readonly number[], amount: number, alpha = 1) {
      const channel = (index: number) => Math.round(from[index] + (to[index] - from[index]) * amount);
      return `rgba(${channel(0)}, ${channel(1)}, ${channel(2)}, ${alpha})`;
    }

    function envelope(u: number) {
      return smoothstep((u - 0.12) / 0.82);
    }

    function baseWave(u: number, time: number) {
      return Math.sin(u * 6.1 + time * 0.00038) * 8 + Math.sin(u * 15.3 - time * 0.00064) * 3.5;
    }

    function divergenceShape(u: number) {
      return envelope(u) * (0.82 + Math.sin(u * 4.2 - 0.4) * 0.13 + Math.sin(u * 9.8) * 0.05);
    }

    function valuesAt(u: number, time: number) {
      const baselineRatio = width < 760 ? 0.68 : 0.58;
      const baseline = height * baselineRatio + baseWave(u, time);
      const separation = Math.min(height * (width < 760 ? 0.3 : 0.38), 350) * gap * divergenceShape(u);
      const real = baseline - separation * 0.42 + Math.sin(u * 9.3 + time * 0.00042) * 3;
      const token = baseline + separation * 0.58 + Math.sin(u * 11.8 - time * 0.00072) * 5;
      const valtide = real + (token - real) * 0.48 + Math.sin(u * 8.4 + time * 0.00051) * 2.5;
      return { real, valtide, token };
    }

    function sampleLines(time: number): Lines {
      const samples = Math.max(110, Math.ceil(lineHeadX / 7));
      const lines: Lines = { real: [], valtide: [], token: [] };
      for (let index = 0; index <= samples; index += 1) {
        const u = index / samples;
        const x = u * lineHeadX;
        const values = valuesAt(u, time);
        lines.real.push({ x, y: values.real });
        lines.valtide.push({ x, y: values.valtide });
        lines.token.push({ x, y: values.token });
      }
      return lines;
    }

    function trace(points: Point[], reverse = false) {
      const sequence = reverse ? [...points].reverse() : points;
      sequence.forEach((point, index) => {
        if (index === 0) drawing.moveTo(point.x, point.y);
        else drawing.lineTo(point.x, point.y);
      });
    }

    function drawGap(lines: Lines) {
      const tension = smoothstep((gap - 0.16) / 0.72);
      const fill = drawing.createLinearGradient(0, 0, lineHeadX, 0);
      fill.addColorStop(0, "rgba(29, 211, 176, 0)");
      fill.addColorStop(0.25, mixColor(COLORS.calm, COLORS.tension, tension, 0.025 + gap * 0.035));
      fill.addColorStop(1, mixColor(COLORS.calm, COLORS.tension, tension, 0.08 + gap * 0.14));
      drawing.beginPath();
      trace(lines.real);
      trace(lines.token, true);
      drawing.closePath();
      drawing.fillStyle = fill;
      drawing.fill();

      drawing.save();
      drawing.strokeStyle = mixColor(COLORS.calm, COLORS.tension, tension, 0.06 + gap * 0.15);
      drawing.lineWidth = 1;
      for (let index = 18; index < lines.real.length - 10; index += 5) {
        const top = lines.real[index];
        const bottom = lines.token[Math.min(lines.token.length - 1, index + (index % 2 ? 1 : -1))];
        drawing.beginPath();
        drawing.moveTo(top.x, top.y + 4);
        drawing.lineTo(bottom.x, bottom.y - 4);
        drawing.stroke();
      }
      drawing.restore();
    }

    function drawLine(points: Point[], color: string, weight: number, glow: string) {
      const stroke = drawing.createLinearGradient(0, 0, lineHeadX, 0);
      stroke.addColorStop(0, `${color}22`);
      stroke.addColorStop(0.28, `${color}88`);
      stroke.addColorStop(0.76, color);
      stroke.addColorStop(1, color);
      drawing.save();
      drawing.beginPath();
      trace(points);
      drawing.strokeStyle = stroke;
      drawing.lineWidth = weight;
      drawing.lineCap = "round";
      drawing.lineJoin = "round";
      drawing.shadowColor = `${color}${glow}`;
      drawing.shadowBlur = 7;
      drawing.stroke();
      drawing.restore();
    }

    function drawRiders(points: Point[], time: number, color: string, speed: number) {
      drawing.save();
      drawing.fillStyle = color;
      drawing.shadowColor = color;
      drawing.shadowBlur = 5;
      for (let dot = 0; dot < 3; dot += 1) {
        const progress = (time * speed + dot * 0.28) % 1;
        const index = Math.floor((0.48 + progress * 0.48) * (points.length - 1));
        const point = points[index];
        drawing.globalAlpha = 0.35 + progress * 0.55;
        drawing.beginPath();
        drawing.arc(point.x, point.y, dot === 2 ? 2.4 : 1.7, 0, Math.PI * 2);
        drawing.fill();
      }
      drawing.restore();
    }

    function solveLabelPositions(time: number) {
      const values = valuesAt(1, time);
      const raw = [values.real, values.valtide, values.token];
      const spacing = width < 760 ? 21 : 26;
      const targets = [...raw];
      targets[1] = Math.max(targets[1], targets[0] + spacing);
      targets[2] = Math.max(targets[2], targets[1] + spacing);
      const recenter = (raw[0] + raw[1] + raw[2] - targets[0] - targets[1] - targets[2]) / 3;
      for (let index = 0; index < targets.length; index += 1) targets[index] += recenter;
      if (targets[0] < 20) {
        const shift = 20 - targets[0];
        for (let index = 0; index < targets.length; index += 1) targets[index] += shift;
      }
      if (targets[2] > height - 20) {
        const shift = targets[2] - (height - 20);
        for (let index = 0; index < targets.length; index += 1) targets[index] -= shift;
      }

      const names: LineName[] = ["real", "valtide", "token"];
      names.forEach((name, index) => {
        if (labelPositions[name] === null) labelPositions[name] = targets[index];
        labelPositions[name]! += (targets[index] - labelPositions[name]!) * 0.14;
        labels[name].style.left = `${lineHeadX + 15}px`;
        labels[name].style.top = `${labelPositions[name]}px`;
      });
      return labelPositions as Record<LineName, number>;
    }

    function drawDirectLabels(lines: Lines, positions: Record<LineName, number>) {
      const entries = [
        { points: lines.real, color: COLORS.real, y: positions.real },
        { points: lines.valtide, color: COLORS.valtide, y: positions.valtide },
        { points: lines.token, color: COLORS.token, y: positions.token },
      ];
      drawing.save();
      drawing.lineWidth = 1;
      drawing.lineCap = "round";
      entries.forEach((entry) => {
        const endpoint = entry.points[entry.points.length - 1];
        drawing.strokeStyle = `${entry.color}99`;
        drawing.beginPath();
        drawing.moveTo(endpoint.x, endpoint.y);
        drawing.lineTo(lineHeadX + 18, entry.y);
        drawing.stroke();
      });
      drawing.restore();
    }

    function draw(time: number) {
      drawing.clearRect(0, 0, width, height);
      const lines = sampleLines(time);
      drawGap(lines);
      drawLine(lines.real, COLORS.real, 2.2, "44");
      drawLine(lines.valtide, COLORS.valtide, 2.8, "55");
      drawLine(lines.token, COLORS.token, 2.4, "55");
      drawRiders(lines.real, time, COLORS.real, 0.000035);
      drawRiders(lines.valtide, time, COLORS.valtide, 0.000043);
      drawRiders(lines.token, time, COLORS.token, 0.000051);
      drawDirectLabels(lines, solveLabelPositions(time));
    }

    function resize() {
      const bounds = hero.getBoundingClientRect();
      width = bounds.width;
      const lowerBand = width < 760 ? 292 : 224;
      height = Math.max(320, bounds.height - lowerBand);
      lineHeadX = width * (width < 760 ? 0.72 : 0.84);
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      drawing.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      labelPositions.real = null;
      labelPositions.valtide = null;
      labelPositions.token = null;
      draw(performance.now());
    }

    function animate(time: number) {
      if (disposed) return;
      const elapsed = Math.min(64, time - lastFrame);
      lastFrame = time;
      if (visible) {
        const idle = time - lastPointerMove > 1600;
        const idleGap = 0.18 + (Math.sin(time * 0.00055 - 1.2) * 0.5 + 0.5) * 0.76;
        gap += ((idle ? idleGap : pointerGap) - gap) * Math.min(1, elapsed * 0.0055);
        draw(time);
      }
      animationFrame = requestAnimationFrame(animate);
    }

    function handlePointerMove(event: PointerEvent) {
      const bounds = hero.getBoundingClientRect();
      pointerGap = 0.05 + clamp((event.clientX - bounds.left) / Math.max(1, bounds.width)) * 0.94;
      lastPointerMove = performance.now();
    }

    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      if (visible && prefersReducedMotion) draw(0);
    }, { threshold: 0.05 });
    resizeObserver.observe(hero);
    intersectionObserver.observe(hero);
    hero.addEventListener("pointermove", handlePointerMove, { passive: true });
    resize();
    if (prefersReducedMotion) {
      gap = 0.72;
      draw(0);
    } else {
      animationFrame = requestAnimationFrame(animate);
    }

    return () => {
      disposed = true;
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      hero.removeEventListener("pointermove", handlePointerMove);
    };
  }, []);

  return (
    <section ref={heroRef} className="valtide-hero" aria-labelledby="valtide-hero-title">
      <header className="valtide-hero__nav">
        <a className="valtide-hero__brand" href="/" aria-label="Valtide home">
          <span className="valtide-logo-crop valtide-logo-crop--hero"><img src="/valtide-logo.jpg" alt="" /></span>
          <span>Valtide</span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#incident">Product</a>
          <a href="#method">Methodology</a>
          <a href="/docs">Docs</a>
        </nav>
        <a className="valtide-hero__nav-action" href="?view=console">Open console <span aria-hidden="true">↗</span></a>
      </header>

      <div className="valtide-hero__copy">
        <p className="valtide-hero__eyebrow">Independent valuation evidence for tokenized collateral</p>
        <h1 id="valtide-hero-title">When markets disagree,<br />know what the <span>evidence supports.</span></h1>
      </div>

      <div className="valtide-hero__motion" aria-label="Animated market divergence">
        <canvas ref={canvasRef} aria-hidden="true" />
        <div ref={realLabelRef} className="valtide-hero__label valtide-hero__label--real" aria-hidden="true"><i /><span>Real world</span></div>
        <div ref={valtideLabelRef} className="valtide-hero__label valtide-hero__label--valtide" aria-hidden="true"><i /><span>Valtide</span></div>
        <div ref={tokenLabelRef} className="valtide-hero__label valtide-hero__label--token" aria-hidden="true"><i /><span>Token</span></div>
      </div>

      <div className="valtide-hero__lower">
        <p className="valtide-hero__lede">Valtide challenges the reference a protocol relies on, quantifies uncertainty, and makes a standardized Evidence State usable by curator-defined policies on X Layer.</p>
        <div className="valtide-hero__actions">
          <a className="valtide-hero__action" href="#incident">Replay a divergence <span aria-hidden="true">↓</span></a>
          <a className="valtide-hero__secondary" href="?view=console">Open validation console <span aria-hidden="true">↗</span></a>
        </div>
      </div>

      <div className="valtide-hero__principles" aria-label="Product principles">
        <span>Independent challenger</span>
        <span>Calibrated uncertainty</span>
        <span>Curator-owned policy</span>
        <span>X Layer attestations</span>
      </div>

      <p className="sr-only">Three animated lines begin together and diverge across the screen. The real-world reference holds, the tokenized market moves away, and Valtide tracks between them. Move the pointer left or right to close or widen the gap.</p>
    </section>
  );
}
