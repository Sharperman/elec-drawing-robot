/**
 * useAutoCAD Hook - AutoCAD 连接状态轮询和手动重连
 */
import { useCallback, useEffect, useRef } from 'react';
import toast from 'react-hot-toast';

import apiClient from '@/services/apiClient';
import { useConnectionStore } from '@/stores/connectionStore';
import type { AutoCADStatus } from '@/types';

export function useAutoCAD() {
  const {
    autocadStatus,
    isPolling,
    pollingInterval,
    snapshotUrl,
    snapshotError,
    setAutocadStatus,
    setPolling,
    setSnapshotUrl,
    setSnapshotError,
    setLoadingSnapshot,
    setSnapshot,
    setSnapshotLoading,
    setConnectionError,
    setIsConnecting,
    setIsConnected,
  } = useConnectionStore();

  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const snapshotTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  /**
   * 查询 AutoCAD 连接状态
   */
  const checkStatus = useCallback(async (): Promise<AutoCADStatus | null> => {
    try {
      const resp = await apiClient.get<{ data: AutoCADStatus }>('/api/autocad/status');
      const status = resp.data.data;
      setAutocadStatus(status);
      return status;
    } catch (_) {
      return null;
    }
  }, [setAutocadStatus]);

  /**
   * 连接 AutoCAD
   */
  const connect = useCallback(async (version?: string) => {
    setIsConnecting(true);
    setConnectionError(null);
    const toastId = toast.loading('正在连接 AutoCAD...');
    try {
      const resp = await apiClient.post<{ data: AutoCADStatus; message: string }>(
        '/api/autocad/connect',
        { version }
      );
      const status = resp.data.data;
      setAutocadStatus(status);
      setIsConnecting(false);
      setIsConnected(status?.connected ?? false);

      if (status?.connected) {
        toast.success(`AutoCAD 连接成功: ${status.drawing_name ?? ''}`, { id: toastId });
        startPolling();
      } else {
        toast.error('AutoCAD 连接失败，请确保 AutoCAD 已打开图纸', { id: toastId });
      }
    } catch (err: unknown) {
      setIsConnecting(false);
      setConnectionError(err instanceof Error ? err.message : '连接失败');
      toast.error('无法连接 AutoCAD，请检查 AutoCAD 是否正在运行', { id: toastId });
    }
  }, [setAutocadStatus, setIsConnecting, setIsConnected, setConnectionError]);

  /**
   * 断开 AutoCAD 连接
   */
  const disconnect = useCallback(async () => {
    try {
      await apiClient.post('/api/autocad/disconnect');
      stopPolling();
      setAutocadStatus({
        connected: false,
        entity_count: 0,
        last_check: new Date().toISOString(),
      });
      toast('AutoCAD 已断开连接');
    } catch (_) {
      // ignore
    }
  }, [setAutocadStatus]);

  /**
   * 获取 AutoCAD 截图（同时写入 snapshotUrl 和 snapshot 字段）
   */
  const fetchSnapshot = useCallback(async () => {
    if (!autocadStatus.connected) return;

    setLoadingSnapshot(true);
    setSnapshotLoading(true);
    try {
      const resp = await apiClient.get<{ data: { image: string } }>(
        '/api/autocad/snapshot?width=800&height=600'
      );
      const imageData = resp.data.data?.image;
      if (imageData) {
        setSnapshotUrl(imageData);
        setSnapshot(imageData);         // 供 AutoCADPreview 使用
        setSnapshotError(null);
      }
    } catch (_err) {
      const msg = '截图失败';
      setSnapshotError(msg);
    } finally {
      setLoadingSnapshot(false);
      setSnapshotLoading(false);
    }
  }, [autocadStatus.connected, setLoadingSnapshot, setSnapshotLoading, setSnapshotUrl, setSnapshot, setSnapshotError]);

  /** takeSnapshot 是 fetchSnapshot 的别名，供 AutoCADPreview 使用 */
  const takeSnapshot = fetchSnapshot;

  /**
   * 开始状态轮询
   */
  const startPolling = useCallback(() => {
    setPolling(true);
    if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);

    pollingTimerRef.current = setInterval(() => {
      checkStatus();
    }, pollingInterval);
  }, [checkStatus, pollingInterval, setPolling]);

  /**
   * 停止状态轮询
   */
  const stopPolling = useCallback(() => {
    setPolling(false);
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, [setPolling]);

  /**
   * 开始截图轮询
   */
  const startSnapshotPolling = useCallback((intervalSec: number = 5) => {
    if (snapshotTimerRef.current) clearInterval(snapshotTimerRef.current);
    fetchSnapshot(); // 立即获取一次
    snapshotTimerRef.current = setInterval(fetchSnapshot, intervalSec * 1000);
  }, [fetchSnapshot]);

  /**
   * 停止截图轮询
   */
  const stopSnapshotPolling = useCallback(() => {
    if (snapshotTimerRef.current) {
      clearInterval(snapshotTimerRef.current);
      snapshotTimerRef.current = null;
    }
  }, []);

  // 组件挂载时：先查状态，如果未连接则自动尝试连接
  useEffect(() => {
    const autoConnect = async () => {
      const status = await checkStatus();
      if (status && !status.connected) {
        await connect();
      } else if (status?.connected) {
        setIsConnected(true);
      }
    };
    autoConnect();
    return () => {
      stopPolling();
      stopSnapshotPolling();
    };
  }, []);

  // AutoCAD 连接后自动开始轮询
  useEffect(() => {
    if (autocadStatus.connected && !isPolling) {
      startPolling();
    } else if (!autocadStatus.connected && isPolling) {
      stopPolling();
    }
  }, [autocadStatus.connected]);

  return {
    autocadStatus,
    isPolling,
    snapshotUrl,
    snapshotError,
    checkStatus,
    connect,
    disconnect,
    fetchSnapshot,
    takeSnapshot,
    startSnapshotPolling,
    stopSnapshotPolling,
  };
}
