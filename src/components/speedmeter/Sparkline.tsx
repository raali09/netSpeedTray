"use client";

// نمودار خطی سبک SVG — برای نمایش سری‌های زمانی سرعت و پینگ.
// جهت نمودار LTR است (زمان از چپ به راست جریان دارد) حتی در صفحهٔ RTL.

import { useId } from "react";

interface SparklineProps {
  values: number[];
  color?: string;
  height?: number;
  max?: number;
  className?: string;
  /** مساحت زیر خط پر شود */
  area?: boolean;
  /** خط چین برای داده‌های قدیمی */
  emptyText?: string;
}

export function Sparkline({
  values,
  color = "#22d3ee",
  height = 56,
  max,
  className,
  area = true,
  emptyText = "در انتظار داده…",
}: SparklineProps) {
  const gid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const W = 240;
  const H = height;
  const PAD = 3;

  const data = values.filter((v) => Number.isFinite(v));
  if (data.length < 2) {
    return (
      <div
        dir="ltr"
        className={`flex items-center justify-center text-[11px] text-muted-foreground/70 ${className ?? ""}`}
        style={{ height: H }}
        role="img"
        aria-label={emptyText}
      >
        {emptyText}
      </div>
    );
  }

  const yMax = Math.max(max ?? 0, ...data) * 1.08 || 1;
  const x = (i: number) => PAD + (i / (data.length - 1)) * (W - 2 * PAD);
  const y = (v: number) => H - PAD - (v / yMax) * (H - 2 * PAD);

  const path = data.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const areaPath = `${path} L${x(data.length - 1).toFixed(1)},${H - PAD} L${x(0).toFixed(1)},${H - PAD} Z`;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={`w-full ${className ?? ""}`}
      style={{ height: H, direction: "ltr" }}
      role="img"
      aria-label="نمودار"
    >
      <defs>
        <linearGradient id={`sg-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {area && <path d={areaPath} fill={`url(#sg-${gid})`} />}
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={x(data.length - 1)} cy={y(data[data.length - 1])} r="2.6" fill={color}>
        <animate attributeName="opacity" values="1;0.3;1" dur="1.4s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
}
