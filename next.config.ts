import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // خروجی standalone — برای اجرای سرور داخلی داخل ویجت الکترون
  // (`node .next/standalone/server.js` پس از build)
  output: "standalone",
  reactStrictMode: false,
};

export default nextConfig;
