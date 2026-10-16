// تست آپلود واقعی — بدنه درخواست را کامل می‌خواند و حجم دریافتی را تأیید
// می‌کند. سنجش زمان آپلود سمت مرورگر با رویدادهای پیشرفت XHR انجام می‌شود.
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const buf = await req.arrayBuffer();
  return NextResponse.json(
    {
      ok: true,
      received: buf.byteLength,
      receivedHuman: (buf.byteLength / (1024 * 1024)).toFixed(2) + " MiB",
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    }
  );
}
