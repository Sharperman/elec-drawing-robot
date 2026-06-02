/**
 * AppShell.tsx
 * 应用主布局：三栏布局（侧边栏 | 对话面板 | 预览面板）
 * 支持响应式折叠、面板宽度拖拽调整、预览默认折叠
 */
import React, { useCallback, useRef, useState } from 'react';
import { PanelRightOpen, PanelRightClose } from 'lucide-react';
import Sidebar from './Sidebar';
import StatusBar from './StatusBar';
import ChatPanel from '@/components/chat/ChatPanel';
import AutoCADPreview from '@/components/preview/AutoCADPreview';
import { useSettingsStore } from '@/stores/settingsStore';

const SIDEBAR_MIN_WIDTH = 180;
const SIDEBAR_MAX_WIDTH = 320;
const PREVIEW_MIN_WIDTH = 260;
const PREVIEW_MAX_WIDTH = 700;

interface AppShellProps {
  mainContent?: React.ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ mainContent }) => {
  const { sidebarCollapsed, previewCollapsed, setSidebarCollapsed, setPreviewCollapsed } =
    useSettingsStore();

  const [sidebarWidth, setSidebarWidth] = useState(220);
  const [previewWidth, setPreviewWidth] = useState(420);

  const dragTarget = useRef<'sidebar' | 'preview' | null>(null);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(0);

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
            setPreviewWidth(
              Math.max(PREVIEW_MIN_WIDTH, Math.min(PREVIEW_MAX_WIDTH, dragStartWidth.current - delta))
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

  return (
    <div className="flex flex-col h-screen w-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── 侧边栏 ── */}
        <div
          className={`hidden md:flex flex-shrink-0 transition-[width] duration-300 ease-in-out overflow-hidden
                      border-r border-gray-800/50`}
          style={{ width: sidebarCollapsed ? 0 : sidebarWidth }}
        >
          {!sidebarCollapsed && (
            <Sidebar onCollapse={() => setSidebarCollapsed(true)} />
          )}
        </div>

        {!sidebarCollapsed && (
          <div
            className="hidden md:block w-1 flex-shrink-0 cursor-col-resize hover:bg-blue-500/40
                       active:bg-blue-500/70 transition-colors group relative"
            onMouseDown={startDrag('sidebar')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20" />
          </div>
        )}

        {/* 侧边栏折叠展开按钮 */}
        {sidebarCollapsed && (
          <button
            onClick={() => setSidebarCollapsed(false)}
            className="hidden md:flex flex-shrink-0 w-7 bg-gray-900 border-r border-gray-800/50
                       hover:bg-gray-800 transition-colors items-center justify-center group"
            title="展开侧边栏"
          >
            <span className="text-gray-500 group-hover:text-gray-300 text-sm">›</span>
          </button>
        )}

        {/* ── 聊天面板 ── */}
        <div className="flex-1 min-w-0 overflow-hidden">
          {mainContent ?? <ChatPanel />}
        </div>

        {/* 预览分割线 */}
        {!previewCollapsed && (
          <div
            className="w-1 flex-shrink-0 cursor-col-resize hover:bg-blue-500/40
                       active:bg-blue-500/70 transition-colors group relative"
            onMouseDown={startDrag('preview')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-blue-500/20" />
          </div>
        )}

        {/* 预览面板折叠把手 */}
        {previewCollapsed && (
          <button
            onClick={() => setPreviewCollapsed(false)}
            className="flex-shrink-0 w-9 bg-gray-900/80 border-l border-gray-800/50
                       hover:bg-gray-800 transition-colors flex flex-col items-center
                       justify-center gap-1.5 group backdrop-blur-sm"
            title="展开图纸预览"
          >
            <PanelRightOpen className="w-4 h-4 text-gray-500 group-hover:text-blue-400 transition-colors" />
            <span className="text-[10px] text-gray-600 group-hover:text-gray-400 transition-colors
                             leading-tight text-center writing-vertical">
              图纸预览
            </span>
          </button>
        )}

        {/* ── AutoCAD 预览面板 ── */}
        <div
          className={`flex-shrink-0 transition-[width] duration-300 ease-in-out overflow-hidden
                      border-l border-gray-800/50`}
          style={{ width: previewCollapsed ? 0 : previewWidth }}
        >
          {!previewCollapsed && (
            <div className="h-full flex flex-col glass-panel">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800/50 flex-shrink-0">
                <span className="text-xs font-medium text-gray-400 tracking-wider uppercase">
                  图纸预览
                </span>
                <button
                  onClick={() => setPreviewCollapsed(true)}
                  className="text-gray-500 hover:text-gray-300 transition-colors"
                  title="折叠预览面板"
                >
                  <PanelRightClose className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 overflow-hidden">
                <AutoCADPreview />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 状态栏 ── */}
      <StatusBar />
    </div>
  );
};

export default AppShell;
