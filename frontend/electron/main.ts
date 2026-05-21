/**
 * Electron 主进程
 * 负责：创建浏览器窗口、管理应用生命周期、启动 Python 子进程
 */
import { app, BrowserWindow, ipcMain, dialog, nativeTheme } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url';
import { PythonBridge } from './utils/pythonBridge';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 开发模式判断
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

let mainWindow: BrowserWindow | null = null;
let pythonBridge: PythonBridge | null = null;

/**
 * 创建主窗口
 */
function createMainWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    title: '电气图纸绘制机器人',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    backgroundColor: '#1e293b',
    show: false,
    titleBarStyle: 'default',
  });

  // 窗口就绪后显示，避免白屏
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
    if (isDev) {
      mainWindow?.webContents.openDevTools({ mode: 'detach' });
    }
  });

  // 加载页面
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * 注册 IPC 处理器
 */
function registerIpcHandlers(): void {
  // 获取 Python 服务状态
  ipcMain.handle('python:status', () => {
    return pythonBridge?.getStatus() ?? { running: false, pid: null, port: 8765 };
  });

  // 启动 Python 服务
  ipcMain.handle('python:start', async () => {
    if (!pythonBridge) return { success: false, error: 'Bridge not initialized' };
    try {
      await pythonBridge.start();
      return { success: true };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  });

  // 停止 Python 服务
  ipcMain.handle('python:stop', async () => {
    if (!pythonBridge) return { success: false, error: 'Bridge not initialized' };
    try {
      await pythonBridge.stop();
      return { success: true };
    } catch (err) {
      return { success: false, error: String(err) };
    }
  });

  // 打开文件对话框
  ipcMain.handle('dialog:openFile', async (_, filters) => {
    const result = await dialog.showOpenDialog(mainWindow!, {
      properties: ['openFile'],
      filters: filters ?? [{ name: '图片文件', extensions: ['png', 'jpg', 'jpeg', 'bmp', 'tiff'] }],
    });
    return result;
  });

  // 主题切换
  ipcMain.handle('theme:toggle', () => {
    nativeTheme.themeSource = nativeTheme.shouldUseDarkColors ? 'light' : 'dark';
    return nativeTheme.shouldUseDarkColors;
  });

  // 获取应用版本
  ipcMain.handle('app:version', () => app.getVersion());
}

// ============================================================
// 应用生命周期
// ============================================================

app.whenReady().then(async () => {
  // 初始化 Python 桥接器
  const backendPath = isDev
    ? path.join(__dirname, '../../backend/main.py')
    : path.join(process.resourcesPath, 'backend/main.py');

  pythonBridge = new PythonBridge({
    scriptPath: backendPath,
    port: 8765,
    onLog: (msg) => {
      console.log(`[Python] ${msg}`);
      mainWindow?.webContents.send('python:log', msg);
    },
    onError: (err) => {
      console.error(`[Python Error] ${err}`);
      mainWindow?.webContents.send('python:error', err);
    },
    onStatusChange: (status) => {
      mainWindow?.webContents.send('python:statusChange', status);
    },
  });

  registerIpcHandlers();
  createMainWindow();

  // 自动启动 Python 后端
  try {
    await pythonBridge.start();
    console.log('[Main] Python backend started successfully');
  } catch (err) {
    console.error('[Main] Failed to start Python backend:', err);
    // 不阻断前端启动，让用户手动连接
  }
});

app.on('window-all-closed', async () => {
  try {
    await pythonBridge?.stop();
  } catch (_) {
    // ignore
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});

// 防止多实例
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}
