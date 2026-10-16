"use client";

// نمای «ویجت» — حالت فشرده برای پنجرهٔ کوچکِ بدون قابِ الکترون
// (همیشه بالای صفحه). همان منطق سه‌سیگنالی تشخیص قطعی + سرعت
// زندهٔ واقعی از طریق دریافت دوره‌ای داده؛ فقط سبک‌تر و جمع‌وجورتر.

import { useEffect, useRef, useState } from "react";
import { useNetworkStatus } from "@/hooks/use-network-status";
import { Sparkline } from "./Sparkline";
import { faFormat, formatMbps } from "@/lib/speedtest";
import { Maximize2, Minus, Radar, RadioTower, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

const WIDGET_CHUNK_BYTES = 512 * 1024; // 512KB — نمونهٔ سبک برای پایش زنده
const WIDGET_INTERVAL_MS = 2400;
const WIDGET_HISTORY_CAP = 48;

export function WidgetView() {
  const net = useNetworkStatus();
  const [liveMbps, setLiveMbps] = useState<number | null>(null);
  const [liveHistory, setLiveHistory] = useState<number[]>([]);
  const [bridge, setBridge] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const aliveRef = useRef(true);
  const onlineRef = useRef(net.isOnline);
  const sampleRef = useRef<() => void>(() => {});

  // تشخیص پل الکترون (فقط داخل ویجت ویندوزی وجود دارد)
  useEffect(() => {
    setBridge(Boolean(window.speedmeter));
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    onlineRef.current = net.isOnline;
  }, [net.isOnline]);

  // حلقهٔ نمونه‌برداری — از طریق ref فراخوانی می‌شود تا از بسته‌شدن
  // کهنه (stale closure) در حلقهٔ تایمر در امان باشیم.
  sampleRef.current = async () => {
    if (onlineRef.current && aliveRef.current) {
      if (document.visibilityState !== "hidden") {
        const t0 = performance.now();
        try {
          const res = await fetch(`/api/speedtest/download?bytes=${WIDGET_CHUNK_BYTES}`, {
            cache: "no-store",
          });
          if (!res.ok) throw new Error("bad status");
          const buf = await res.arrayBuffer();
          const ms = performance.now() - t0;
          if (!aliveRef.current) return;
          const mbps = ((buf.byteLength * 8) / 1e6) / (ms / 1000);
          setLiveMbps(mbps);
          setLiveHistory((prev) => {
            const next = [...prev, mbps];
            return next.length > WIDGET_HISTORY_CAP ? next.slice(-WIDGET_HISTORY_CAP) : next;
          });
        } catch {
          if (aliveRef.current) setLiveMbps(null);
        }
      }
    }
    if (aliveRef.current && onlineRef.current) {
      timerRef.current = setTimeout(() => void sampleRef.current(), WIDGET_INTERVAL_MS);
    }
  };

  // با آنلاین‌بودن نمونه‌برداری فعال و با قطعی متوقف می‌شود
  useEffect(() => {
    if (net.isOnline) {
      void sampleRef.current();
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    setLiveMbps(null);
    setLiveHistory([]);
  }, [net.isOnline]);

  const offline = net.state === "offline";
  const pingText =
    net.state === "online" && net.rtt != null ? `${faFormat(net.rtt, 0)} ms` : "—";

  return (
    <div
      className={cn(
        "h-screen w-screen flex flex-col overflow-hidden app-bg",
        offline && "bg-rose-950/40"
      )}
      role="application"
      aria-label="ویجت آزمونگر سرعت"
    >
      {/* نوار بالا — ناحیهٔ کشیدن پنجره */}
      <div className="drag-region flex items-center justify-between gap-2 px-3 pt-2.5 pb-1.5">
        <div
          className="flex items-center gap-1.5 min-w-0 text-xs font-bold"
          role="status"
          aria-live="polite"
        >
          {net.state === "online" && (
            <>
              <span className="size-2 rounded-full bg-emerald-400 live-dot shrink-0" aria-hidden />
              <span className="text-emerald-400">متصل</span>
              <span className="text-muted-foreground font-normal">· {pingText}</span>
            </>
          )}
          {net.state === "checking" && (
            <>
              <Radar className="size-3.5 text-slate-300 animate-spin-slow" aria-hidden />
              <span className="text-slate-300">در حال بررسی…</span>
            </>
          )}
          {net.state === "server-down" && (
            <>
              <RadioTower className="size-3.5 text-amber-400" aria-hidden />
              <span className="text-amber-400">سرور در دسترس نیست</span>
            </>
          )}
          {offline && (
            <>
              <WifiOff className="size-3.5 text-rose-400" aria-hidden />
              <span className="text-rose-400">اینترنت قطع است</span>
            </>
          )}
        </div>

        {bridge && (
          <div className="flex items-center gap-1 no-drag">
            <button
              type="button"
              onClick={() => window.speedmeter?.openMain()}
              className="grid place-items-center size-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors"
              title="نمایش پنجرهٔ اصلی"
              aria-label="نمایش پنجرهٔ اصلی"
            >
              <Maximize2 className="size-3.5" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => window.speedmeter?.hideWidget()}
              className="grid place-items-center size-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors"
              title="مخفی کردن ویجت (از system tray دوباره ظاهر می‌شود)"
              aria-label="مخفی کردن ویجت"
            >
              <Minus className="size-3.5" aria-hidden />
            </button>
          </div>
        )}
      </div>

      {offline ? (
        /* حالت قطع کامل اینترنت — تمایز صریح از «بدون ترافیک» */
        <div className="flex-1 flex flex-col items-center justify-center gap-2 px-4 text-center">
          <WifiOff className="size-8 text-rose-400" aria-hidden />
          <div className="text-rose-300 font-extrabold text-sm">اینترنت قطع است</div>
          <p className="text-[10px] leading-4 text-rose-200/70 max-w-[240px]">
            پاسخی از سرور برنامه و میزبان‌های بیرونی دریافت نمی‌شود. «قطعی» با
            «بدون ترافیک» متفاوت است — در حالت بدون ترافیک، اتصال سالم است.
          </p>
          <button
            type="button"
            onClick={net.forceCheck}
            className="no-drag mt-1 inline-flex items-center gap-1.5 rounded-md border border-rose-400/40 px-2.5 py-1 text-[11px] text-rose-200 hover:bg-rose-500/10 transition-colors"
          >
            <Radar className="size-3" aria-hidden />
            بررسی مجدد
          </button>
        </div>
      ) : (
        <>
          {/* سرعت زندهٔ واقعی */}
          <div className="drag-region flex-1 flex flex-col justify-center gap-1 px-3">
            <div className="flex items-baseline gap-2">
              <span className="text-[28px] leading-none font-extrabold tnum text-foreground">
                {liveMbps != null ? formatMbps(liveMbps) : "—"}
              </span>
              <span className="text-[11px] text-muted-foreground font-semibold">Mbps</span>
            </div>
            <span className="text-[10px] text-muted-foreground/80">
              دانلود زنده — اندازه‌گیری با انتقال واقعی داده
            </span>
          </div>

          {/* نمودار کوچک سرعت */}
          <div className="px-2 pb-1">
            <Sparkline
              values={liveHistory}
              color="#22D3EE"
              height={44}
              emptyText="در انتظار نمونه…"
            />
          </div>

          {/* نوار پایین */}
          <div className="px-3 pb-2.5 pt-1.5 flex items-center justify-between gap-2 text-[10px] text-muted-foreground border-t border-border/40">
            <span className="tnum">
              پینگ: {pingText}
            </span>
            <span className="truncate">
              {net.state === "server-down"
                ? "اینترنت سالم است؛ مشکل از سرور برنامه است"
                : "آزمونگر سرعت"}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
