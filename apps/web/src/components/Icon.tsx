import type { ReactNode } from "react";

const paths: Record<string, ReactNode> = {
  signal: <><path d="M3 17V5M3 17h18" /><path d="m6 13 4-5 4 3 6-7" /></>,
  range: <><path d="M3 12h18M3 9v6M21 9v6" /><rect x="8" y="7" width="8" height="10" rx="2" /><path d="M12 5v14" /></>,
  shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
  evidence: <><circle cx="10" cy="10" r="6" /><path d="m14.5 14.5 5 5M7 10l2 2 4-4" /></>,
  basis: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2" /><circle cx="15" cy="17" r="2" /></>,
  record: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h4" /></>,
  chain: <><path d="m10 13 4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 3 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 1)" /></>,
  play: <path d="m8 4 12 8-12 8V4Z" />,
  pause: <><path d="M8 5v14M16 5v14" /></>,
  replay: <><path d="M3 10a9 9 0 1 1 2 8M3 4v6h6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  arrow: <path d="M4 12h16m-5-5 5 5-5 5" />,
  coin: <><circle cx="12" cy="12" r="8" /><path d="M14.5 9.5c-.5-.7-1.3-1-2.4-1-1.4 0-2.3.6-2.3 1.5 0 2.2 4.7 1 4.7 3.3 0 .9-.9 1.6-2.4 1.6-1.1 0-2-.4-2.6-1.2M12 7v10" /></>,
  model: <><path d="M4 18 9 12l4 3 7-9" /><circle cx="4" cy="18" r="1" /><circle cx="9" cy="12" r="1" /><circle cx="13" cy="15" r="1" /><circle cx="20" cy="6" r="1" /></>,
  residual: <><circle cx="12" cy="12" r="7" /><path d="M12 3v5M12 16v5M3 12h5M16 12h5" /><circle cx="12" cy="12" r="2" /></>,
  depth: <><path d="M5 6h14M3 12h18M6 18h12" /><path d="M8 4v4M16 10v4M11 16v4" /></>,
};

export type IconName = keyof typeof paths;

export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={`shrink-0 ${className}`}>{paths[name]}</svg>;
}
