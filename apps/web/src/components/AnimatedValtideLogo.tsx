import { useState } from "react";

type AnimatedValtideLogoProps = {
  className?: string;
  label?: string;
};

export function AnimatedValtideLogo({ className = "", label }: AnimatedValtideLogoProps) {
  const [cycle, setCycle] = useState(0);

  return (
    <span
      className={`logo-motion-trigger ${className}`.trim()}
      onPointerEnter={() => setCycle((value) => value + 1)}
    >
      <span
        key={cycle}
        className="logo-motion-mark"
        role={label ? "img" : undefined}
        aria-label={label}
        aria-hidden={label ? undefined : true}
      >
        <span className="logo-motion-panel logo-motion-panel--left" />
        <span className="logo-motion-diamond" />
        <span className="logo-motion-panel logo-motion-panel--right" />
      </span>
    </span>
  );
}
