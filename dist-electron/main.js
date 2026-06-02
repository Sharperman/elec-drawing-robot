"use strict";
var __defProp = Object.defineProperty;
var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
const electron = require("electron");
const path = require("path");
const url = require("url");
const child_process = require("child_process");
const fs = require("fs");
var _documentCurrentScript = typeof document !== "undefined" ? document.currentScript : null;
class PythonBridge {
  constructor(options) {
    __publicField(this, "process", null);
    __publicField(this, "options");
    __publicField(this, "healthCheckInterval", null);
    __publicField(this, "healthCheckIntervalMs", 1e4);
    __publicField(this, "startupTimeoutMs", 3e4);
    this.options = options;
  }
  /**
   * 获取当前运行状态
   */
  getStatus() {
    var _a;
    return {
      running: this.process !== null && this.process.exitCode === null,
      pid: ((_a = this.process) == null ? void 0 : _a.pid) ?? null,
      port: this.options.port
    };
  }
  /**
   * 启动 Python 子进程
   */
  async start() {
    if (this.getStatus().running) {
      this.options.onLog("Python backend is already running");
      return;
    }
    if (!fs.existsSync(this.options.scriptPath)) {
      throw new Error(`Python script not found: ${this.options.scriptPath}`);
    }
    return new Promise((resolve, reject) => {
      var _a, _b;
      const pythonExecutable = this.findPythonExecutable();
      const env = {
        ...process.env,
        PYTHONPATH: path.dirname(path.dirname(this.options.scriptPath)),
        PYTHONUNBUFFERED: "1"
      };
      this.options.onLog(`Starting Python backend: ${pythonExecutable} ${this.options.scriptPath}`);
      this.process = child_process.spawn(pythonExecutable, [this.options.scriptPath], {
        env,
        cwd: path.dirname(path.dirname(this.options.scriptPath)),
        stdio: ["ignore", "pipe", "pipe"]
      });
      let started = false;
      const startupTimeout = setTimeout(() => {
        if (!started) {
          reject(new Error(`Python backend startup timeout after ${this.startupTimeoutMs}ms`));
        }
      }, this.startupTimeoutMs);
      (_a = this.process.stdout) == null ? void 0 : _a.on("data", (data) => {
        const msg = data.toString().trim();
        this.options.onLog(msg);
        if (msg.includes("Application startup complete") || msg.includes("Uvicorn running on")) {
          if (!started) {
            started = true;
            clearTimeout(startupTimeout);
            this.startHealthCheck();
            this.options.onStatusChange(this.getStatus());
            resolve();
          }
        }
      });
      (_b = this.process.stderr) == null ? void 0 : _b.on("data", (data) => {
        const msg = data.toString().trim();
        if (msg.includes("Application startup complete") || msg.includes("Uvicorn running on")) {
          this.options.onLog(msg);
          if (!started) {
            started = true;
            clearTimeout(startupTimeout);
            this.startHealthCheck();
            this.options.onStatusChange(this.getStatus());
            resolve();
          }
        } else {
          this.options.onError(msg);
        }
      });
      this.process.on("exit", (code, signal) => {
        this.options.onLog(`Python backend exited: code=${code} signal=${signal}`);
        this.process = null;
        this.stopHealthCheck();
        this.options.onStatusChange(this.getStatus());
        if (!started) {
          clearTimeout(startupTimeout);
          reject(new Error(`Python backend exited unexpectedly: code=${code}`));
        }
      });
      this.process.on("error", (err) => {
        this.options.onError(`Process error: ${err.message}`);
        this.process = null;
        this.stopHealthCheck();
        this.options.onStatusChange(this.getStatus());
        if (!started) {
          clearTimeout(startupTimeout);
          reject(err);
        }
      });
    });
  }
  /**
   * 停止 Python 子进程
   */
  async stop() {
    this.stopHealthCheck();
    if (!this.process) {
      return;
    }
    return new Promise((resolve) => {
      const proc = this.process;
      this.process = null;
      const killTimeout = setTimeout(() => {
        try {
          proc.kill("SIGKILL");
        } catch (_) {
        }
        resolve();
      }, 5e3);
      proc.on("exit", () => {
        clearTimeout(killTimeout);
        this.options.onStatusChange(this.getStatus());
        resolve();
      });
      try {
        proc.kill("SIGTERM");
      } catch (err) {
        clearTimeout(killTimeout);
        resolve();
      }
    });
  }
  /**
   * 启动健康检查定时器
   */
  startHealthCheck() {
    this.stopHealthCheck();
    this.healthCheckInterval = setInterval(async () => {
      const isAlive = await this.checkHealth();
      if (!isAlive && this.getStatus().running) {
        this.options.onError("Python backend health check failed");
      }
    }, this.healthCheckIntervalMs);
  }
  /**
   * 停止健康检查定时器
   */
  stopHealthCheck() {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }
  /**
   * 执行健康检查 HTTP 请求
   */
  async checkHealth() {
    try {
      const response = await fetch(`http://localhost:${this.options.port}/health`, {
        signal: AbortSignal.timeout(3e3)
      });
      return response.ok;
    } catch (_) {
      return false;
    }
  }
  /**
   * 查找 Python 可执行路径
   * 优先使用虚拟环境中的 python
   */
  findPythonExecutable() {
    const candidates = [
      // Windows 虚拟环境
      path.join(path.dirname(this.options.scriptPath), "..", "venv", "Scripts", "python.exe"),
      path.join(path.dirname(this.options.scriptPath), "..", ".venv", "Scripts", "python.exe"),
      // 系统 Python
      "python",
      "python3"
    ];
    for (const candidate of candidates) {
      if (candidate.includes(path.sep) && fs.existsSync(candidate)) {
        return candidate;
      }
    }
    return "python";
  }
}
const __dirname$1 = path.dirname(url.fileURLToPath(typeof document === "undefined" ? require("url").pathToFileURL(__filename).href : _documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === "SCRIPT" && _documentCurrentScript.src || new URL("main.js", document.baseURI).href));
const isDev = process.env.NODE_ENV === "development" || !electron.app.isPackaged;
let mainWindow = null;
let pythonBridge = null;
function createMainWindow() {
  mainWindow = new electron.BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    title: "电气图纸绘制机器人",
    webPreferences: {
      preload: path.join(__dirname$1, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    },
    backgroundColor: "#1e293b",
    show: false,
    titleBarStyle: "default"
  });
  mainWindow.once("ready-to-show", () => {
    mainWindow == null ? void 0 : mainWindow.show();
    if (isDev) {
      mainWindow == null ? void 0 : mainWindow.webContents.openDevTools({ mode: "detach" });
    }
  });
  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname$1, "../dist/index.html"));
  }
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}
function registerIpcHandlers() {
  electron.ipcMain.handle("python:status", () => {
    return (pythonBridge == null ? void 0 : pythonBridge.getStatus()) ?? { running: false, pid: null, port: 8765 };
  });
  electron.ipcMain.handle("python:start", async () => {
    if (!pythonBridge) return { success: false, error: "Bridge not initialized" };
    try {
      await pythonBridge.start();
      return { success: true };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  });
  electron.ipcMain.handle("python:stop", async () => {
    if (!pythonBridge) return { success: false, error: "Bridge not initialized" };
    try {
      await pythonBridge.stop();
      return { success: true };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  });
  electron.ipcMain.handle("dialog:openFile", async (_, filters) => {
    const result = await electron.dialog.showOpenDialog(mainWindow, {
      properties: ["openFile"],
      filters: filters ?? [{ name: "图片文件", extensions: ["png", "jpg", "jpeg", "bmp", "tiff"] }]
    });
    return result;
  });
  electron.ipcMain.handle("theme:toggle", () => {
    electron.nativeTheme.themeSource = electron.nativeTheme.shouldUseDarkColors ? "light" : "dark";
    return electron.nativeTheme.shouldUseDarkColors;
  });
  electron.ipcMain.handle("app:version", () => electron.app.getVersion());
}
electron.app.whenReady().then(async () => {
  const backendPath = isDev ? path.join(__dirname$1, "../../backend/main.py") : path.join(process.resourcesPath, "backend/main.py");
  pythonBridge = new PythonBridge({
    scriptPath: backendPath,
    port: 8765,
    onLog: (msg) => {
      console.log(`[Python] ${msg}`);
      mainWindow == null ? void 0 : mainWindow.webContents.send("python:log", msg);
    },
    onError: (err) => {
      console.error(`[Python Error] ${err}`);
      mainWindow == null ? void 0 : mainWindow.webContents.send("python:error", err);
    },
    onStatusChange: (status) => {
      mainWindow == null ? void 0 : mainWindow.webContents.send("python:statusChange", status);
    }
  });
  registerIpcHandlers();
  createMainWindow();
  try {
    await pythonBridge.start();
    console.log("[Main] Python backend started successfully");
  } catch (err) {
    console.error("[Main] Failed to start Python backend:", err);
  }
});
electron.app.on("window-all-closed", async () => {
  try {
    await (pythonBridge == null ? void 0 : pythonBridge.stop());
  } catch (_) {
  }
  if (process.platform !== "darwin") {
    electron.app.quit();
  }
});
electron.app.on("activate", () => {
  if (electron.BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});
const gotLock = electron.app.requestSingleInstanceLock();
if (!gotLock) {
  electron.app.quit();
} else {
  electron.app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}
