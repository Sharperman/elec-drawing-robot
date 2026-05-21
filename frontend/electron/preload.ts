/**
 * Electron Preload 脚本
 * 通过 contextBridge 安全地将 IPC 接口暴露给渲染进程
 */
import { contextBridge, ipcRenderer } from 'electron';

// ============================================================
// 类型定义
// ============================================================

interface PythonStatus {
  running: boolean;
  pid: number | null;
  port: number;
}

interface DialogFilter {
  name: string;
  extensions: string[];
}

interface DialogResult {
  canceled: boolean;
  filePaths: string[];
}

interface IpcResult<T = void> {
  success: boolean;
  data?: T;
  error?: string;
}

// ============================================================
// 暴露给渲染进程的 API
// ============================================================

contextBridge.exposeInMainWorld('electronAPI', {
  // ---- Python 后端管理 ----
  python: {
    /** 获取 Python 服务运行状态 */
    getStatus: (): Promise<PythonStatus> =>
      ipcRenderer.invoke('python:status'),

    /** 启动 Python 服务 */
    start: (): Promise<IpcResult> =>
      ipcRenderer.invoke('python:start'),

    /** 停止 Python 服务 */
    stop: (): Promise<IpcResult> =>
      ipcRenderer.invoke('python:stop'),

    /** 监听 Python 日志输出 */
    onLog: (callback: (msg: string) => void) => {
      ipcRenderer.on('python:log', (_, msg) => callback(msg));
    },

    /** 监听 Python 错误输出 */
    onError: (callback: (err: string) => void) => {
      ipcRenderer.on('python:error', (_, err) => callback(err));
    },

    /** 监听 Python 服务状态变化 */
    onStatusChange: (callback: (status: PythonStatus) => void) => {
      ipcRenderer.on('python:statusChange', (_, status) => callback(status));
    },

    /** 移除 Python 状态变化监听器 */
    removeStatusChangeListener: () => {
      ipcRenderer.removeAllListeners('python:statusChange');
    },
  },

  // ---- 对话框 ----
  dialog: {
    /** 打开文件选择对话框 */
    openFile: (filters?: DialogFilter[]): Promise<DialogResult> =>
      ipcRenderer.invoke('dialog:openFile', filters),
  },

  // ---- 主题 ----
  theme: {
    /** 切换暗/亮主题 */
    toggle: (): Promise<boolean> =>
      ipcRenderer.invoke('theme:toggle'),
  },

  // ---- 应用信息 ----
  app: {
    /** 获取应用版本号 */
    getVersion: (): Promise<string> =>
      ipcRenderer.invoke('app:version'),
  },
});

// ============================================================
// TypeScript 类型声明（供渲染进程使用）
// ============================================================

declare global {
  interface Window {
    electronAPI: {
      python: {
        getStatus: () => Promise<PythonStatus>;
        start: () => Promise<IpcResult>;
        stop: () => Promise<IpcResult>;
        onLog: (callback: (msg: string) => void) => void;
        onError: (callback: (err: string) => void) => void;
        onStatusChange: (callback: (status: PythonStatus) => void) => void;
        removeStatusChangeListener: () => void;
      };
      dialog: {
        openFile: (filters?: DialogFilter[]) => Promise<DialogResult>;
      };
      theme: {
        toggle: () => Promise<boolean>;
      };
      app: {
        getVersion: () => Promise<string>;
      };
    };
  }
}
