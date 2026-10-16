// الکترون — «آزمونگر سرعت» به‌صورت ویجت ویندوزی
// ------------------------------------------------------------------
// • سرور Next.js (نسخهٔ standalone) داخل خودِ برنامه اجرا می‌شود؛
//   بنابراین ویجت کاملاً آفلاین-محور و مستقل است (بدون نیاز به XAMPP و…).
// • دو پنجره: «ویجت» کوچکِ بدون قاب و همیشه‌بالای صفحه + «پنجرهٔ اصلی».
// • آیکون در system tray با منوی فارسی (نمایش/مخفی، اجرای خودکار و…).
// • پایگاه‌داده در پوشهٔ قابل‌نوشتنِ کاربر (userData) کپی می‌شود.

"use strict";

const { app, BrowserWindow, Tray, Menu, ipcMain, dialog } = require("electron");
const { fork, spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const net = require("net");

// در حالت توسعهٔ دسکتاپ، به‌جای سرور داخلی به dev server وصل می‌شویم:
//   SPEEDMETER_DEV_URL=http://localhost:3000 bun run desktop:dev
const DEV_SERVER_URL = process.env.SPEEDMETER_DEV_URL || "";
const SERVER_START_TIMEOUT_MS = 25000;
const MAX_SERVER_RESTARTS = 5;

let serverProc = null;
let serverPort = 0;
let baseUrl = "";
let widgetWindow = null;
let mainWindow = null;
let tray = null;
let alwaysOnTop = true;
let restarts = 0;
let isQuitting = false;

/* ------------------------------ ابزارها ------------------------------ */

function isDev() {
  return !app.isPackaged;
}

function trayIconPath() {
  // در بستهٔ نهایی کنار منابع، در حالت توسعه از پوشهٔ build پروژه
  return isDev()
    ? path.join(__dirname, "..", "build", "icon.png")
    : path.join(process.resourcesPath, "icon.png");
}

function appServerDir() {
  // سرور Next داخل resources/app-server/inner قرار دارد (ساختار
  // یک‌سطح-عمیق‌تر برای دورزدن فیلتر node_modules در electron-builder)
  return path.join(process.resourcesPath, "app-server", "inner");
}

function userDbPath() {
  return path.join(app.getPath("userData"), "speedmeter.db");
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

async function waitHttp(url, timeoutMs) {
  const t0 = Date.now();
  for (;;) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) return;
    } catch {
      /* هنوز بالا نیامده */
    }
    if (Date.now() - t0 > timeoutMs) {
      throw new Error("timeout waiting for " + url);
    }
    await new Promise((r) => setTimeout(r, 250));
  }
}

/* --------------------------- سرور داخلی --------------------------- */

async function startServer() {
  if (DEV_SERVER_URL) {
    baseUrl = DEV_SERVER_URL;
    return;
  }

  const dir = appServerDir();
  const serverFile = path.join(dir, "server.js");
  if (!fs.existsSync(serverFile)) {
    throw new Error("server.js not found in resources (app-server)");
  }

  serverPort = await getFreePort();
  baseUrl = `http://127.0.0.1:${serverPort}`;

  // پایگاه‌دادهٔ SQLite در مسیر قابل‌نوشتنِ کاربر — دفعهٔ اول از
  // نسخهٔ اولیهٔ همراهِ برنامه کپی می‌شود.
  const dbPath = userDbPath();
  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  if (!fs.existsSync(dbPath)) {
    const seed = path.join(dir, "prisma", "speedmeter.db");
    if (!fs.existsSync(seed)) {
      throw new Error("seed database not found: " + seed);
    }
    fs.copyFileSync(seed, dbPath);
  }

  const env = Object.assign({}, process.env, {
    PORT: String(serverPort),
    HOSTNAME: "127.0.0.1",
    NODE_ENV: "production",
    // آدرس مطلق خام (بدون کدگذاری URL) — Prisma مسیر خام با فاصله را
    // می‌پذیرد اما %20 را نه؛ برای سازگاری ویندوز، اسلش‌ها یکدست می‌شوند.
    DATABASE_URL: "file:" + dbPath.split(path.sep).join("/"),
  });

  serverProc = fork(serverFile, [], {
    cwd: dir,
    env,
    stdio: ["ignore", "pipe", "pipe", "ipc"],
  });
  serverProc.stdout.on("data", (d) => process.stdout.write("[server] " + d));
  serverProc.stderr.on("data", (d) => process.stderr.write("[server] " + d));
  serverProc.on("exit", (code) => {
    serverProc = null;
    if (!isQuitting) {
      console.error("[main] internal server exited with code", code);
      scheduleServerRestart();
    }
  });

  await waitHttp(`${baseUrl}/api/heartbeat`, SERVER_START_TIMEOUT_MS);
}

function killServer() {
  if (!serverProc) return;
  const proc = serverProc;
  serverProc = null;
  try {
    if (process.platform === "win32") {
      // در ویندوز باید کل درختِ فرایند بسته شود
      spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"]);
    } else {
      proc.kill("SIGTERM");
    }
  } catch (err) {
    console.error("[main] kill server failed:", err);
  }
}

