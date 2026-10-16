"use client";

// پایش زنده — مشابه ویجت همیشه‌رویِ برنامهٔ اصلی، اما در وب:
//   • تأخیر (RTT) پیوسته هر ۲ ثانیه نمونه‌برداری و رسم می‌شود.
//   • «مانیتور زندهٔ سرعت» با دانلود دوره‌ای تکه‌های کوچک، سرعت واقعی جاری را
//     نشان می‌دهد.
// نکتهٔ کلیدی UX: حالت «بدون ترافیک» (اتصال برقرار، داده‌ای رد و بدل نمی‌شود)
// با حالت «اینترنت قطع است» (هیچ پاسخی از هیچ‌کجا نمی‌آید) کاملاً متمایز است.

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Sparkline } from "./Sparkline";
import type { NetworkStatus } from "@/hooks/use-network-status";
import { formatDataSize, formatMs, formatMbps } from "@/lib/speedtest";
import { cn } from "@/lib/utils";
import { Activity, RadioTower, WifiOff, Coffee, TrendingDown } from "lucide-react";

const MONITOR_CHUNK_BYTES = 512 * 1024;
const MONITOR_INTERVAL_MS = 2500;
const LIVE_HISTORY_CAP = 48;

export function LiveMonitorCard({ net }: { net: NetworkStatus }) {
  const [monitorOn, setMonitorOn] = useState(false);
  const [liveMbps, setLiveMbps] = useState<number | null>(null);
  const [liveHistory, setLiveHistory] = useState<number[]>([]);
  const [usedBytes, setUsedBytes] = useState(0);
  const [lastSampleAt, setLastSampleAt] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const monitorRef = useRef(false);
  const aliveRef = useRef(true);
  const onlineRef = useRef(net.isOnline);
  const sampleRef = useRef<() => void>(() => {});

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      monitorRef.current = false;
    };
  }, []);

  useEffect(() => {
    onlineRef.current = net.isOnline;
  }, [net.isOnline]);

  // حلقهٔ نمونه‌برداری — همیشه از طریق ref فراخوانی می‌شود تا از بسته‌شدن
  // کهنه (stale closure) در حلقهٔ تایمر در امان باشیم.
  sampleRef.current = async () => {
    if (monitorRef.current && onlineRef.current && aliveRef.current) {
      const t0 = performance.now();
      try {
        const res = await fetch(`/api/speedtest/download?bytes=${MONITOR_CHUNK_BYTES}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error("bad status");
        const buf = await res.arrayBuffer();
        const ms = performance.now() - t0;
        if (!aliveRef.current || !monitorRef.current) return;
        const mbps = ((buf.byteLength * 8) / 1e6) / (ms / 1000);
        setLiveMbps(mbps);
        setUsedBytes((b) => b + buf.byteLength);
        setLastSampleAt(Date.now());
        setLiveHistory((prev) => {
          const next = [...prev, mbps];
          return next.length > LIVE_HISTORY_CAP ? next.slice(-LIVE_HISTORY_CAP) : next;
        });
      } catch {
        if (aliveRef.current) setLiveMbps(null);
      }
    }
    if (monitorRef.current && aliveRef.current) {
      timerRef.current = setTimeout(() => void sampleRef.current(), MONITOR_INTERVAL_MS);
    }
  };

  useEffect(() => {
    monitorRef.current = monitorOn;
    if (monitorOn) {
      void sampleRef.current();
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      setLiveMbps(null);
      setLiveHistory([]);
      setUsedBytes(0);
      setLastSampleAt(null);
    }
  }, [monitorOn]);

  // با قطع اینترنت، نمونه‌برداری متوقف می‌شود (تا داده هدر نرود)
  useEffect(() => {
    if (!net.isOnline && monitorOn) setMonitorOn(false);
  }, [net.isOnline]);

  const pingValues = net.pingHistory.map((p) => p.ms);
  const pingAvg =
    pingValues.length > 0
      ? pingValues.reduce((a, b) => a + b, 0) / pingValues.length
      : null;
  const pingMin = pingValues.length > 0 ? Math.min(...pingValues) : null;

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Activity className="size-4 text-emerald-400" />
          پایش زندهٔ شبکه
        </CardTitle>
        <CardDescription className="text-xs">
          وضعیت اتصال و تأخیر لحظه‌ای — بدون نیاز به اجرای آزمون
        </CardDescription>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-4">
        {/* نوار وضعیت اتصال */}
        <div
          className={cn(
            "rounded-lg border px-3 py-2.5 flex items-center justify-between gap-2",
            net.state === "online" && "bg-emerald-500/[0.07] border-emerald-500/25",
            net.state === "checking" && "bg-slate-500/[0.07] border-slate-500/25",
            net.state === "server-down" && "bg-amber-500/[0.07] border-amber-500/30",
            net.state === "offline" && "bg-rose-500/[0.09] border-rose-500/35"
          )}
          role="status"
          aria-live="polite"
        >
          <span className="flex items-center gap-2 text-sm font-semibold">
            {net.state === "online" && (
              <>
                <span className="size-2 rounded-full bg-emerald-400 live-dot" />
                <span className="text-emerald-400">متصل</span>
              </>
            )}
            {net.state === "checking" && (
              <>
                <span className="size-2 rounded-full bg-slate-400 live-dot" />
                <span className="text-slate-300">در حال بررسی…</span>
              </>
            )}
            {net.state === "server-down" && (
              <>
                <RadioTower className="size-4 text-amber-400" />
                <span className="text-amber-400">سرور در دسترس نیست</span>
              </>
            )}
            {net.state === "offline" && (
              <>
                <WifiOff className="size-4 text-rose-400" />
                <span className="text-rose-400">اینترنت قطع است</span>
              </>
            )}
          </span>
          <span className="text-[11px] text-muted-foreground tnum">
            تأخیر: {net.rtt != null ? `${formatMs(net.rtt)} ms` : "—"}
          </span>
        </div>

        {/* نمودار پینگ */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-medium text-muted-foreground">
              تأخیر زنده (۶۰ نمونهٔ اخیر)
            </span>
            {pingAvg != null && (
              <span className="text-[11px] text-muted-foreground tnum">
                میانگین {formatMs(pingAvg)} · کمینه {formatMs(pingMin ?? 0)} ms
              </span>
            )}
          </div>
          <div className="rounded-lg border bg-[#0D151D] px-2 pt-1" dir="ltr">
            <Sparkline
              values={pingValues}
              color="#34D399"
              height={54}
              emptyText="در انتظار اولین تپ قلب…"
            />
          </div>
        </div>

        {/* مانیتور زندهٔ سرعت */}
        <div className="rounded-lg border bg-[#0D151D] p-3 flex flex-col gap-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Switch
                id="live-monitor"
                checked={monitorOn}
                onCheckedChange={setMonitorOn}
                disabled={!net.isOnline}
                aria-label="مانیتور زندهٔ سرعت"
              />
              <label htmlFor="live-monitor" className="text-xs font-medium cursor-pointer">
                مانیتور زندهٔ سرعت
              </label>
              <Badge variant="outline" className="h-4 px-1.5 text-[9px] border-amber-500/40 text-amber-400">
                مصرف داده
              </Badge>
            </div>
            {monitorOn && usedBytes > 0 && (
              <span className="text-[10px] text-muted-foreground tnum">{formatDataSize(usedBytes)}</span>
            )}
          </div>

          <div dir="ltr" className={cn(!monitorOn && "opacity-40")}>
            <Sparkline
              values={liveHistory}
              color="#22D3EE"
              height={44}
              emptyText={
                monitorOn
                  ? "در حال نمونه‌برداری…"
                  : "برای دیدن سرعت جاری، مانیتور را روشن کنید"
              }
            />
          </div>

          <div className="flex items-center justify-between" aria-live="polite">
            <span className="text-xs text-muted-foreground">سرعت جاری:</span>
            {net.state === "offline" ? (
              <span className="flex items-center gap-1.5 text-xs font-bold text-rose-400">
                <WifiOff className="size-3.5" />
                اینترنت قطع است
              </span>
            ) : !monitorOn ? (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <TrendingDown className="size-3.5 opacity-50" />
                مانیتور خاموش است
              </span>
            ) : liveMbps == null ? (
              <span className="text-xs text-muted-foreground">در حال نمونه‌برداری…</span>
            ) : liveMbps < 0.05 && (Date.now() - (lastSampleAt ?? 0) < 10000) ? (
              <span className="flex items-center gap-1.5 text-xs text-slate-300">
                <Coffee className="size-3.5" />
                بدون ترافیک (اتصال برقرار است)
              </span>
            ) : (
              <span className="tnum text-sm font-bold text-cyan-400">
                {formatMbps(liveMbps)} Mbps
              </span>
            )}
          </div>
        </div>

        <p className="text-[10px] leading-5 text-muted-foreground/80">
          «بدون ترافیک» یعنی اتصال سالم است و فقط داده‌ای جابه‌جا نمی‌شود؛
          «اینترنت قطع است» یعنی هیچ پاسخی از هیچ میزبانی دریافت نمی‌شود.
        </p>
      </CardContent>
    </Card>
  );
}
