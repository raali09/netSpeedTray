import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "آزمونگر سرعت اینترنت | اندازه‌گیری واقعی",
  description:
    "آزمون سرعت دانلود و آپلود بر پایه انتقال واقعی داده، همراه با پایش زنده پینگ و تشخیص دقیق قطعی اینترنت — متمایز از حالت بدون ترافیک.",
  icons: {
    icon: "/logo.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#0A1017",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fa" dir="rtl" className="dark" suppressHydrationWarning>
      <head>
        {/* فونت وزیرمتن از سمت مرورگر کاربر بارگذاری می‌شود؛ در صورت قطعی،
            فونت‌های جایگزین سیستم (Tahoma) به‌کار می‌روند. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased bg-background text-foreground min-h-screen">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
