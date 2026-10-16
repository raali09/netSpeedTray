"use client";

// صفحهٔ اصلی «آزمونگر سرعت» —
//   • سرعت واقعی: اندازه‌گیری با انتقال واقعی بایت‌ها (نه برآورد مرورگر)
//   • تشخیص قطعی: سه سیگنال مستقل و بنر صریح «اینترنت قطع است»
//   • تمایز صریح «قطع» از «بدون ترافیک/بیکار»

import { useCallback, useEffect, useState } from "react";
import { useNetworkStatus } from "@/hooks/use-network-status";
import { SpeedTestCard, type TestOutcome } from "@/components/speedmeter/SpeedTestCard";
import { LiveMonitorCard } from "@/components/speedmeter/LiveMonitorCard";
import { ConnectionInfoCard } from "@/components/speedmeter/ConnectionInfoCard";
import { HistoryCard } from "@/components/speedmeter/HistoryCard";
import { WidgetView } from "@/components/speedmeter/WidgetView";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import type { HistoryItem } from "@/lib/types";
import { faFormat } from "@/lib/speedtest";
import { Gauge as GaugeIcon, Wifi, WifiOff, RadioTower, Radar, Heart, PictureInPicture2 } from "lucide-react";
import { cn } from "@/lib/utils";

const LS_KEY = "speedmeter:history";
const HISTORY_CAP = 20;
// نسخهٔ برنامه — با package.json هماهنگ نگه دارید
const APP_VERSION = "۲٫۱۳٫۰";

function loadLocalHistory(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (it): it is HistoryItem =>
          it && typeof it.download === "number" && typeof it.createdAt === "string"
      )
      .slice(0, HISTORY_CAP);
  } catch {
    return [];
  }
}

function persistLocal(items: HistoryItem[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(items.slice(0, HISTORY_CAP)));
  } catch {
    /* حافظه پر یا غیرفعال — نادیده بگیر */
  }
}

