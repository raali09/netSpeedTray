import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

// آدرس پایگاه‌داده در زمانِ اجرا قابل بازنویسی است:
//   • در ویجت ویندوزی، الکترون مسیرِ قابل‌نوشتنِ کاربر را از طریق
//     DATABASE_URL به سرور داخلی تزریق می‌کند (file:…/speedmeter.db).
//   • در حالت وب/توسعه، همان مسیر پیش‌فرضِ schema (db/custom.db) استفاده می‌شود.
const runtimeUrl = process.env.DATABASE_URL

export const db =
  globalForPrisma.prisma ??
  new PrismaClient({
    ...(runtimeUrl ? { datasourceUrl: runtimeUrl } : {}),
    log: process.env.NODE_ENV === 'development' ? ['query'] : [],
  })

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = db
