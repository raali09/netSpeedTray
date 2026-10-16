// موتور اندازه‌گیری سرعت واقعی — همهٔ اعداد این ماژول از انتقال «واقعی»
// بایت‌ها روی شبکه به دست می‌آیند، نه از برآورد مرورگر.
// دانلود با خواندن جریان پاسخ (ReadableStream) و آپلود با رویدادهای پیشرفت
// XHR اندازه‌گیری می‌شود تا سرعت لحظه‌ای در طول آزمون هم قابل مشاهده باشد.

export interface SpeedSample {
  t: number; // زمان نسبی از شروع فاز (ms)
  v: number; // مگابیت بر ثانیه (لحظه‌ای)
}

export interface PhaseResult {
  avgMbps: number;
  peakMbps: number;
  bytes: number;
  elapsedMs: number;
  samples: SpeedSample[];
}

export interface PingResult {
  min: number;
  median: number;
  avg: number;
  max: number;
  jitter: number;
  samples: number[];
}

/** پنجرهٔ لغزان برای محاسبهٔ سرعت لحظه‌ای روی جریان بایت‌ها. */
export class SpeedWindow {
  private events: { t: number; total: number }[] = [];
  private windowMs: number;

  constructor(windowMs = 700) {
    this.windowMs = windowMs;
  }

  add(cumulativeBytes: number, t: number) {
    this.events.push({ t, total: cumulativeBytes });
    // حافظهٔ محدود: فقط نقاط داخل پنجرهٔ دوبرابر نگه داشته می‌شود
    const cutoff = t - this.windowMs * 2.5;
    while (this.events.length > 2 && this.events[0].t < cutoff) {
      this.events.shift();
    }
  }

  /** بایت بر ثانیه روی پنجرهٔ اخیر؛ اگر داده کم است با کل دوره محاسبه می‌شود. */
  instant(t: number): number {
    if (this.events.length < 2) return 0;
    const first = this.events[0];
    const last = this.events[this.events.length - 1];
    const span = last.t - first.t;
    if (span <= 0) return 0;
    return ((last.total - first.total) / span) * 1000;
  }

  reset() {
    this.events = [];
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const MB = 1024 * 1024;
const BITS_PER_BYTE = 8;

/** یک تپ قلب زمان‌گیری‌شده؛ خطا با reject. */
export async function timedHeartbeat(timeoutMs = 4000): Promise<number> {
  const ctl = new AbortController();
  const to = setTimeout(() => ctl.abort(), timeoutMs);
  const t0 = performance.now();
  try {
    const res = await fetch("/api/heartbeat", {
      cache: "no-store",
      signal: ctl.signal,
      headers: { "Cache-Control": "no-cache" },
    });
    if (!res.ok) throw new Error(`status ${res.status}`);
    return performance.now() - t0;
  } finally {
    clearTimeout(to);
  }
}

/** بررسی دسترسی به اینترنت خارجی (فراتر از سرور خود برنامه). */
export async function probeExternal(timeoutMs = 3500): Promise<boolean> {
  const targets = [
    "https://www.gstatic.com/generate_204",
    "https://cp.cloudflare.com/generate_204",
    "https://www.cloudflare.com/cdn-cgi/trace",
  ];
  for (const url of targets) {
    try {
      const ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), timeoutMs);
      await fetch(url, { mode: "no-cors", cache: "no-store", signal: ctl.signal });
      clearTimeout(to);
      // در حالت no-cors حتی پاسخ مبهم هم یعنی شبکه پاسخ داده است
      return true;
    } catch {
      //_endpoint بعدی
    }
  }
  return false;
}

/** نوسان (جیتر) = میانگین قدرمطلق اختلاف نمونه‌های متوالی. */
function jitterOf(samples: number[]): number {
  if (samples.length < 2) return 0;
  let sum = 0;
  for (let i = 1; i < samples.length; i++) sum += Math.abs(samples[i] - samples[i - 1]);
  return sum / (samples.length - 1);
}

