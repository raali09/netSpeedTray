// تپ قلب اتصال — پاسخ همیشه کوچک و بدون کش است تا زمان سنجش واقعی رفت‌وبرگشت
// (RTT) ممکن باشد و وضعیت آنلاین/آفلاین به‌صورت فعال بررسی شود.
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(
    { ok: true, ts: Date.now() },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Content-Type": "application/json",
      },
    }
  );
}
