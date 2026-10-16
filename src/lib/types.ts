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
