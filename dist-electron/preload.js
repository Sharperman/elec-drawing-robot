"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("electronAPI", {
  // ---- Python 后端管理 ----
  python: {
    /** 获取 Python 服务运行状态 */
    getStatus: () => electron.ipcRenderer.invoke("python:status"),
    /** 启动 Python 服务 */
    start: () => electron.ipcRenderer.invoke("python:start"),
    /** 停止 Python 服务 */
    stop: () => electron.ipcRenderer.invoke("python:stop"),
    /** 监听 Python 日志输出 */
    onLog: (callback) => {
      electron.ipcRenderer.on("python:log", (_, msg) => callback(msg));
    },
    /** 监听 Python 错误输出 */
    onError: (callback) => {
      electron.ipcRenderer.on("python:error", (_, err) => callback(err));
    },
    /** 监听 Python 服务状态变化 */
    onStatusChange: (callback) => {
      electron.ipcRenderer.on("python:statusChange", (_, status) => callback(status));
    },
    /** 移除 Python 状态变化监听器 */
    removeStatusChangeListener: () => {
      electron.ipcRenderer.removeAllListeners("python:statusChange");
    }
  },
  // ---- 对话框 ----
  dialog: {
    /** 打开文件选择对话框 */
    openFile: (filters) => electron.ipcRenderer.invoke("dialog:openFile", filters)
  },
  // ---- 主题 ----
  theme: {
    /** 切换暗/亮主题 */
    toggle: () => electron.ipcRenderer.invoke("theme:toggle")
  },
  // ---- 应用信息 ----
  app: {
    /** 获取应用版本号 */
    getVersion: () => electron.ipcRenderer.invoke("app:version")
  }
});