function median(values: number[]): number {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/** فاز پینگ: چند تپ پشت‌سرهم برای کمینه/میانه/جیتر. */
export async function runPingBurst(
  count = 6,
  onProgress?: (done: number, total: number, rtt: number) => void,
  signal?: AbortSignal
): Promise<PingResult> {
  const samples: number[] = [];
  for (let i = 0; i < count; i++) {
    if (signal?.aborted) break;
    try {
      const rtt = await timedHeartbeat();
      samples.push(rtt);
      onProgress?.(i + 1, count, rtt);
    } catch {
      onProgress?.(i + 1, count, -1);
    }
    await sleep(130);
  }
  if (!samples.length) throw new Error("پاسخی از سرور دریافت نشد");
  const sorted = [...samples].sort((a, b) => a - b);
  const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
  return {
    min: sorted[0],
    median: median(samples),
    avg,
    max: sorted[sorted.length - 1],
    jitter: jitterOf(samples),
    samples,
  };
}

interface DownloadPhaseOpts {
  onProgress?: (info: {
    instantMbps: number;
    avgMbps: number;
    bytes: number;
    elapsedMs: number;
  }) => void;
  signal?: AbortSignal;
  maxSeconds?: number;
  maxBytes?: number;
}

/**
 * فاز دانلود — حجم تطبیقی: با تکه‌های [۲، ۸، ۱۶] مگابایتی ادامه می‌دهد تا
 * حد زمانی/حجم برسد؛ تکهٔ گرم (۵۱۲KB) از آمار کنار گذاشته می‌شود تا مسیر
 * و بافرهای شبکه از قبل گرم شده باشند و نتیجه دقیق‌تر باشد.
 */
export async function runDownloadPhase(opts: DownloadPhaseOpts = {}): Promise<PhaseResult> {
  const { onProgress, signal, maxSeconds = 10, maxBytes = 26 * MB } = opts;

  // ۱) گرم‌کردن مسیر (از آمار خارج است)
  try {
    await streamDownload(512 * 1024, () => {}, signal, 5000);
  } catch {
    /* گرم‌کردن اختیاری است */
  }

  const schedule = [2 * MB, 8 * MB, 16 * MB];
  let totalBytes = 0;
  const t0 = performance.now();
  const win = new SpeedWindow(700);
  const samples: SpeedSample[] = [];
  let lastUi = 0;

  const report = (force = false) => {
    const now = performance.now();
    if (!force && now - lastUi < 140) return;
    lastUi = now;
    const elapsed = now - t0;
    const inst = win.instant(now);
    const avg = totalBytes / (elapsed / 1000);
    onProgress?.({
      instantMbps: (inst * BITS_PER_BYTE) / 1e6,
      avgMbps: (avg * BITS_PER_BYTE) / 1e6,
      bytes: totalBytes,
      elapsedMs: elapsed,
    });
  };

  const addAndReport = (cum: number, t: number) => {
    win.add(cum, t);
    samples.push({
      t: t - t0,
      v: (win.instant(t) * 8) / 1e6,
    });
    report();
  };

  for (const size of schedule) {
    if (signal?.aborted) break;
    if (totalBytes >= maxBytes || performance.now() - t0 >= maxSeconds * 1000) break;
    try {
      const got = await streamDownload(size, addAndReport, signal, maxSeconds * 1000);
      totalBytes += got;
    } catch {
      break; // قطع عمدی یا خطای شبکه → پایان فاز با آمار جمع‌شده
    }
  }
  const elapsedMs = performance.now() - t0;
  if (totalBytes <= 0) throw new Error("هیچ داده‌ای دریافت نشد");
  report(true);
  return {
    avgMbps: ((totalBytes / (elapsedMs / 1000)) * 8) / 1e6,
    peakMbps: samples.reduce((m, s) => Math.max(m, s.v), 0),
    bytes: totalBytes,
    elapsedMs,
    samples,
  };
}

async function streamDownload(
  bytes: number,
  onRead: (cumulative: number, t: number) => void,
  signal: AbortSignal | undefined,
  deadlineMs: number
): Promise<number> {
  const ctl = new AbortController();
  const onOuterAbort = () => ctl.abort();
  signal?.addEventListener("abort", onOuterAbort);
  const deadline = setTimeout(() => ctl.abort(), deadlineMs);
  const t0 = performance.now();
  let received = 0;
  try {
    const res = await fetch(`/api/speedtest/download?bytes=${bytes}`, {
      cache: "no-store",
      signal: ctl.signal,
    });
    if (!res.ok || !res.body) throw new Error(`status ${res.status}`);
    const reader = res.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value?.length ?? 0;
      onRead(received, performance.now());
    }
    return received;
  } finally {
    clearTimeout(deadline);
    signal?.removeEventListener("abort", onOuterAbort);
  }
}

interface UploadPhaseOpts {
  onProgress?: (info: {
    instantMbps: number;
    avgMbps: number;
    bytes: number;
    elapsedMs: number;
  }) => void;
  signal?: AbortSignal;
  maxSeconds?: number;
  maxBytes?: number;
}

/** ساخت داده تصادفی سمت مرورگر برای آپلود. */
function makePayload(bytes: number): Uint8Array<ArrayBuffer> {
  const data = new Uint8Array(new ArrayBuffer(bytes));
  const view = new DataView(data.buffer);
  // پرکردن با الگوی شبه‌تصادفی برای جلوگیری از فشرده‌سازی مسیر
  let seed = (Math.random() * 0xffffffff) >>> 0;
  for (let i = 0; i < bytes; i += 4) {
    // xorshift32
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    seed >>>= 0;
    view.setUint32(i, seed, true);
  }
  return data;
}

