// تست دانلود واقعی — داده باینری تصادفی را استریم می‌کند تا مرورگر بتواند
// سرعت واقعی انتقال را با خواندن جریان بایت‌ها (backpressure واقعی) اندازه بگیرد.
// هیچ کش و هیچ فشرده‌سازی روی این پاسخ اعمال نمی‌شود تا سرعت اندازه‌گیری‌شده
// دقیقاً برابر سرعت انتقال خام باشد.
import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";

// یک بافر یک مگابایتی از داده تصادفی که یک بار ساخته می‌شود و به‌صورت
// تکرارشونده ارسال می‌شود (محتوای تصادفی برای تست سرعت کاملاً کافی است؛
// نکته مهم خودِ انتقال بایت‌هاست).
const POOL_SIZE = 1024 * 1024;
const CHUNK_SIZE = 256 * 1024; // هر تکه ۲۵۶KB — تعادل بین سربار و نرمی جریان
const MIN_BYTES = 1024;
const MAX_BYTES = 64 * 1024 * 1024;

const pool = crypto.randomBytes(POOL_SIZE);

export async function GET(req: NextRequest) {
  const raw = Number(req.nextUrl.searchParams.get("bytes") ?? "1048576");
  let bytes = Number.isFinite(raw) ? Math.floor(raw) : 0;
  if (bytes < MIN_BYTES) bytes = MIN_BYTES;
  if (bytes > MAX_BYTES) bytes = MAX_BYTES;

  let sent = 0;
  let offset = 0;

  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (sent >= bytes) {
        controller.close();
        return;
      }
      const n = Math.min(CHUNK_SIZE, bytes - sent, POOL_SIZE - offset);
      // کپی نمی‌کنیم؛ زیرمجموعه‌ای از بافر مشترک به‌صورت فقط‌خواندنی صف می‌شود.
      controller.enqueue(pool.subarray(offset, offset + n));
      offset += n;
      if (offset >= POOL_SIZE) offset = 0;
      sent += n;
    },
  });

  return new NextResponse(stream, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Length": String(bytes),
      "Cache-Control": "no-store, no-transform",
      "X-Test-Bytes": String(bytes),
      "Content-Encoding": "none",
    },
  });
}
