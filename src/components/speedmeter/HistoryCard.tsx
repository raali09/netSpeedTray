"use client";

// تاریخچهٔ آزمون‌ها — منبع اصلی سرور (Prisma) است؛ اما اگر اینترنت قطع
// باشد، نسخهٔ محلی (localStorage) همچنان قابل مشاهده است تا کاربر در قطعی هم
// به داده‌های خود دسترسی داشته باشد.

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { History, Trash2, Download, Upload, Activity, Waves, Server, HardDrive } from "lucide-react";
import { faDateTime, faFormat } from "@/lib/speedtest";
import type { HistoryItem } from "@/lib/types";

interface HistoryCardProps {
  items: HistoryItem[];
  onClear: () => void;
  loading?: boolean;
}

export function HistoryCard({ items, onClear, loading }: HistoryCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <History className="size-4 text-cyan-400" />
              تاریخچهٔ آزمون‌ها
            </CardTitle>
            <CardDescription className="mt-1 text-xs">
              نتایج در پایگاه‌داده ذخیره می‌شوند و در قطعی اینترنت از نسخهٔ محلی قابل مشاهده‌اند
            </CardDescription>
          </div>
          {items.length > 0 && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 text-rose-400 border-rose-500/30 hover:bg-rose-500/10 hover:text-rose-300">
                  <Trash2 className="ml-1.5 size-3.5" />
                  پاک‌کردن
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent dir="rtl" className="max-w-sm">
                <AlertDialogHeader className="text-right items-start">
                  <AlertDialogTitle>پاک‌کردن کل تاریخچه؟</AlertDialogTitle>
                  <AlertDialogDescription className="text-right">
                    همهٔ نتایج از سرور و حافظهٔ محلی حذف می‌شوند. این کار بازگشت‌پذیر نیست.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogAction
                    onClick={onClear}
                    className="bg-rose-600 hover:bg-rose-500"
                  >
                    بله، پاک کن
                  </AlertDialogAction>
                  <AlertDialogCancel>انصراف</AlertDialogCancel>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex-1">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-10 text-center text-sm text-muted-foreground">
            <History className="size-8 opacity-30" />
            {loading ? "در حال دریافت…" : "هنوز آزمونی ثبت نشده است — اولین آزمون را اجرا کنید"}
          </div>
        ) : (
          <div className="max-h-72 overflow-y-auto overflow-x-auto custom-scroll rounded-lg border">
            <Table dir="rtl">
              <TableHeader className="sticky top-0 bg-[#16202B] z-10">
                <TableRow className="hover:bg-transparent border-border/60">
                  <TableHead className="text-right h-9">زمان</TableHead>
                  <TableHead className="text-center h-9">
                    <Download className="inline size-3 text-cyan-400" />
                  </TableHead>
                  <TableHead className="text-center h-9">
                    <Upload className="inline size-3 text-amber-400" />
                  </TableHead>
                  <TableHead className="text-center h-9">
                    <Activity className="inline size-3 text-emerald-400" />
                  </TableHead>
                  <TableHead className="text-center h-9">
                    <Waves className="inline size-3 text-violet-400" />
                  </TableHead>
                  <TableHead className="text-center h-9">منبع</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it) => (
                  <TableRow key={it.id} className="border-border/50">
                    <TableCell className="text-right text-[11px] text-muted-foreground whitespace-nowrap py-2">
                      {faDateTime(it.createdAt)}
                    </TableCell>
                    <TableCell className="text-center py-2 font-bold tnum text-cyan-400">
                      {faFormat(it.download, 1)}
                    </TableCell>
                    <TableCell className="text-center py-2 font-bold tnum text-amber-400">
                      {faFormat(it.upload, 1)}
                    </TableCell>
                    <TableCell className="text-center py-2 tnum text-emerald-400">
                      {faFormat(Math.round(it.ping), 0)}
                    </TableCell>
                    <TableCell className="text-center py-2 tnum text-violet-400">
                      {faFormat(Math.round(it.jitter), 0)}
                    </TableCell>
                    <TableCell className="text-center py-2">
                      {it.source === "server" ? (
                        <Badge variant="outline" className="h-4 px-1.5 text-[9px] gap-1 border-emerald-500/40 text-emerald-400">
                          <Server className="size-2.5" />
                          سرور
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="h-4 px-1.5 text-[9px] gap-1 border-amber-500/40 text-amber-400">
                          <HardDrive className="size-2.5" />
                          محلی
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
