"use client";

// کارت آزمون سرعت — جریان کامل: پینگ → دانلود → آپلود.
// همهٔ اعداد از انتقال واقعی بایت‌ها به دست می‌آیند و سرعت لحظه‌ای با پنجرهٔ
// لغزان روی جریان خوانده می‌شود. در حالت قطع اینترنت دکمهٔ شروع قفل می‌شود.

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Gauge } from "./Gauge";
import { Sparkline } from "./Sparkline";
import type { NetworkStatus } from "@/hooks/use-network-status";
import {
  runDownloadPhase,
  runPingBurst,
  runUploadPhase,
  formatMbps,
  formatMs,
  formatDataSize,
  faFormat,
  type PingResult,
  type PhaseResult,
  type SpeedSample,
} from "@/lib/speedtest";
import { cn } from "@/lib/utils";
import {
  Download,
  Upload,
  Activity,
  Waves,
  Play,
  Square,
  CheckCircle2,
  WifiOff,
  Gauge as GaugeIcon,
  RefreshCw,
} from "lucide-react";

export interface TestOutcome {
  download: number;
  upload: number;
  ping: number;
  jitter: number;
}

type Phase = "idle" | "ping" | "download" | "upload" | "done" | "error";

interface SpeedTestCardProps {
  net: NetworkStatus;
  onResult: (outcome: TestOutcome) => Promise<void> | void;
}

const PHASE_STEPS: { key: Phase; label: string }[] = [
  { key: "ping", label: "پینگ" },
  { key: "download", label: "دانلود" },
  { key: "upload", label: "آپلود" },
];

