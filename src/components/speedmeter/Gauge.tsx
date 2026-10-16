"use client";

// عقربهٔ نیم‌دایره‌ای سرعت — عدد بزرگ در مرکز و قوس پرشونده با مقیاس خودکار.

import { faFormat, niceScaleMax } from "@/lib/speedtest";

interface GaugeProps {
  /** مقدار فعلی (Mbps) */
  value: number;
  /** رنگ قوس و عدد */
  color?: string;
  /** برچسب فاز بالای عدد */
  label?: string;
  /** مقدار میانگین برای نمایش کوچک زیر عدد */
  avg?: number;
  /** مقدار حداکثری */
  max?: number;
}

export function Gauge({ value, color = "#22d3ee", label, avg, max }: GaugeProps) {
  const scaleMax = niceScaleMax(Math.max(value, max ?? 0, 1));
  const clamped = Math.max(0, Math.min(value, scaleMax));
  const pct = (clamped / scaleMax) * 100;

  // قوس نیم‌دایره از ۱۸۰° تا ۰°
  const R = 80;
  const cx = 100;
  const cy = 96;
  const arc = (startPct: number, endPct: number) => {
    const a0 = Math.PI * (1 - startPct / 100);
    const a1 = Math.PI * (1 - endPct / 100);
    const p0 = { x: cx + R * Math.cos(a0), y: cy - R * Math.sin(a0) };
    const p1 = { x: cx + R * Math.cos(a1), y: cy - R * Math.sin(a1) };
    const large = endPct - startPct > 50 ? 1 : 0;
    return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
  };

  const track = arc(0, 100);
  const fillPct = pct;
  const valueArc = fillPct > 0.5 ? arc(0, fillPct) : "";

  // درجه‌بندی — کلید = درصد (همیشه یکتا)، برچسب = مقدار با ارقام اعشاری هوشمند
  const ticks = [0, 25, 50, 75, 100].map((p) => {
    const a = Math.PI * (1 - p / 100);
    const v = (p / 100) * scaleMax;
    const label = scaleMax >= 4 ? Math.round(v).toString() : String(Math.round(v * 100) / 100);
    return {
      key: p,
      label,
      x: cx + (R + 12) * Math.cos(a),
      y: cy - (R + 12) * Math.sin(a) + 3,
      anchor: (p === 0 ? "end" : p === 100 ? "start" : "middle") as "end" | "start" | "middle",
    };
  });

  return (
    <div dir="ltr" className="w-full max-w-[340px] mx-auto select-none">
      <svg viewBox="0 0 200 118" className="w-full h-auto overflow-visible">
        <path d={track} fill="none" stroke="#1B2733" strokeWidth="12" strokeLinecap="round" />
        {valueArc && (
          <path
            d={valueArc}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            style={{
              transition: "d 0.18s linear, stroke 0.3s",
              filter: `drop-shadow(0 0 6px ${color}55)`,
            }}
          />
        )}
        {ticks.map((t) => (
          <text
            key={t.key}
            x={t.x}
            y={t.y}
            textAnchor={t.anchor}
            fontSize="8"
            fill="#8290A0"
            className="tnum"
          >
            {t.label}
          </text>
        ))}
      </svg>
      <div className="-mt-[72px] pb-2 text-center" dir="rtl">
        {label && (
          <div className="text-[11px] font-medium text-muted-foreground mb-0.5">{label}</div>
        )}
        <div className="tnum text-4xl font-extrabold leading-none" style={{ color }}>
          {faFormat(clamped, 1)}
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground tnum">
          Mbps
          {typeof avg === "number" && Number.isFinite(avg) && (
            <span className="mx-1.5 opacity-50">|</span>
          )}
          {typeof avg === "number" && Number.isFinite(avg) && (
            <span>
              میانگین: <span className="tnum">{faFormat(avg, 1)}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
