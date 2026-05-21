/**
 * AppShell.tsx
 * 应用主布局外壳：三栏布局（侧边栏 | 对话面板 | 预览面板）
 * 支持响应式折叠、面板宽度拖拽调整
 */

import React, { useCallback, useRef, useState } from 'react';
import Sidebar from './Sidebar';
import StatusBar from './StatusBar';
import ChatPanel from '@/components/chat/ChatPanel';
import AutoCADPreview from '@/components/preview/AutoCADPreview';
import { useSettingsStore } from '@/stores/settingsStore';

// ─── 常量 ────────────────────────────────────────────────────────────────────

const SIDEBAR_MIN_WIDTH = 180;
const SIDEBAR_MAX_WIDTH = 320;
const PREVIEW_MIN_WIDTH = 240;
const PREVIEW_MAX_WIDTH = 800;

// ─── 类型 ────────────────────────────────────────────────────────────────────

interface AppShellProps {
  /**
   * 替换中央聊天面板的内容（用于配置页）。
   * 若不传，默认渲染 ChatPanel。
   */
  mainContent?: React.ReactNode;
}

// ─── 组件实现 ────────────────────────────────────────────────────────────────

/**
 * AppShell — 应用顶层布局容器
 *
 * 布局结构：
 * ┌─────────────┬──────────────────────┬───────────────────┐
 * │   Sidebar   │  ChatPanel / 配置页  │  AutoCADPreview   │
 * │  (可折叠)   │   (自适应占满)       │    (可折叠)       │
 * ├─────────────┴──────────────────────┴───────────────────┤
 * │                     StatusBar                           │
 * └─────────────────────────────────────────────────────────┘
 */
const AppShell: React.FC<AppShellProps> = ({ mainContent }) => {
  const { sidebarCollapsed, previewCollapsed, setSidebarCollapsed, setPreviewCollapsed } =
    useSettingsStore();

  const [sidebarWidth, setSidebarWidth] = useState(220);
  const [previewWidth, setPreviewWidth] = useState(420);

  // 拖拽状态 ref（不触发重渲染）
  const dragTarget = useRef<'sidebar' | 'preview' | null>(null);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

  // ── 拖拽分割线逻辑 ─────────────────────────────────────────────────────────

  const startDrag = useCallback(
    (target: 'sidebar' | 'preview') =>
      (e: React.MouseEvent) => {
        e.preventDefault();
        dragTarget.current = target;
        dragStartX.current = e.clientX;
        dragStartWidth.current = target === 'sidebar' ? sidebarWidth : previewWidth;

        const onMouseMove = (ev: MouseEvent) => {
          const delta = ev.clientX - dragStartX.current;
          if (dragTarget.current === 'sidebar') {
            setSidebarWidth(
              Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, dragStartWidth.current + delta))
            );
          } else {
            // 预览面板向右拖拽 → 宽度减小（分割线在预览左侧）
            setPreviewWidth(
              Math.max(
                PREVIEW_MIN_WIDTH,
                Math.min(PREVIEW_MAX_WIDTH, dragStartWidth.current - delta)
              )
            );
          }
        };

        const onMouseUp = () => {
          dragTarget.current = null;
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      },
    [sidebarWidth, previewWidth]
  );

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-screen w-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* 主内容区（三栏） */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── 侧边栏 ─────────────────────────────────────────────────── */}
        <div
          className={`flex-shrink-0 transition-[width] duration-200 ease-in-out overflow-hidden
                      border-r border-gray-800`}
          style={{ width: sidebarCollapsed ? 0 : sidebarWidth }}
        >
          {!sidebarCollapsed && (
            <Sidebar onCollapse={() => setSidebarCollapsed(true)} />
          )}
        </div>

        {/* 侧边栏分割线（可拖拽） */}
        {!sidebarCollapsed && (
          <div
            className="w-1 flex-shrink-0 cursor-col-resize hover:bg-blue-500/40 active:bg-blue-500/70
                       transition-colors group relative"
            onMouseDown={startDrag('sidebar')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20" />
          </div>
        )}

        {/* 侧边栏折叠时的展开按钮 */}
        {sidebarCollapsed && (
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="flex-shrink-0 w-6 bg-gray-900 border-r border-gray-800 hover:bg-gray-800
                       transition-colors flex items-center justify-center group"
            title="展开侧边栏"
          >
            <span className="text-gray-600 group-hover:text-gray-300 text-xs">›</span>
          </button>
        )}

        {/* ── 聊天面板（弹性填充） ────────────────────────────────────── */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {mainContent ?? <ChatPanel />}
        </div>

        {/* 预览分割线（可拖拽） */}
        {!previewCollapsed && (
          <div
            className="w-1 flex-shrink-0 cursor-col-resize hover:bg-blue-500/40 active:bg-blue-500/70
                       transition-colors group relative"
            onMouseDown={startDrag('preview')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20" />
          </div>
        )}

        {/* 预览面板折叠时的展开按钮 */}
        {previewCollapsed && (
          <button
            onClick={() => setPreviewCollapsed(false)}
            className="flex-shrink-0 w-6 bg-gray-900 border-l border-gray-800 hover:bg-gray-800
                       transition-colors flex items-center justify-center group"
            title="展开 AutoCAD 预览"
          >
            <span className="text-gray-600 group-hover:text-gray-300 text-xs">‹</span>
          </button>
        )}

        {/* ── AutoCAD 预览面板 ─────────────────────────────────────────── */}
        <div
          className={`flex-shrink-0 transition-[width] duration-200 ease-in-out overflow-hidden
                      border-l border-gray-800`}
          style={{ width: previewCollapsed ? 0 : previewWidth }}
        >
          {!previewCollapsed && (
            <div className="h-full flex flex-col">
              {/* 预览面板标题栏 */}
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800
                              bg-gray-900 flex-shrink-0">
                <span className="text-xs font-medium text-gray-400 tracking-wider uppercase">
                  图纸预览
                </span>
                <button
                  onClick={() => setPreviewCollapsed(true)}
                  className="text-gray-600 hover:text-gray-300 transition-colors text-lg leading-none"
                  title="折叠预览面板"
                >
                  ×
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <AutoCADPreview />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 底部状态栏 ───────────────────────────────────────────────── */}
      <StatusBar />
    </div>
  );
};

export default AppShell;
