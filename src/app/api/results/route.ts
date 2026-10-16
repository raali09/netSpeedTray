// تاریخچه آزمون‌های سرعت — ذخیره و بازیابی از پایگاه‌داده (Prisma).
// اگر کلاینت آفلاین باشد، خودش نتایج را به‌صورت محلی نگه می‌دارد و هنگام
// اتصال دوباره می‌تواند ذخیره کند.
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";

export const dynamic = "force-dynamic";

const resultSchema = z.object({
  download: z.number().min(0).max(1000000),
  upload: z.number().min(0).max(1000000),
  ping: z.number().min(0).max(60000),
  jitter: z.number().min(0).max(60000).default(0),
});

export async function GET() {
  try {
    const rows = await db.testResult.findMany({
      orderBy: { createdAt: "desc" },
      take: 20,
    });
    return NextResponse.json(
      { ok: true, rows },
      { headers: { "Cache-Control": "no-store" } }
    );
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: (e as Error).message, rows: [] },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const parsed = resultSchema.safeParse(body);
    if (!parsed.success) {
      return NextResponse.json(
        { ok: false, error: "داده نامعتبر" },
        { status: 400 }
      );
    }
    const row = await db.testResult.create({
      data: {
        download: parsed.data.download,
        upload: parsed.data.upload,
        ping: parsed.data.ping,
        jitter: parsed.data.jitter,
      },
    });
    return NextResponse.json({ ok: true, row }, { status: 201 });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: (e as Error).message },
      { status: 500 }
    );
  }
}

export async function DELETE() {
  try {
    await db.testResult.deleteMany({});
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: (e as Error).message },
      { status: 500 }
    );
  }
}
