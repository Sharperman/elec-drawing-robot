/**
 * AutoCADPreview.tsx
 * AutoCAD 实时截图预览组件
 * 轮询后端截图 API，展示图纸实时状态
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useConnectionStore } from '@/stores/connectionStore';
import { useAutoCAD } from '@/hooks/useAutoCAD';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import {
  ArrowPathIcon,
  PhotoIcon,
  ExclamationTriangleIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  MagnifyingGlassMinusIcon,
  MagnifyingGlassPlusIcon,
} from '@heroicons/react/24/outline';

// ─── 类型定义 ───────────────────────────────────────────────────────────────

interface TransformState {
  scale: number;
  translateX: number;
  translateY: number;
}

// ─── 组件实现 ───────────────────────────────────────────────────────────────

/**
 * AutoCAD 实时预览面板
 * 功能：
 * - 每 3 秒自动轮询截图
 * - 支持手动刷新
 * - 支持缩放/平移（鼠标滚轮 + 拖拽）
 * - 全屏模式
 * - 未连接/加载中/错误的空状态处理
 */
const AutoCADPreview: React.FC = () => {
  const { isConnected, snapshot, isSnapshotLoading, snapshotError } = useConnectionStore();
  const { takeSnapshot } = useAutoCAD();

  // 变换状态（缩放+平移）
  const [transform, setTransform] = useState<TransformState>({
    scale: 1,
    translateX: 0,
    translateY: 0,
  });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── 轮询逻辑 ──────────────────────────────────────────────────────────────

  const startPolling = useCallback(() => {
    if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);
    pollingTimerRef.current = setInterval(() => {
      if (isConnected && autoRefresh) {
        takeSnapshot();
      }
    }, 3000);
  }, [isConnected, autoRefresh, takeSnapshot]);

  useEffect(() => {
    if (isConnected && autoRefresh) {
      // 立即取一次截图
      takeSnapshot();
      startPolling();
    }
    return () => {
      if (pollingTimerRef.current) clearInterval(pollingTimerRef.current);
    };
  }, [isConnected, autoRefresh]); // eslint-disable-line react-hooks/exhaustive-deps

  // 自动刷新开关变化时重启轮询
  useEffect(() => {
    if (!autoRefresh && pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
    } else if (autoRefresh && isConnected) {
      startPolling();
    }
  }, [autoRefresh, isConnected, startPolling]);

  // ── 鼠标滚轮缩放 ─────────────────────────────────────────────────────────

  const handleWheel = useCallback((e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform((prev) => ({
      ...prev,
      scale: Math.max(0.2, Math.min(5, prev.scale * delta)),
    }));
  }, []);

  // ── 拖拽平移 ──────────────────────────────────────────────────────────────

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.button !== 0) return;
      setIsDragging(true);
      setDragStart({ x: e.clientX - transform.translateX, y: e.clientY - transform.translateY });
    },
    [transform.translateX, transform.translateY]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!isDragging) return;
      setTransform((prev) => ({
        ...prev,
        translateX: e.clientX - dragStart.x,
        translateY: e.clientY - dragStart.y,
      }));
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = useCallback(() => setIsDragging(false), []);
  const handleMouseLeave = useCallback(() => setIsDragging(false), []);

  // ── 缩放按钮 ──────────────────────────────────────────────────────────────

  const zoomIn = () =>
    setTransform((prev) => ({ ...prev, scale: Math.min(5, prev.scale * 1.25) }));

  const zoomOut = () =>
    setTransform((prev) => ({ ...prev, scale: Math.max(0.2, prev.scale * 0.8) }));

  const resetTransform = () =>
    setTransform({ scale: 1, translateX: 0, translateY: 0 });

  // ── 全屏 ──────────────────────────────────────────────────────────────────

  const toggleFullscreen = useCallback(async () => {
    if (!isFullscreen) {
      await containerRef.current?.requestFullscreen?.();
      setIsFullscreen(true);
    } else {
      await document.exitFullscreen?.();
      setIsFullscreen(false);
    }
  }, [isFullscreen]);

  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, []);

  // ── 渲染：未连接空状态 ────────────────────────────────────────────────────

  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-950 text-gray-500 select-none">
        <PhotoIcon className="w-16 h-16 mb-4 opacity-30" />
        <p className="text-sm font-medium">未连接 AutoCAD</p>
        <p className="text-xs mt-1 opacity-60">请在状态栏中连接 AutoCAD 以查看图纸预览</p>
      </div>
    );
  }

  // ── 渲染：首次加载中 ──────────────────────────────────────────────────────

  if (isSnapshotLoading && !snapshot) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-950">
        <LoadingSpinner size="lg" />
        <p className="mt-3 text-sm text-gray-400">正在获取图纸截图…</p>
      </div>
    );
  }

  // ── 渲染：错误状态 ────────────────────────────────────────────────────────

  if (snapshotError && !snapshot) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gray-950 text-gray-500">
        <ExclamationTriangleIcon className="w-12 h-12 mb-3 text-yellow-500/60" />
        <p className="text-sm font-medium text-yellow-400">截图获取失败</p>
        <p className="text-xs mt-1 opacity-70 max-w-xs text-center">{snapshotError}</p>
        <button
          onClick={() => takeSnapshot()}
          className="mt-4 flex items-center gap-2 px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500
                     text-white text-sm transition-colors"
        >
          <ArrowPathIcon className="w-4 h-4" />
          重试
        </button>
      </div>
    );
  }

  // ── 渲染：预览主体 ────────────────────────────────────────────────────────

  return (
    <div
      ref={containerRef}
      className="relative flex flex-col h-full bg-gray-950 overflow-hidden"
    >
      {/* 工具栏 */}
      <div className="absolute top-2 right-2 z-20 flex items-center gap-1 bg-gray-900/80 backdrop-blur-sm
                      border border-gray-700/50 rounded-lg px-2 py-1 shadow-lg">
        {/* 自动刷新开关 */}
        <button
          onClick={() => setAutoRefresh((v) => !v)}
          title={autoRefresh ? '关闭自动刷新' : '开启自动刷新（3s）'}
          className={`p-1 rounded transition-colors ${
            autoRefresh ? 'text-green-400 hover:text-green-300' : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          <span className="text-xs font-mono">{autoRefresh ? 'AUTO' : 'MNL'}</span>
        </button>

        <div className="w-px h-4 bg-gray-700" />

        {/* 手动刷新 */}
        <button
          onClick={() => takeSnapshot()}
          disabled={isSnapshotLoading}
          title="立即刷新截图"
          className="p-1 rounded text-gray-400 hover:text-white transition-colors disabled:opacity-40"
        >
          <ArrowPathIcon className={`w-4 h-4 ${isSnapshotLoading ? 'animate-spin' : ''}`} />
        </button>

        <div className="w-px h-4 bg-gray-700" />

        {/* 缩小 */}
        <button
          onClick={zoomOut}
          title="缩小"
          className="p-1 rounded text-gray-400 hover:text-white transition-colors"
        >
          <MagnifyingGlassMinusIcon className="w-4 h-4" />
        </button>

        {/* 缩放比例 */}
        <button
          onClick={resetTransform}
          title="重置缩放"
          className="px-1 py-0.5 rounded text-xs font-mono text-gray-300 hover:text-white
                     hover:bg-gray-700 transition-colors min-w-[3rem] text-center"
        >
          {Math.round(transform.scale * 100)}%
        </button>

        {/* 放大 */}
        <button
          onClick={zoomIn}
          title="放大"
          className="p-1 rounded text-gray-400 hover:text-white transition-colors"
        >
          <MagnifyingGlassPlusIcon className="w-4 h-4" />
        </button>

        <div className="w-px h-4 bg-gray-700" />

        {/* 全屏 */}
        <button
          onClick={toggleFullscreen}
          title={isFullscreen ? '退出全屏' : '全屏预览'}
          className="p-1 rounded text-gray-400 hover:text-white transition-colors"
        >
          {isFullscreen ? (
            <ArrowsPointingInIcon className="w-4 h-4" />
          ) : (
            <ArrowsPointingOutIcon className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* 刷新指示器（截图中覆盖闪烁边框） */}
      {isSnapshotLoading && snapshot && (
        <div className="absolute inset-0 z-10 pointer-events-none border-2 border-blue-500/40
                        animate-pulse rounded" />
      )}

      {/* 图纸画布区域 */}
      <div
        className={`flex-1 overflow-hidden ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      >
        {snapshot ? (
          <div
            className="w-full h-full flex items-center justify-center"
            style={{ userSelect: 'none' }}
          >
            <img
              ref={imgRef}
              src={`data:image/png;base64,${snapshot}`}
              alt="AutoCAD 图纸预览"
              draggable={false}
              style={{
                transform: `translate(${transform.translateX}px, ${transform.translateY}px) scale(${transform.scale})`,
                transformOrigin: 'center center',
                transition: isDragging ? 'none' : 'transform 0.1s ease',
                maxWidth: 'none',
                imageRendering: transform.scale > 2 ? 'pixelated' : 'auto',
              }}
              className="shadow-2xl"
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <PhotoIcon className="w-12 h-12 mb-2 opacity-30" />
            <p className="text-sm">暂无图纸截图</p>
          </div>
        )}
      </div>

      {/* 底部信息栏 */}
      <div className="absolute bottom-2 left-2 z-20 flex items-center gap-3 text-xs text-gray-500
                      bg-gray-900/70 backdrop-blur-sm px-2 py-1 rounded">
        <span
          className={`w-1.5 h-1.5 rounded-full ${autoRefresh ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`}
        />
        <span>{autoRefresh ? '自动刷新（3s）' : '手动刷新'}</span>
        {snapshotError && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-yellow-500/80 truncate max-w-[200px]" title={snapshotError}>
              {snapshotError}
            </span>
          </>
        )}
      </div>
    </div>
  );
};

export default AutoCADPreview;
