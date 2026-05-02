"use client";

import { cn } from "@/lib/utils";

interface TrustScoreGaugeProps {
  score: number;
  size?: number;
  className?: string;
}

export function TrustScoreGauge({ score, size = 150, className }: TrustScoreGaugeProps) {
  const strokeW = 10;
  const r       = (size - strokeW * 2) / 2;
  const circ    = 2 * Math.PI * r;
  const offset  = circ - (score / 100) * circ;
  const cx      = size / 2;
  const cy      = size / 2;

  const color =
    score >= 70
      ? { stroke: "#10b981", text: "text-emerald-500" }
      : score >= 40
      ? { stroke: "#f59e0b", text: "text-amber-500" }
      : { stroke: "#f43f5e", text: "text-rose-500" };

  return (
    <div className={cn("flex items-center justify-center", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90 absolute inset-0">
          <circle
            cx={cx} cy={cy} r={r}
            fill="none"
            strokeWidth={strokeW}
            stroke="currentColor"
            className="text-muted/30"
          />
          <circle
            cx={cx} cy={cy} r={r}
            fill="none"
            strokeWidth={strokeW}
            stroke={color.stroke}
            strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={cn("text-3xl font-bold tabular-nums leading-none", color.text)}>
            {score}
          </span>
          <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-widest mt-1">
            Trust
          </span>
        </div>
      </div>
    </div>
  );
}