/**
 * فاز آپلود — با XHR چون رویداد پیشرفت آپلود (فقط در XHR موجود است)
 * سرعت لحظه‌ای را در طول ارسال می‌دهد.
 */
export async function runUploadPhase(opts: UploadPhaseOpts = {}): Promise<PhaseResult> {
  const { onProgress, signal, maxSeconds = 10, maxBytes = 14 * MB } = opts;

  const schedule = [1 * MB, 4 * MB, 8 * MB];
  let totalBytes = 0;
  const t0 = performance.now();
  const win = new SpeedWindow(700);
  const samples: SpeedSample[] = [];
  let lastUi = 0;

  const report = (force = false) => {
    const now = performance.now();
    if (!force && now - lastUi < 140) return;
    lastUi = now;
    const elapsed = now - t0;
    const inst = win.instant(now);
    const avg = totalBytes / (elapsed / 1000);
    onProgress?.({
      instantMbps: (inst * 8) / 1e6,
      avgMbps: (avg * 8) / 1e6,
      bytes: totalBytes,
      elapsedMs: elapsed,
    });
  };

  for (const size of schedule) {
    if (signal?.aborted) break;
    if (totalBytes >= maxBytes || performance.now() - t0 >= maxSeconds * 1000) break;
    try {
      const got = await xhrUpload(size, (loaded, t) => {
        win.add(totalBytes + loaded, t);
        samples.push({
          t: t - t0,
          v: (win.instant(t) * 8) / 1e6,
        });
        report();
      }, signal);
      totalBytes += got;
      report(true);
    } catch {
      break;
    }
  }
  const elapsedMs = performance.now() - t0;
  if (totalBytes <= 0) throw new Error("هیچ داده‌ای ارسال نشد");
  report(true);
  return {
    avgMbps: ((totalBytes / (elapsedMs / 1000)) * 8) / 1e6,
    peakMbps: samples.reduce((m, s) => Math.max(m, s.v), 0),
    bytes: totalBytes,
    elapsedMs,
    samples,
  };
}

function xhrUpload(
  bytes: number,
  onProgress: (loaded: number, t: number) => void,
  signal: AbortSignal | undefined
): Promise<number> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/speedtest/upload", true);
    xhr.responseType = "text";
    let lastLoaded = 0;
    let settled = false;
    const cleanup = () => {
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      if (!settled) {
        settled = true;
        xhr.abort();
      }
    };
    signal?.addEventListener("abort", onAbort);
    xhr.upload.onprogress = (e) => {
      if (e.loaded > lastLoaded) {
        lastLoaded = e.loaded;
        onProgress(e.loaded, performance.now());
      }
    };
    xhr.onload = () => {
      settled = true;
      cleanup();
      if (xhr.status >= 200 && xhr.status < 300) resolve(bytes);
      else reject(new Error(`status ${xhr.status}`));
    };
    xhr.onerror = () => {
      settled = true;
      cleanup();
      reject(new Error("network"));
    };
    xhr.onabort = () => {
      settled = true;
      cleanup();
      // وقتی خودِ آزمون قطع شده، دادهٔ ارسالیِ ناتمام را جزو نتایج می‌شماریم
      resolve(lastLoaded);
    };
    try {
      xhr.send(makePayload(bytes));
    } catch (e) {
      cleanup();
      reject(e as Error);
    }
  });
}

/* ------------------------------ قالب‌بندی ------------------------------ */

const faNum = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 });
const faNum2 = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 });

export function faFormat(n: number, digits = 1): string {
  if (!Number.isFinite(n)) return "—";
  return (digits === 2 ? faNum2 : faNum).format(n);
}

export function formatMbps(mbps: number): string {
  if (!Number.isFinite(mbps) || mbps < 0) return "—";
  if (mbps >= 100) return faNum.format(Math.round(mbps));
  return faFormat(mbps, 1);
}

export function formatMs(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "—";
  return faFormat(Math.round(ms), 0);
}

export function formatDataSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${faFormat(bytes, 0)} بایت`;
  if (bytes < MB) return `${faFormat(bytes / 1024, 1)} کیلوبایت`;
  if (bytes < 1024 * MB) return `${faFormat(bytes / MB, 2)} مگابایت`;
  return `${faFormat(bytes / (1024 * MB), 2)} گیگابایت`;
}

export function faDateTime(iso: string | number | Date): string {
  const d = new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "short",
    timeStyle: "short",
  });
  return d.format(new Date(iso));
}

/** آستانه‌های خوانا برای مقیاس عقربه */
export function niceScaleMax(v: number): number {
  const candidates = [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000];
  const target = Math.max(v * 1.25, 1);
  for (const c of candidates) if (c >= target) return c;
  return Math.ceil(target / 1000) * 1000;
}
