/**
 * StatusBar.tsx
 * 底部状态栏：后端心跳 + AutoCAD 状态 + 文档信息 + 操作按钮
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useConnectionStore } from '@/stores/connectionStore';
import { useAutoCAD } from '@/hooks/useAutoCAD';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import apiClient from '@/services/apiClient';
import {
  SignalIcon, SignalSlashIcon, ComputerDesktopIcon,
  InformationCircleIcon, ServerIcon,
} from '@heroicons/react/24/outline';

// ─── 连接状态徽章 ──────────────────────────────────────────────

interface BadgeProps {
  isConnected: boolean;
  isConnecting: boolean;
  error?: string | null;
}

const CadBadge: React.FC<BadgeProps> = ({ isConnected, isConnecting, error }) => {
  if (isConnecting) {
    return (
      <span className="flex items-center gap-1.5 text-yellow-400 text-xs">
        <LoadingSpinner size="sm" />
        <span>连接中...</span>
      </span>
    );
  }
  if (isConnected) {
    return (
      <span className="flex items-center gap-1.5 text-green-400 text-xs">
        <span className="w-2 h-2 rounded-full bg-green-400 glow-green" />
        <SignalIcon className="w-3 h-3" />
        <span>CAD 在线</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-gray-500 text-xs" title={error || undefined}>
      <span className="w-2 h-2 rounded-full bg-gray-600" />
      <SignalSlashIcon className="w-3 h-3" />
      <span>CAD 离线</span>
    </span>
  );
};

const BackendBadge: React.FC<{ online: boolean }> = ({ online }) => (
  <span className="flex items-center gap-1.5 text-xs">
    <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-400 glow-green' : 'bg-red-400 animate-pulse'}`} />
    <span className={online ? 'text-green-400' : 'text-red-400'}>
      {online ? '后端在线' : '后端离线'}
    </span>
  </span>
);

// ─── 主组件 ────────────────────────────────────────────────────

const StatusBar: React.FC = () => {
  const {
    isConnected, isConnecting, autocadVersion, activeDocument, connectionError, backendOnline,
  } = useConnectionStore();
  const { connect, disconnect } = useAutoCAD();

  const [showError, setShowError] = useState(false);

  // ── 后端心跳 ──
  const checkBackend = useCallback(async () => {
    try {
      await apiClient.get('/health');
      useConnectionStore.getState().setBackendOnline(true);
    } catch {
      useConnectionStore.getState().setBackendOnline(false);
    }
  }, []);

  useEffect(() => {
    checkBackend();
    const timer = setInterval(checkBackend, 15000);
    return () => clearInterval(timer);
  }, [checkBackend]);

  const handleToggleConnection = async () => {
    if (isConnected) {
      await disconnect();
    } else {
      await connect();
    }
  };

  return (
    <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-800/50
                    glass-panel text-xs flex-shrink-0 select-none">
      {/* 左侧 */}
      <div className="flex items-center gap-4">
        {/* 后端状态 */}
        <div className="flex items-center gap-1.5">
          <ServerIcon className="w-3 h-3 text-gray-500" />
          <BackendBadge online={backendOnline} />
        </div>

        <span className="text-gray-700">|</span>

        {/* CAD 状态 */}
        <div className="flex items-center gap-2">
          <ComputerDesktopIcon className="w-3 h-3 text-gray-500" />
          <span className="font-medium text-gray-400 text-xs">AutoCAD</span>
          <CadBadge isConnected={isConnected} isConnecting={isConnecting} error={connectionError} />
        </div>

        {isConnected && activeDocument && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-gray-400 max-w-[180px] truncate text-xs" title={activeDocument}>
              {activeDocument}
            </span>
          </>
        )}

        {isConnected && autocadVersion && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500 text-xs">{autocadVersion}</span>
          </>
        )}

        {connectionError && !isConnected && (
          <>
            <span className="text-gray-700">|</span>
            <button
              onMouseEnter={() => setShowError(true)}
              onMouseLeave={() => setShowError(false)}
              className="flex items-center gap-1 text-red-400/80 hover:text-red-400 transition-colors relative"
            >
              <InformationCircleIcon className="w-3 h-3" />
              <span className="text-xs">连接失败</span>
              {showError && (
                <div className="absolute bottom-5 left-0 bg-gray-800 border border-gray-700
                                rounded-lg px-2.5 py-1.5 text-xs text-red-300 whitespace-nowrap
                                shadow-xl z-50">
                  {connectionError}
                </div>
              )}
            </button>
          </>
        )}
      </div>

      {/* 右侧 */}
      <div className="flex items-center gap-3">
        <span className="text-gray-600 text-xs">
          ⌘
          K 快捷指令
        </span>

        <span className="text-gray-700">|</span>

        <span className="text-gray-600 text-xs">v1.0.2</span>

        <button
          onClick={handleToggleConnection}
          disabled={isConnecting}
          className={`px-2.5 py-0.5 rounded-md text-xs font-medium transition-all
                      disabled:opacity-50 disabled:cursor-not-allowed active:scale-95
                      ${isConnected
                        ? 'bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-800/30'
                        : 'bg-blue-900/30 hover:bg-blue-900/50 text-blue-400 border border-blue-800/30'
                      }`}
        >
          {isConnecting ? '连接中...' : isConnected ? '断开 CAD' : '连接 CAD'}
        </button>
      </div>
    </div>
  );
};

export default StatusBar;