export function SpeedTestCard({ net, onResult }: SpeedTestCardProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [instant, setInstant] = useState(0);
  const [avg, setAvg] = useState(0);
  const [phaseBytes, setPhaseBytes] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [spark, setSpark] = useState<SpeedSample[]>([]);
  const [ping, setPing] = useState<PingResult | null>(null);
  const [down, setDown] = useState<PhaseResult | null>(null);
  const [up, setUp] = useState<PhaseResult | null>(null);
  const [error, setError] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved-server" | "saved-local" | "failed">("idle");
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
    };
  }, []);

  const running = phase === "ping" || phase === "download" || phase === "upload";

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPhase("idle");
    setInstant(0);
    setSpark([]);
    setError("");
  }, []);

  const start = useCallback(async () => {
    if (running || !net.isOnline) return;
    const ctl = new AbortController();
    abortRef.current = ctl;
    setError("");
    setSaveState("idle");
    setPing(null);
    setDown(null);
    setUp(null);
    setSpark([]);
    setInstant(0);
    setAvg(0);

    try {
      // ---------- فاز ۱: پینگ ----------
      setPhase("ping");
      const p = await runPingBurst(6, undefined, ctl.signal);
      if (!mountedRef.current || ctl.signal.aborted) return;
      setPing(p);

      // ---------- فاز ۲: دانلود ----------
      if (ctl.signal.aborted) return;
      setPhase("download");
      setSpark([]);
      setPhaseBytes(0);
      const d = await runDownloadPhase({
        signal: ctl.signal,
        onProgress: ({ instantMbps, avgMbps, bytes, elapsedMs }) => {
          if (!mountedRef.current) return;
          setInstant(instantMbps);
          setAvg(avgMbps);
          setPhaseBytes(bytes);
          setElapsed(elapsedMs);
        },
      });
      if (!mountedRef.current || ctl.signal.aborted) return;
      setDown(d);
      setSpark(d.samples);

      // ---------- فاز ۳: آپلود ----------
      setPhase("upload");
      setInstant(0);
      setAvg(0);
      setPhaseBytes(0);
      setSpark([]);
      const u = await runUploadPhase({
        signal: ctl.signal,
        onProgress: ({ instantMbps, avgMbps, bytes, elapsedMs }) => {
          if (!mountedRef.current) return;
          setInstant(instantMbps);
          setAvg(avgMbps);
          setPhaseBytes(bytes);
          setElapsed(elapsedMs);
        },
      });
      if (!mountedRef.current || ctl.signal.aborted) return;
      setUp(u);
      setSpark(u.samples);

      // ---------- پایان ----------
      setPhase("done");
      setInstant(0);
      setSaveState("saving");
      try {
        await onResult({
          download: d.avgMbps,
          upload: u.avgMbps,
          ping: p.median,
          jitter: p.jitter,
        });
        if (mountedRef.current) setSaveState((s) => (s === "saving" ? "saved-server" : s));
      } catch {
        if (mountedRef.current) setSaveState("saved-local");
      }
    } catch (e) {
      if (!mountedRef.current) return;
      if (ctl.signal.aborted) return;
      setError(
        (e as Error)?.message?.includes("پاسخی")
          ? "سرور پاسخ نداد — اتصال را بررسی کنید"
          : "آزمون ناتمام ماند؛ اتصال شبکه دچار اختلال شد"
      );
      setPhase("error");
    } finally {
      if (abortRef.current === ctl) abortRef.current = null;
    }
  }, [net.isOnline, onResult, running]);

  const displayColor =
    phase === "upload" ? "#FBBF24" : phase === "download" ? "#22D3EE" : phase === "ping" ? "#34D399" : "#22D3EE";

  const gaugeLabel =
    phase === "ping"
      ? "در حال سنجش پینگ…"
      : phase === "download"
        ? "سرعت لحظه‌ای دانلود"
        : phase === "upload"
          ? "سرعت لحظه‌ای آپلود"
          : phase === "done"
            ? "میانگین دانلود نهایی"
            : phase === "error"
              ? "خطا در آزمون"
              : "آمادهٔ آزمون";

  const phasePct =
    phase === "ping" ? 12 : phase === "download" ? 55 : phase === "upload" ? 92 : phase === "done" ? 100 : 0;

  const disabledByOffline = !net.isOnline && !running;

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <GaugeIcon className="size-4 text-cyan-400" />
              آزمون سرعت واقعی
            </CardTitle>
            <CardDescription className="mt-1 text-xs leading-5">
              اندازه‌گیری با انتقال واقعی داده بین مرورگر شما و سرور — نه برآورد مرورگر
            </CardDescription>
          </div>
          <div className="flex items-center gap-1.5" aria-hidden>
            {PHASE_STEPS.map((s, i) => {
              const order = { idle: -1, ping: 0, download: 1, upload: 2, done: 3, error: 3 }[phase];
              const active = phase === s.key;
              const complete = order > i || phase === "done";
              return (
                <div key={s.key} className="flex items-center gap-1.5">
                  {i > 0 && <div className="w-4 h-px bg-border" />}
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-[11px] font-medium border transition-colors",
                      active && "bg-primary/15 text-primary border-primary/40",
                      complete && !active && "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
                      !active && !complete && "bg-transparent text-muted-foreground/60 border-border"
                    )}
                  >
                    {complete && !active ? "✓ " : ""}
                    {s.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-4">
        {/* عقربه و کنترل */}
        <div className="relative">
          <Gauge
            value={
              phase === "download" || phase === "upload" ? instant : (down?.avgMbps ?? 0)
            }
            avg={phase === "download" || phase === "upload" ? avg : undefined}
            max={Math.max(down?.peakMbps ?? 0, up?.peakMbps ?? 0)}
            color={displayColor}
            label={gaugeLabel}
          />
          {phase === "ping" && (
            <div className="text-center text-xs text-emerald-400 tnum -mt-1">
              <Activity className="inline size-3.5 ml-1 -mt-0.5" />
              در حال سنجش تأخیر رفت‌وبرگشت…
            </div>
          )}
        </div>

        {/* نمودار لحظه‌ای */}
        <div className="rounded-lg border bg-[#0D151D] px-2 pt-1">
          <Sparkline
            values={spark.map((s) => s.v)}
            color={displayColor}
            height={64}
            emptyText={
              phase === "idle"
                ? "نمودار سرعت لحظه‌ای پس از شروع آزمون اینجا رسم می‌شود"
                : "در حال دریافت نمونه‌ها…"
            }
          />
          {running && (
            <div className="flex items-center justify-between px-2 pb-1.5 text-[11px] text-muted-foreground tnum">
              <span>
                {formatDataSize(phaseBytes)} منتقل‌شده
              </span>
              <span>{faFormat(Math.round(elapsed / 100) / 10, 1)} ثانیه</span>
            </div>
          )}
        </div>

        {running && <Progress value={phasePct} className="h-1.5" />}

        {/* دکمه‌ها */}
        <div className="flex flex-wrap items-center gap-3">
          {!running ? (
            <TooltipProvider delayDuration={disabledByOffline ? 0 : 700}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <Button
                      size="lg"
                      onClick={start}
                      disabled={disabledByOffline}
                      className="min-w-[170px] font-bold"
                    >
                      {phase === "done" || phase === "error" ? (
                        <>
                          <RefreshCw className="ml-2 size-4" />
                          آزمون مجدد
                        </>
                      ) : (
                        <>
                          <Play className="ml-2 size-4" />
                          شروع آزمون
                        </>
                      )}
                    </Button>
                  </span>
                </TooltipTrigger>
                {disabledByOffline && (
                  <TooltipContent side="top" className="bg-rose-950/90 border-rose-500/40">
                    <span className="flex items-center gap-1.5 text-rose-200">
                      <WifiOff className="size-3.5" />
                      اینترنت قطع است — تا بازگشت اتصال امکان آزمون نیست
                    </span>
                  </TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          ) : (
            <Button size="lg" variant="destructive" onClick={stop} className="min-w-[170px]">
              <Square className="ml-2 size-4" />
              توقف آزمون
            </Button>
          )}

          <div className="text-[11px] leading-5 text-muted-foreground">
            {phase === "idle" && "آزمون حدود ۳۰ ثانیه و در مجموع تا ~۴۰ مگابایت داده منتقل می‌کند"}
            {phase === "done" && (
              <span className="inline-flex items-center gap-1.5 text-emerald-400">
                <CheckCircle2 className="size-3.5" />
                آزمون کامل شد
                {saveState === "saved-server" && " — در تاریخچه (سرور) ذخیره شد"}
                {saveState === "saved-local" && " — در تاریخچه محلی ذخیره شد"}
                {saveState === "saving" && " — در حال ذخیره…"}
              </span>
            )}
            {phase === "error" && <span className="text-rose-400">{error}</span>}
          </div>
        </div>

        {/* نتایج نهایی */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <MetricBox
            icon={<Download className="size-3.5" />}
            label="دانلود"
            value={down ? formatMbps(down.avgMbps) : "—"}
            unit="Mbps"
            color="#22D3EE"
            hint={down ? `اوج: ${formatMbps(down.peakMbps)}` : undefined}
          />
          <MetricBox
            icon={<Upload className="size-3.5" />}
            label="آپلود"
            value={up ? formatMbps(up.avgMbps) : "—"}
            unit="Mbps"
            color="#FBBF24"
            hint={up ? `اوج: ${formatMbps(up.peakMbps)}` : undefined}
          />
          <MetricBox
            icon={<Activity className="size-3.5" />}
            label="پینگ"
            value={ping ? formatMs(ping.median) : "—"}
            unit="ms"
            color="#34D399"
            hint={ping ? `کمینه: ${formatMs(ping.min)}` : undefined}
          />
          <MetricBox
            icon={<Waves className="size-3.5" />}
            label="نوسان (جیتر)"
            value={ping ? formatMs(ping.jitter) : "—"}
            unit="ms"
            color="#A78BFA"
            hint={ping ? `نمونه‌ها: ${faFormat(ping.samples.length, 0)}` : undefined}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function MetricBox({
  icon,
  label,
  value,
  unit,
  color,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  unit: string;
  color: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border bg-[#1B2733]/60 px-3 py-2.5 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <span style={{ color }}>{icon}</span>
        {label}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="tnum text-xl font-bold leading-none" style={{ color }}>
          {value}
        </span>
        <span className="text-[10px] text-muted-foreground/80">{unit}</span>
      </div>
      {hint && <div className="text-[10px] text-muted-foreground/70 tnum">{hint}</div>}
    </div>
  );
}
