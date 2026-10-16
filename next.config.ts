import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // آزمون سرعت نیاز به پاسخ خام و بدون کش/فشرده‌سازی دارد.
  // (هدرهای no-store در خود API routeها تنظیم می‌شوند.)
  reactStrictMode: false,
};

export default nextConfig;
