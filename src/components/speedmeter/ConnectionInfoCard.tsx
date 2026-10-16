"use client";

// شفافیت کامل منطق تشخیص — کاربر می‌بیند کدام سیگنال‌ها فعال/غیرفعال‌اند:
// مرورگر، سرور برنامه و اینترنت بیرونی؛ به‌علاوهٔ برآورد تقریبی مرورگر
// (Network Information API) که صراحتاً «برآوردی» برچسب خورده تا با سرعت
// واقعی اندازه‌گیری‌شده اشتباه گرفته نشود.

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { NetworkStatus } from "@/hooks/use-network-status";
import { faFormat } from "@/lib/speedtest";
import { Globe, Signal, ShieldQuestion, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface NetworkInformationLike {
  effectiveType?: string;
  downlink?: number;
  rtt?: number;
  saveData?: boolean;
  type?: string;
}

export function ConnectionInfoCard({ net }: { net: NetworkStatus }) {
  const [connInfo, setConnInfo] = useState<NetworkInformationLike | null>(null);
  const [publicIp, setPublicIp] = useState<string | null>(null);
  const [ipState, setIpState] = useState<"idle" | "loading" | "ok" | "fail">("idle");

  useEffect(() => {
    const nav = navigator as Navigator & { connection?: NetworkInformationLike };
    const read = () => setConnInfo(nav.connection ?? null);
    read();
    const anyNav = nav as unknown as Record<string, { addEventListener?: (t: string, f: () => void) => void; removeEventListener?: (t: string, f: () => void) => void }>;
    anyNav.connection?.addEventListener?.("change", read);
    return () => anyNav.connection?.removeEventListener?.("change", read);
  }, []);

  // هنگام تغییر وضعیت اتصال، وضعیت IP را در رندر بازنشانی می‌کنیم (الگوی
  // «تعدیل state در حین رندر» که react توصیه می‌کند) تا setState همگام در
  // effect رخ ندهد.
  const [prevOnline, setPrevOnline] = useState(net.isOnline);
  if (prevOnline !== net.isOnline) {
    setPrevOnline(net.isOnline);
    if (net.isOnline) {
      setIpState("loading");
      setPublicIp(null);
    } else {
      setIpState("idle");
    }
  }

  useEffect(() => {
    if (!net.isOnline) return;
    let cancelled = false;
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), 5000);
    fetch("https://api.ipify.org?format=json", { signal: ctl.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((j: { ip?: string }) => {
        if (cancelled) return;
        setPublicIp(j.ip ?? null);
        setIpState(j.ip ? "ok" : "fail");
      })
      .catch(() => {
        if (!cancelled) setIpState("fail");
      })
      .finally(() => clearTimeout(to));
    return () => {
      cancelled = true;
      ctl.abort();
      clearTimeout(to);
    };
  }, [net.isOnline]);

  const signals: {
    label: string;
    value: boolean | null;
    desc: string;
  }[] = [
    {
      label: "مرورگر (navigator.onLine)",
      value: net.browserOnline ? true : false,
      desc: "وضعیت رابط شبکه از دید سیستم‌عامل",
    },
    {
      label: "سرور برنامه (تپ قلب)",
      value: net.heartbeatOk,
      desc: `هر ۲ ثانیه · ${net.rtt != null ? `${faFormat(Math.round(net.rtt), 0)} ms` : "بدون پاسخ"}`,
    },
    {
      label: "اینترنت بیرونی (پروب ۲۰۴)",
      value: net.externalOk,
      desc: net.externalOk == null ? "فقط هنگام خطای تپ قلب آزمایش می‌شود" : "gstatic / cloudflare",
    },
  ];

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Signal className="size-4 text-violet-400" />
          جزئیات اتصال
        </CardTitle>
        <CardDescription className="text-xs">
          سه سیگنال مستقل برای تشخیص دقیق وضعیت شبکه
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col gap-4">
        <ul className="flex flex-col gap-2">
          {signals.map((s) => (
            <li
              key={s.label}
              className="flex items-start justify-between gap-3 rounded-lg border bg-[#0D151D] px-3 py-2"
            >
              <div className="min-w-0">
                <div className="text-xs font-medium">{s.label}</div>
                <div className="text-[10px] text-muted-foreground mt-0.5">{s.desc}</div>
              </div>
              <span className="shrink-0 mt-0.5">
                {s.value == null ? (
                  <ShieldQuestion className="size-4 text-muted-foreground/60" aria-label="نامشخص" />
                ) : s.value ? (
                  <span
                    className="flex items-center gap-1 text-[11px] font-bold text-emerald-400"
                    aria-label="فعال"
                  >
                    <Check className="size-4" />
                    برقرار
                  </span>
                ) : (
                  <span
                    className="flex items-center gap-1 text-[11px] font-bold text-rose-400"
                    aria-label="قطع"
                  >
                    <X className="size-4" />
                    قطع
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>

        <div className="grid grid-cols-2 gap-2.5">
          <InfoTile
            label="IP عمومی"
            value={
              ipState === "loading"
                ? "در حال دریافت…"
                : ipState === "ok" && publicIp
                  ? publicIp
                  : ipState === "fail"
                    ? "دریافت نشد"
                    : "—"
            }
            dir="ltr"
            icon={<Globe className="size-3.5" />}
          />
          <InfoTile
            label="نوع اتصال"
            value={connInfo?.effectiveType ? connInfo.effectiveType.toUpperCase() : "نامشخص"}
            icon={<Signal className="size-3.5" />}
          />
          <InfoTile
            label="برآورد دانلود مرورگر"
            value={
              connInfo?.downlink != null ? `${faFormat(connInfo.downlink, 1)} Mbps` : "ناموجود"
            }
            icon={<Signal className="size-3.5" />}
            badge="تقریبی"
          />
          <InfoTile
            label="برآورد RTT مرورگر"
            value={connInfo?.rtt != null ? `${faFormat(connInfo.rtt, 0)} ms` : "ناموجود"}
            icon={<Signal className="size-3.5" />}
            badge="تقریبی"
          />
        </div>

        <p className="text-[10px] leading-5 text-muted-foreground/80">
          اعداد «برآوردی» از Network Information API مرورگر می‌آیند و معیار دقیقی
          نیستند؛ نتایج اصلی آزمون از انتقال واقعی داده به دست می‌آیند.
        </p>
      </CardContent>
    </Card>
  );
}

function InfoTile({
  label,
  value,
  icon,
  dir,
  badge,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  dir?: "ltr" | "rtl";
  badge?: string;
}) {
  return (
    <div className="rounded-lg border bg-[#1B2733]/60 px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span className="text-violet-400">{icon}</span>
        {label}
        {badge && (
          <Badge variant="outline" className="h-3.5 px-1 text-[8px] border-amber-500/40 text-amber-400">
            {badge}
          </Badge>
        )}
      </div>
      <div
        className={cn("mt-1 text-sm font-bold tnum", dir === "ltr" && "text-left")}
        dir={dir}
      >
        {value}
      </div>
    </div>
  );
}
