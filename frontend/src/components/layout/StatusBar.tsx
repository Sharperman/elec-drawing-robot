/**
 * StatusBar.tsx
 * 底部状态栏：AutoCAD 连接状态、连接/断开按钮、版本信息
 */

import React, { useState } from 'react';
import { useConnectionStore } from '@/stores/connectionStore';
import { useAutoCAD } from '@/hooks/useAutoCAD';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import {
  SignalIcon,
  SignalSlashIcon,
  ComputerDesktopIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';

// ─── 子组件：连接状态徽章 ────────────────────────────────────────────────────

interface ConnectionBadgeProps {
  isConnected: boolean;
  isConnecting: boolean;
}

const ConnectionBadge: React.FC<ConnectionBadgeProps> = ({ isConnected, isConnecting }) => {
  if (isConnecting) {
    return (
      <span className="flex items-center gap-1.5 text-yellow-400">
        <LoadingSpinner size="sm" />
        <span>连接中…</span>
      </span>
    );
  }
  if (isConnected) {
    return (
      <span className="flex items-center gap-1.5 text-green-400">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        <SignalIcon className="w-3.5 h-3.5" />
        <span>已连接</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-gray-500">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />
      <SignalSlashIcon className="w-3.5 h-3.5" />
      <span>未连接</span>
    </span>
  );
};

// ─── 主组件 ────────────────────────────────────────────────────────────────────

/**
 * StatusBar — 底部状态栏
 *
 * 左侧：AutoCAD 连接状态 + 文档信息
 * 中间：当前活动 AutoCAD 版本
 * 右侧：连接/断开按钮 + 版本号
 */
const StatusBar: React.FC = () => {
  const { isConnected, isConnecting, autocadVersion, activeDocument, connectionError } =
    useConnectionStore();
  const { connect, disconnect } = useAutoCAD();

  const [showError, setShowError] = useState(false);

  const handleToggleConnection = async () => {
    if (isConnected) {
      await disconnect();
    } else {
      await connect();
    }
  };

  return (
    <div
      className="flex items-center justify-between px-3 py-1 border-t border-gray-800
                 bg-gray-900/90 text-xs text-gray-500 flex-shrink-0 select-none"
    >
      {/* 左侧：AutoCAD 状态 */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <ComputerDesktopIcon className="w-3.5 h-3.5" />
          <span className="font-medium text-gray-400">AutoCAD</span>
          <ConnectionBadge isConnected={isConnected} isConnecting={isConnecting} />
        </div>

        {/* 当前文档名称 */}
        {isConnected && activeDocument && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-gray-400 max-w-[200px] truncate" title={activeDocument}>
              {activeDocument}
            </span>
          </>
        )}

        {/* 版本信息 */}
        {isConnected && autocadVersion && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500">{autocadVersion}</span>
          </>
        )}

        {/* 错误提示 */}
        {connectionError && !isConnected && (
          <>
            <span className="text-gray-700">|</span>
            <button
              onMouseEnter={() => setShowError(true)}
              onMouseLeave={() => setShowError(false)}
              className="flex items-center gap-1 text-red-400/80 hover:text-red-400 transition-colors
                         relative"
            >
              <InformationCircleIcon className="w-3.5 h-3.5" />
              <span>连接失败</span>

              {/* Tooltip */}
              {showError && (
                <div
                  className="absolute bottom-5 left-0 bg-gray-800 border border-gray-700
                             rounded px-2 py-1 text-xs text-red-300 whitespace-nowrap shadow-lg z-50"
                >
                  {connectionError}
                </div>
              )}
            </button>
          </>
        )}
      </div>

      {/* 右侧：操作按钮 */}
      <div className="flex items-center gap-3">
        {/* 版本号 */}
        <span className="text-gray-700">v1.0.0</span>

        {/* 连接/断开按钮 */}
        <button
          onClick={handleToggleConnection}
          disabled={isConnecting}
          className={`px-2.5 py-0.5 rounded text-xs font-medium transition-colors
                      disabled:opacity-50 disabled:cursor-not-allowed
                      ${isConnected
                        ? 'bg-red-900/40 hover:bg-red-900/60 text-red-400 border border-red-800/50'
                        : 'bg-blue-900/40 hover:bg-blue-900/60 text-blue-400 border border-blue-800/50'
                      }`}
        >
          {isConnecting ? '连接中…' : isConnected ? '断开连接' : '连接 AutoCAD'}
        </button>
      </div>
    </div>
  );
};

export default StatusBar;
