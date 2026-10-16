"use client";

// پایش وضعیت شبکه — سه سیگنال مستقل:
//   ۱) navigator.onLine مرورگر (رویداد فوری برای قطع‌شدن کارت شبکه/وای‌فای)
//   ۲) تپ قلب به سرور برنامه (هر ۲ ثانیه؛ هم دسترسی، هم RTT)
//   ۳) پروب اینترنت خارجی (فقط وقتی تپ قلب شکست بخورد؛ برای تمایز
//      «قطع کامل اینترنت» از «قطع سرور برنامه»)
// دو خطای پشت‌سرهم لازم است تا وضعیت «قطع» اعلام شود تا لرزش لحظه‌ای شبکه
// باعث هشدار دروغین نشود؛ اما بازیابی با اولین موفقیت فوری است.

import { useCallback, useEffect, useRef, useState } from "react";
import { probeExternal, timedHeartbeat } from "@/lib/speedtest";

export type NetState = "checking" | "online" | "offline" | "server-down";

export interface PingSample {
  t: number;
  ms: number;
}

export interface NetworkStatus {
  state: NetState;
  isOnline: boolean;
  /** null یعنی هنوز بررسی نشده */
  heartbeatOk: boolean | null;
  /** null یعنی هنوز بررسی نشده */
  externalOk: boolean | null;
  browserOnline: boolean;
  rtt: number | null;
  pingHistory: PingSample[];
  lastCheckedAt: number | null;
  offlineFailures: number;
  forceCheck: () => void;
}

const HEARTBEAT_INTERVAL_MS = 2000;
const OFFLINE_AFTER_FAILURES = 2;
const PING_HISTORY_CAP = 60;

export function useNetworkStatus(): NetworkStatus {
  const [state, setState] = useState<NetState>("checking");
  const [heartbeatOk, setHeartbeatOk] = useState<boolean | null>(null);
  const [externalOk, setExternalOk] = useState<boolean | null>(null);
  const [browserOnline, setBrowserOnline] = useState(true);
  const [rtt, setRtt] = useState<number | null>(null);
  const [pingHistory, setPingHistory] = useState<PingSample[]>([]);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  const [offlineFailures, setOfflineFailures] = useState(0);

  const failCountRef = useRef(0);
  const busyRef = useRef(false);
  const runIdRef = useRef(0);
  const browserOnlineRef = useRef(true);

  const applySuccess = useCallback((ms: number) => {
    failCountRef.current = 0;
    setOfflineFailures(0);
    setHeartbeatOk(true);
    setRtt(ms);
    setLastCheckedAt(Date.now());
    setPingHistory((prev) => {
      const next = [...prev, { t: Date.now(), ms }];
      return next.length > PING_HISTORY_CAP ? next.slice(-PING_HISTORY_CAP) : next;
    });
    setState((prev) => (prev === "online" ? prev : "online"));
  }, []);

  const runCheck = useCallback(async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    const myRun = ++runIdRef.current;
    try {
      const ms = await timedHeartbeat(4000);
      if (myRun !== runIdRef.current) return; // بررسی تازه‌تری جاگذاری شده
      applySuccess(ms);
      setExternalOk(null); // نیازی به پروب خارجی نیست
    } catch {
      if (myRun !== runIdRef.current) return;
      failCountRef.current += 1;
      setOfflineFailures(failCountRef.current);
      setHeartbeatOk(false);
      setLastCheckedAt(Date.now());
      // تمایز کلیدی: اینترنتِ بیرون هم قطع است یا فقط سرور ما؟
      const ext = await probeExternal(3500);
      if (myRun !== runIdRef.current) return;
      setExternalOk(ext);
      if (ext) {
        // اینترنت بیرونی کار می‌کند؛ مشکل از دسترسی به سرور برنامه است
        setState((prev) => (prev === "offline" ? prev : "server-down"));
      } else if (failCountRef.current >= OFFLINE_AFTER_FAILURES) {
        // نه سرور در دسترس است و نه هیچ میزبان بیرونی → اینترنت قطع است
        setState("offline");
      }
    } finally {
      busyRef.current = false;
    }
  }, [applySuccess]);

  useEffect(() => {
    browserOnlineRef.current = browserOnline;
  }, [browserOnline]);

  useEffect(() => {
    const onOffline = () => {
      // مرورگر خودش قطعی کارت شبکه/وای‌فای را فوری اعلام می‌کند
      setBrowserOnline(false);
      failCountRef.current += 1;
      setOfflineFailures(failCountRef.current);
      setHeartbeatOk(false);
      runIdRef.current++; // بررسی‌های در حال پرواز را بی‌اعتبار کن
      setState("offline");
      setLastCheckedAt(Date.now());
    };
    const onOnline = () => {
      setBrowserOnline(true);
      // رویداد online فقط یعنی شبکه دوباره فعال است؛ بلافاصله دوباره بررسی کن
      void runCheck();
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") void runCheck();
    };
    window.addEventListener("offline", onOffline);
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("offline", onOffline);
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [runCheck]);

  useEffect(() => {
    void runCheck();
    const interval = setInterval(() => void runCheck(), HEARTBEAT_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [runCheck]);

  const forceCheck = useCallback(() => {
    runIdRef.current++;
    busyRef.current = false;
    void runCheck();
  }, [runCheck]);

  return {
    state,
    isOnline: state === "online",
    heartbeatOk,
    externalOk,
    browserOnline,
    rtt,
    pingHistory,
    lastCheckedAt,
    offlineFailures,
    forceCheck,
  };
}
