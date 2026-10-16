// پل امن بین صفحهٔ وب و فرایند اصلی الکترون — تنها نقطهٔ تماس
// صفحه با قابلیت‌های دسکتاپ (بدون دسترسی مستقیم Node در صفحه).

"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("speedmeter", {
  isDesktop: true,
  openMain: () => ipcRenderer.invoke("sm:open-main"),
  openWidget: () => ipcRenderer.invoke("sm:open-widget"),
  hideWidget: () => ipcRenderer.invoke("sm:hide-widget"),
  quit: () => ipcRenderer.invoke("sm:quit"),
});