function scheduleServerRestart() {
  if (isQuitting) return;
  restarts += 1;
  if (restarts > MAX_SERVER_RESTARTS) {
    dialog.showErrorBox(
      "خطای سرور داخلی",
      "سرور داخلی برنامه پس از چند بار تلاش بالا نیامد. برنامه بسته می‌شود."
    );
    app.quit();
    return;
  }
  setTimeout(() => {
    startServer()
      .then(reloadWindows)
      .catch((err) => {
        console.error("[main] server restart failed:", err);
        dialog.showErrorBox("خطای سرور داخلی", String(err));
        app.quit();
      });
  }, 1500);
}

function reloadWindows() {
  if (widgetWindow && !widgetWindow.isDestroyed()) {
    widgetWindow.loadURL(`${baseUrl}/?widget=1`);
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadURL(`${baseUrl}/`);
  }
}

/* ----------------------------- پنجره‌ها ----------------------------- */

function createWidgetWindow() {
  if (widgetWindow && !widgetWindow.isDestroyed()) {
    widgetWindow.show();
    widgetWindow.focus();
    return;
  }
  widgetWindow = new BrowserWindow({
    width: 380,
    height: 300,
    minWidth: 300,
    minHeight: 200,
    frame: false, // بدون نوار عنوان — یک ویجت واقعی
    resizable: true,
    alwaysOnTop,
    skipTaskbar: true,
    backgroundColor: "#0A1017",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // چیدمان در گوشهٔ پایین-چپِ محلی کار (نزدیک ساعت و system tray)
  try {
    const area = require("electron").screen.getPrimaryDisplay().workArea;
    widgetWindow.setPosition(area.x + 16, area.y + area.height - widgetWindow.getBounds().height - 16);
  } catch {
    /* در دسترس نبودن صفحه — پیش‌فرض */
  }

  widgetWindow.once("ready-to-show", () => widgetWindow.show());
  widgetWindow.on("close", (e) => {
    if (!isQuitting && tray) {
      e.preventDefault();
      widgetWindow.hide();
    }
  });
  widgetWindow.loadURL(`${baseUrl}/?widget=1`);
}

function createMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
    return;
  }
  mainWindow = new BrowserWindow({
    width: 1240,
    height: 900,
    minWidth: 400,
    minHeight: 560,
    backgroundColor: "#0A1017",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("close", (e) => {
    if (!isQuitting && tray) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
  mainWindow.loadURL(`${baseUrl}/`);
}

/* ------------------------------- tray ------------------------------- */

function rebuildTrayMenu() {
  if (!tray) return;
  const menu = Menu.buildFromTemplate([
    { label: "نمایش / مخفی ویجت", click: () => toggleWidget() },
    { label: "پنجرهٔ اصلی", click: () => createMainWindow() },
    { type: "separator" },
    {
      label: "همیشه روی همهٔ پنجره‌ها",
      type: "checkbox",
      checked: alwaysOnTop,
      click: (item) => {
        alwaysOnTop = item.checked;
        if (widgetWindow && !widgetWindow.isDestroyed()) {
          widgetWindow.setAlwaysOnTop(alwaysOnTop);
        }
      },
    },
    {
      label: "اجرای خودکار با ورود به ویندوز",
      type: "checkbox",
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => {
        app.setLoginItemSettings({ openAtLogin: item.checked });
      },
    },
    { type: "separator" },
    { label: "خروج", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
  tray.setToolTip("آزمونگر سرعت — ویجت سرعت اینترنت");
}

function toggleWidget() {
  if (!widgetWindow || widgetWindow.isDestroyed()) {
    createWidgetWindow();
    return;
  }
  if (widgetWindow.isVisible()) {
    widgetWindow.hide();
  } else {
    widgetWindow.show();
    widgetWindow.focus();
  }
}

function createTray() {
  const iconFile = trayIconPath();
  if (!fs.existsSync(iconFile)) {
    console.warn("[main] tray icon not found:", iconFile);
    return;
  }
  tray = new Tray(iconFile);
  tray.on("double-click", () => toggleWidget());
  rebuildTrayMenu();
}

/* ------------------------------ IPC ------------------------------ */

function registerIpc() {
  ipcMain.handle("sm:open-main", () => createMainWindow());
  ipcMain.handle("sm:open-widget", () => createWidgetWindow());
  ipcMain.handle("sm:hide-widget", () => {
    if (widgetWindow && !widgetWindow.isDestroyed()) widgetWindow.hide();
  });
  ipcMain.handle("sm:quit", () => app.quit());
}

/* ------------------------------ چرخهٔ عمر ------------------------------ */

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => toggleWidget());

  app.whenReady().then(async () => {
    try {
      await startServer();
    } catch (err) {
      dialog.showErrorBox(
        "خطا در اجرای سرور داخلی",
        "سرور داخلی برنامه بالا نیامد:\n\n" + String(err)
      );
      app.quit();
      return;
    }

    registerIpc();
    createTray();
    createWidgetWindow();

    // بار اول پنجرهٔ اصلی هم باز شود تا کاربر کل برنامه را ببیند؛
    // دفعات بعد فقط ویجت.
    const seenMarker = path.join(app.getPath("userData"), ".seen-main");
    if (!fs.existsSync(seenMarker)) {
      createMainWindow();
      try {
        fs.writeFileSync(seenMarker, String(Date.now()));
      } catch {
        /* فقط یک نشانگر است */
      }
    }
  });

  app.on("window-all-closed", () => {
    // برنامه در tray زنده می‌ماند (رفتار استاندارد ویجت‌ها)
  });

  app.on("before-quit", () => {
    isQuitting = true;
    killServer();
  });

  app.on("will-quit", () => {
    isQuitting = true;
    killServer();
  });
}
