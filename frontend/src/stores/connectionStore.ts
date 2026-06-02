/**
 * Connection Store - AutoCAD 连接状态 + 后端心跳
 */
import { create } from 'zustand';
import type { AutoCADStatus } from '@/types';

interface ConnectionState {
  autocadStatus: AutoCADStatus;
  isPolling: boolean;
  pollingInterval: number;

  isConnected: boolean;
  isConnecting: boolean;
  autocadVersion: string | null;
  activeDocument: string | null;
  connectionError: string | null;

  // 后端心跳
  backendOnline: boolean;

  // 截图
  snapshot: string | null;
  isSnapshotLoading: boolean;
  snapshotError: string | null;
  snapshotUrl: string | null;
}

interface ConnectionActions {
  setAutocadStatus: (status: AutoCADStatus) => void;
  setPolling: (polling: boolean) => void;
  setPollingInterval: (interval: number) => void;
  setIsConnected: (connected: boolean) => void;
  setIsConnecting: (connecting: boolean) => void;
  setAutocadVersion: (version: string | null) => void;
  setActiveDocument: (doc: string | null) => void;
  setConnectionError: (error: string | null) => void;
  setBackendOnline: (online: boolean) => void;
  setSnapshot: (data: string | null) => void;
  setSnapshotLoading: (loading: boolean) => void;
  setSnapshotError: (error: string | null) => void;
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
  autocadStatus: defaultStatus,
  isPolling: false,
  pollingInterval: 10000,

  isConnected: false,
  isConnecting: false,
  autocadVersion: null,
  activeDocument: null,
  connectionError: null,

  backendOnline: false,

  snapshot: null,
  isSnapshotLoading: false,
  snapshotError: null,
  snapshotUrl: null,

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

  setBackendOnline: (online) => set({ backendOnline: online }),

  setSnapshot: (data) => set({ snapshot: data }),
  setSnapshotLoading: (loading) => set({ isSnapshotLoading: loading }),
  setSnapshotError: (error) => set({ snapshotError: error }),

  setSnapshotUrl: (url) => set({ snapshotUrl: url }),
  setLoadingSnapshot: (loading) => set({ isSnapshotLoading: loading }),
}));