export default function Home() {
  const net = useNetworkStatus();
  const { toast } = useToast();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  // حالت ویجت (/?widget=1): نمای فشرده برای پنجرهٔ کوچک الکترون
  const [widgetMode, setWidgetMode] = useState(false);
  // پل الکترون (فقط داخل ویجت ویندوزی وجود دارد)
  const [desktop, setDesktop] = useState(false);

  useEffect(() => {
    try {
      setWidgetMode(new URLSearchParams(window.location.search).has("widget"));
      setDesktop(Boolean(window.speedmeter));
    } catch {
      /* دسترسی به window ناموفق — نادیده بگیر */
    }
  }, []);

  // بارگذاری اولیه: نسخهٔ محلی + نسخهٔ سرور در یک ادامهٔ غیرهمگام ادغام
  // می‌شوند تا setState همگام داخل بدنهٔ effect رخ ندهد. اگر سرور پاسخ ندهد،
  // همان نسخهٔ محلی (آینهٔ localStorage) نمایش داده می‌شود.
  useEffect(() => {
    if (widgetMode) return; // در حالت ویجت، تاریخچه لازم نیست
    let cancelled = false;
    const ctl = new AbortController();
    const timeout = setTimeout(() => ctl.abort(), 5000);
    (async () => {
      const local = loadLocalHistory();
      let serverRows: HistoryItem[] | null = null;
      try {
        const r = await fetch("/api/results", { cache: "no-store", signal: ctl.signal });
        if (!r.ok) throw new Error("bad status");
        const j = (await r.json()) as { rows?: HistoryItem[] };
        serverRows = (j.rows ?? []).map((row) => ({ ...row, source: "server" as const }));
      } catch {
        /* سرور در دسترس نیست — نسخهٔ محلی نمایش داده می‌شود */
      }
      if (cancelled) return;
      if (serverRows) {
        const serverIds = new Set(serverRows.map((r) => r.id));
        const keptLocal = local.filter((l) => !serverIds.has(l.id));
        const merged = [...serverRows, ...keptLocal]
          .sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt))
          .slice(0, HISTORY_CAP);
        setHistory(merged);
      } else {
        setHistory(local);
      }
      setLoadingHistory(false);
    })();
    return () => {
      cancelled = true;
      ctl.abort();
      clearTimeout(timeout);
    };
  }, [widgetMode]);

  // آینهٔ محلی: با هر تغییر تاریخچه در localStorage نوشته می‌شود (برای
  // مشاهده در قطعی) — نوشتن در سیستم بیرونی، کارِ مجازِ effect است.
  // در حالت ویجت نوشتن انجام نمی‌شود تا تاریخچهٔ محلی کاربر پاک نشود.
  useEffect(() => {
    if (!widgetMode) persistLocal(history);
  }, [history, widgetMode]);

  const handleResult = useCallback(async (outcome: TestOutcome) => {
    const optimistic: HistoryItem = {
      id: `local-${Date.now()}`,
      download: outcome.download,
      upload: outcome.upload,
      ping: outcome.ping,
      jitter: outcome.jitter,
      createdAt: new Date().toISOString(),
      source: "local",
    };
    setHistory((prev) => [optimistic, ...prev].slice(0, HISTORY_CAP));

    const res = await fetch("/api/results", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        download: outcome.download,
        upload: outcome.upload,
        ping: outcome.ping,
        jitter: outcome.jitter,
      }),
    });
    if (!res.ok) throw new Error("save failed");
    const j = (await res.json()) as { row?: HistoryItem };
    const saved = j.row;
    setHistory((prev) => {
      const next = prev.map((it) =>
        it.id === optimistic.id && saved ? { ...saved, source: "server" as const } : it
      );
      return next;
    });
  }, []);

  const handleResultSafe = useCallback(
    async (outcome: TestOutcome) => {
      try {
        await handleResult(outcome);
      } catch {
        toast({
          title: "ذخیره در سرور ممکن نشد",
          description: "اینترنت یا سرور در دسترس نیست؛ نتیجه در حافظهٔ محلی نگه داشته شد.",
        });
        throw new Error("saved-local");
      }
    },
    [handleResult, toast]
  );

  const handleClear = useCallback(async () => {
    persistLocal([]);
    setHistory([]);
    try {
      await fetch("/api/results", { method: "DELETE" });
      toast({ title: "تاریخچه پاک شد", description: "همهٔ نتایج حذف شدند." });
    } catch {
      toast({
        title: "تاریخچهٔ محلی پاک شد",
        description: "حذف از سرور ممکن نشد — اتصال را بررسی کنید.",
      });
    }
  }, [toast]);

  // حالت ویجت: نمای فشرده برای پنجرهٔ کوچکِ همیشه‌بالای صفحه (الکترون)
  if (widgetMode) return <WidgetView />;

  return (
    <div className="min-h-screen flex flex-col app-bg">
      {/* هدر */}
      <header className="sticky top-0 z-40 border-b bg-[#0A1017]/85 backdrop-blur supports-[backdrop-filter]:bg-[#0A1017]/70">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="grid place-items-center size-10 rounded-xl bg-gradient-to-br from-cyan-400/25 to-cyan-400/5 border border-cyan-400/30 shrink-0">
              <GaugeIcon className="size-5 text-cyan-400" aria-hidden />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                <h1 className="text-sm sm:text-base font-extrabold leading-tight truncate">
                  آزمونگر سرعت اینترنت
                </h1>
                <span
                  className="shrink-0 rounded-full border border-cyan-400/25 bg-cyan-400/10 px-1.5 py-px text-[9px] font-bold text-cyan-300/90"
                  title={`نسخهٔ ${APP_VERSION}`}
                >
                  {APP_VERSION}
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground truncate">
                اندازه‌گیری واقعی · پایش پیوسته · تشخیص قطعی
              </p>
            </div>
          </div>

          <div
            className={cn(
              "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold shrink-0 transition-colors",
              net.state === "online" && "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
              net.state === "checking" && "bg-slate-500/10 border-slate-500/30 text-slate-300",
              net.state === "server-down" && "bg-amber-500/10 border-amber-500/30 text-amber-400",
              net.state === "offline" && "bg-rose-500/10 border-rose-500/30 text-rose-400"
            )}
            role="status"
            aria-live="polite"
          >
            {net.state === "online" && (
              <>
                <Wifi className="size-3.5" aria-hidden />
                متصل
                <span className="size-1.5 rounded-full bg-emerald-400 live-dot" aria-hidden />
              </>
            )}
            {net.state === "checking" && (
              <>
                <Radar className="size-3.5 animate-spin-slow" aria-hidden />
                در حال بررسی
              </>
            )}
            {net.state === "server-down" && (
              <>
                <RadioTower className="size-3.5" aria-hidden />
                سرور قطع
              </>
            )}
            {net.state === "offline" && (
              <>
                <WifiOff className="size-3.5" aria-hidden />
                اینترنت قطع است
              </>
            )}
          </div>

          {desktop && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => window.speedmeter?.openWidget()}
              className="shrink-0"
              title="نمایش ویجت همیشه‌بالای صفحه"
            >
              <PictureInPicture2 className="size-3.5" aria-hidden />
              <span className="hidden sm:inline">ویجت</span>
            </Button>
          )}
        </div>
      </header>

      {/* بدنه */}
      <main className="flex-1 mx-auto w-full max-w-6xl px-4 sm:px-6 py-6 flex flex-col gap-6">
        {/* بنرهای وضعیت */}
        {net.state === "offline" && (
          <div
            role="alert"
            className="banner-in alert-glow rounded-xl border border-rose-500/40 bg-gradient-to-l from-rose-950/80 to-rose-900/40 px-4 sm:px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-4"
          >
            <div className="grid place-items-center size-12 rounded-full bg-rose-500/15 border border-rose-500/30 shrink-0">
              <WifiOff className="size-6 text-rose-400" aria-hidden />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-rose-300">اینترنت قطع است</div>
              <p className="text-xs leading-6 text-rose-200/80 mt-1">
                هیچ پاسخی از سرور برنامه و میزبان‌های بیرونی دریافت نمی‌شود. توجه:
                «قطع بودن اینترنت» با «بدون ترافیک بودن» متفاوت است — در حالت بدون
                ترافیک، اتصال سالم است و فقط داده‌ای رد و بدل نمی‌شود. آزمون سرعت
                تا بازگشت اتصال قفل است.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={net.forceCheck}
              className="border-rose-400/40 text-rose-200 hover:bg-rose-500/10 hover:text-rose-100 shrink-0"
            >
              <Radar className="ml-1.5 size-3.5" />
              بررسی مجدد
            </Button>
          </div>
        )}

        {net.state === "server-down" && (
          <div
            role="alert"
            className="banner-in rounded-xl border border-amber-500/40 bg-gradient-to-l from-amber-950/70 to-amber-900/30 px-4 sm:px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-4"
          >
            <div className="grid place-items-center size-12 rounded-full bg-amber-500/15 border border-amber-500/30 shrink-0">
              <RadioTower className="size-6 text-amber-400" aria-hidden />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-amber-300">سرور برنامه در دسترس نیست</div>
              <p className="text-xs leading-6 text-amber-200/80 mt-1">
                اینترنت شما برقرار است (پروب‌های بیرونی پاسخ می‌دهند) اما سرور
                برنامه پاسخ نمی‌دهد. به‌طور خودکار هر ۲ ثانیه دوباره تلاش می‌شود.
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={net.forceCheck}
              className="border-amber-400/40 text-amber-200 hover:bg-amber-500/10 hover:text-amber-100 shrink-0"
            >
              <Radar className="ml-1.5 size-3.5" />
              بررسی مجدد
            </Button>
          </div>
        )}

        {/* شبکهٔ کارت‌ها */}
        <div className="grid gap-5 lg:grid-cols-3 items-start">
          <div className="lg:col-span-2 grid gap-5">
            <SpeedTestCard net={net} onResult={handleResultSafe} />
          </div>
          <LiveMonitorCard net={net} />

          <ConnectionInfoCard net={net} />

          <div className="lg:col-span-2 grid gap-5">
            <HistoryCard items={history} onClear={handleClear} loading={loadingHistory} />
          </div>
        </div>

        {/* توضیح روش‌شناسی */}
        <section className="rounded-xl border bg-[#101820]/70 px-5 py-4">
          <h2 className="text-xs font-bold text-foreground/90 mb-2">
            این اعداد چگونه به دست می‌آیند؟
          </h2>
          <p className="text-[11px] leading-6 text-muted-foreground">
            سرعت دانلود با دریافت جریان واقعی بایت‌ها از سرور و سرعت آپلود با
            ارسال واقعی داده اندازه‌گیری می‌شود؛ پینگ از زمان رفت‌وبرگشت درخواست‌های
            سبک و نوسان از پراکندگی نمونه‌ها محاسبه می‌شود. وضعیت قطعی از سه
            سیگنال مستقل (رویداد شبکهٔ مرورگر، تپ قلب سرور و پروب میزبان‌های
            بیرونی) تعیین می‌شود تا «قطعی واقعی» هرگز با «بیکاری شبکه» اشتباه گرفته
            نشود. {history.length > 0 && `تاکنون ${faFormat(history.length, 0)} آزمون ثبت شده است.`}
          </p>
        </section>
      </main>

      {/* پاصفحهٔ چسبان */}
      <footer className="mt-auto border-t bg-[#0A1017]/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-14 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            ساخته‌شده با Next.js و علاقه
            <Heart className="size-3 text-rose-400 live-dot" aria-hidden />
            <span className="opacity-60">· نسخهٔ {APP_VERSION}</span>
          </span>
          <span className="hidden sm:inline">
            سرعت‌ها از انتقال واقعی داده اندازه‌گیری می‌شوند — نه از برآورد مرورگر
          </span>
          <span className="tnum" suppressHydrationWarning>
            آخرین بررسی:{" "}
            {net.lastCheckedAt
              ? new Intl.DateTimeFormat("fa-IR", { timeStyle: "medium" }).format(net.lastCheckedAt)
              : "—"}
          </span>
        </div>
      </footer>
    </div>
  );
}
