// انواع مشترک برنامه
export interface HistoryItem {
  id: string;
  download: number; // Mbps
  upload: number; // Mbps
  ping: number; // ms
  jitter: number; // ms
  createdAt: string; // ISO
  source: "server" | "local";
}

// پل ارتباطی با دسکتاپ (الکترون) — فقط داخل ویجت ویندوزی موجود است
// و توسط electron/preload.js تزریق می‌شود.
export interface SpeedMeterDesktopBridge {
  isDesktop: true;
  openMain: () => void;
  openWidget: () => void;
  hideWidget: () => void;
  quit: () => void;
}

declare global {
  interface Window {
    speedmeter?: SpeedMeterDesktopBridge;
  }
}
