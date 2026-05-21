/**
 * Connection Store - AutoCAD 连接状态
 * 扩展版：添加 isConnected/isConnecting/autocadVersion/activeDocument/connectionError
 * 以及 snapshot(base64)/isSnapshotLoading/snapshotError 供 AutoCADPreview 使用
 */
import { create } from 'zustand';
import type { AutoCADStatus } from '@/types';

interface ConnectionState {
  // ── 原有字段（兼容 useAutoCAD hook） ───────────────────────────
  autocadStatus: AutoCADStatus;
  isPolling: boolean;
  pollingInterval: number; // 毫秒

  // ── 派生便捷字段（供 StatusBar / AutoCADPreview 直接使用） ─────
  isConnected: boolean;
  isConnecting: boolean;
  autocadVersion: string | null;
  activeDocument: string | null;
  connectionError: string | null;

  // ── 截图（base64 字符串，供 AutoCADPreview 使用） ──────────────
  snapshot: string | null;
  isSnapshotLoading: boolean;
  snapshotError: string | null;

  // ── 兼容旧字段（保留，部分 hook 可能引用） ─────────────────────
  snapshotUrl: string | null;
}

interface ConnectionActions {
  setAutocadStatus: (status: AutoCADStatus) => void;
  setPolling: (polling: boolean) => void;
  setPollingInterval: (interval: number) => void;

  // 派生便捷字段
  setIsConnected: (connected: boolean) => void;
  setIsConnecting: (connecting: boolean) => void;
  setAutocadVersion: (version: string | null) => void;
  setActiveDocument: (doc: string | null) => void;
  setConnectionError: (error: string | null) => void;

  // 截图
  setSnapshot: (data: string | null) => void;
  setSnapshotLoading: (loading: boolean) => void;
  setSnapshotError: (error: string | null) => void;

  // 旧接口保留
  setSnapshotUrl: (url: string | null) => void;
  setLoadingSnapshot: (loading: boolean) => void;
}

const defaultStatus: AutoCADStatus = {
  connected: false,
  drawing_name: undefined,
  drawing_path: undefined,
  autocad_version: undefined,
  entity_count: 0,
  last_check: new Date().toISOString(),
};

export const useConnectionStore = create<ConnectionState & ConnectionActions>()((set) => ({
  // 初始值
  autocadStatus: defaultStatus,
  isPolling: false,
  pollingInterval: 10000,

  isConnected: false,
  isConnecting: false,
  autocadVersion: null,
  activeDocument: null,
  connectionError: null,

  snapshot: null,
  isSnapshotLoading: false,
  snapshotError: null,

  // 旧字段保留
  snapshotUrl: null,

  // ── Actions ─────────────────────────────────────────────────────────────

  setAutocadStatus: (status) => {
    set({
      autocadStatus: status,
      isConnected: status.connected,
      autocadVersion: status.autocad_version ?? null,
      activeDocument: status.drawing_name ?? null,
      connectionError: null,
    });
  },

  setPolling: (polling) => set({ isPolling: polling }),
  setPollingInterval: (interval) => set({ pollingInterval: interval }),

  setIsConnected: (connected) => set({ isConnected: connected }),
  setIsConnecting: (connecting) => set({ isConnecting: connecting }),
  setAutocadVersion: (version) => set({ autocadVersion: version }),
  setActiveDocument: (doc) => set({ activeDocument: doc }),
  setConnectionError: (error) => set({ connectionError: error }),

  setSnapshot: (data) => set({ snapshot: data }),
  setSnapshotLoading: (loading) => set({ isSnapshotLoading: loading }),
  setSnapshotError: (error) => set({ snapshotError: error }),

  // 旧接口
  setSnapshotUrl: (url) => set({ snapshotUrl: url }),
  setLoadingSnapshot: (loading) => set({ isSnapshotLoading: loading }),
}));
