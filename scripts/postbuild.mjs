// پس از `next build`: سرور standalone را برای بسته‌بندی الکترون آماده می‌کند.
//
// نکتهٔ مهم دربارهٔ ساختار: electron-builder پوشهٔ «node_modules» در
// سطحِ ریشهٔ دایرکتوریِ منبعِ extraResources را همیشه حذف می‌کند
// (فیلتر داخلی createFilter). بنابراین سرور را یک سطح عمیق‌تر در
//   build/server-bundle/inner/
// قرار می‌دهیم تا node_modules آن «زیرپوشه» محسوب شود و کپی شود.
// خروجی نهایی در پکیج: resources/app-server/inner/

import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const standalone = path.join(root, ".next", "standalone");
const bundle = path.join(root, "build", "server-bundle", "inner");

if (!existsSync(standalone)) {
  console.error("postbuild: run `next build` first — .next/standalone not found");
  process.exit(1);
}

// ۰) بستهٔ قبلی را پاک کن
rmSync(path.dirname(bundle), { recursive: true, force: true });
mkdirSync(bundle, { recursive: true });

// ۱) کل خروجی standalone (server.js + node_modules + .next/…)
cpSync(standalone, bundle, { recursive: true });

// ۲) فایل‌های استاتیک Next — کنار server.js در .next/static
cpSync(path.join(root, ".next", "static"), path.join(bundle, ".next", "static"), {
  recursive: true,
});

// ۳) فایل‌های عمومی (لوگو و…)
if (existsSync(path.join(root, "public"))) {
  cpSync(path.join(root, "public"), path.join(bundle, "public"), { recursive: true });
}

// ۴) دیتابیس اولیهٔ خالی + schema — در اولین اجرای برنامه به پوشهٔ
//    قابل‌نوشتنِ کاربر (userData) کپی می‌شود.
const prismaDir = path.join(bundle, "prisma");
mkdirSync(prismaDir, { recursive: true });
const dbSeed = path.join(root, "db", "custom.db");
if (!existsSync(dbSeed)) {
  console.error("postbuild: db/custom.db not found — run `bun run db:push` first");
  process.exit(1);
}
cpSync(dbSeed, path.join(prismaDir, "speedmeter.db"));
cpSync(path.join(root, "prisma", "schema.prisma"), path.join(prismaDir, "schema.prisma"));

// ۵) اطمینان از حضور موتور Prisma در خروجی (دفاعی)
const prismaClientDir = path.join(root, "node_modules", ".prisma");
if (existsSync(prismaClientDir)) {
  cpSync(prismaClientDir, path.join(bundle, "node_modules", ".prisma"), { recursive: true });
}

// ۶) package.json مینیمال — Next فایل package.json کامل پروژه را داخل
//    standalone کپی می‌کند؛ اگر وابستگی‌ها در آن بمانند، electron-builder
//    هنگام بسته‌بندی node_modules را به app.asar منتقل می‌کند. سرور
//    standalone به این فایل نیازی ندارد (server.js آن را نمی‌خواند).
const pkg = JSON.parse(readFileSync(path.join(root, "package.json"), "utf8"));
const minimalPkg = {
  name: "speed-meter-server",
  version: pkg.version || "0.0.0",
  private: true,
};
writeFileSync(
  path.join(bundle, "package.json"),
  JSON.stringify(minimalPkg, null, 2) + "\n",
  "utf8"
);

console.log("postbuild: server bundle assembled at", path.dirname(bundle));
