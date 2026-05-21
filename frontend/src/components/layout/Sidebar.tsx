/**
 * Sidebar.tsx
 * 左侧边栏：会话列表、新建会话、设置入口
 */

import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSessionStore } from '@/stores/sessionStore';
import apiClient from '@/services/apiClient';
import type { Session } from '@/types';
import {
  PlusIcon,
  ChatBubbleLeftRightIcon,
  TrashIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  BookOpenIcon,
  RectangleGroupIcon,
} from '@heroicons/react/24/outline';
import { ChatBubbleLeftRightIcon as ChatBubbleLeftRightIconSolid } from '@heroicons/react/24/solid';

// ─── 类型 ─────────────────────────────────────────────────────────────────────

interface SidebarProps {
  /** 点击折叠按钮的回调 */
  onCollapse: () => void;
}

// ─── 子组件：会话列表项 ────────────────────────────────────────────────────────

interface SessionItemProps {
  id: string;
  title: string;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const SessionItem: React.FC<SessionItemProps> = ({
  id,
  title,
  isActive,
  onSelect,
  onDelete,
}) => {
  const [showDelete, setShowDelete] = useState(false);

  return (
    <div
      className={`group relative flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer
                  text-sm transition-colors
                  ${isActive
                    ? 'bg-blue-600/20 text-blue-300 border border-blue-600/30'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200 border border-transparent'
                  }`}
      onClick={() => onSelect(id)}
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
    >
      {isActive ? (
        <ChatBubbleLeftRightIconSolid className="w-4 h-4 flex-shrink-0 text-blue-400" />
      ) : (
        <ChatBubbleLeftRightIcon className="w-4 h-4 flex-shrink-0" />
      )}

      <span className="flex-1 truncate leading-snug">{title || '新对话'}</span>

      {/* 删除按钮 */}
      {showDelete && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete(id);
          }}
          className="flex-shrink-0 p-0.5 rounded hover:bg-red-500/20 hover:text-red-400
                     text-gray-600 transition-colors"
          title="删除会话"
        >
          <TrashIcon className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};

// ─── 导航菜单项 ───────────────────────────────────────────────────────────────

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  path: string;
  isActive: boolean;
  onClick: () => void;
}

const NavItem: React.FC<NavItemProps> = ({ icon, label, isActive, onClick }) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors
                ${isActive
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
  >
    <span className="w-4 h-4 flex-shrink-0">{icon}</span>
    <span>{label}</span>
  </button>
);

// ─── 主组件 ────────────────────────────────────────────────────────────────────

/**
 * Sidebar — 左侧导航面板
 *
 * 包含：
 * - Logo + 折叠按钮
 * - 新建对话按钮
 * - 历史会话列表（可删除）
 * - 底部导航（规范配置 / 图元库 / 设置）
 */
const Sidebar: React.FC<SidebarProps> = ({ onCollapse }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const {
    sessions,
    currentSessionId,
    setCurrentSession,
    addSession,
    removeSession,
  } = useSessionStore();

  /** 通过 API 创建新会话，成功后添加到 store */
  const handleNewSession = async () => {
    try {
      const res = await apiClient.post<{ data: Session }>('/api/chat/sessions', { title: '新对话' });
      const newSession = res.data.data;
      addSession(newSession);
      setCurrentSession(newSession.session_id);
    } catch (_) {
      // 离线时降级：生成本地临时 session
      const tempId = `local-${Date.now()}`;
      const tempSession: Session = {
        id: 0,
        session_id: tempId,
        title: '新对话',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        entity_count: 0,
      } as unknown as Session;
      addSession(tempSession);
      setCurrentSession(tempId);
    }
    navigate('/');
  };

  const handleSelectSession = (id: string) => {
    setCurrentSession(id);
    navigate('/');
  };

  const handleDeleteSession = (id: string) => {
    removeSession(id);
  };

  const navItems = [
    {
      icon: <BookOpenIcon className="w-4 h-4" />,
      label: '绘图规范',
      path: '/standards',
    },
    {
      icon: <RectangleGroupIcon className="w-4 h-4" />,
      label: '图元符号库',
      path: '/symbols',
    },
    {
      icon: <Cog6ToothIcon className="w-4 h-4" />,
      label: '设置',
      path: '/settings',
    },
  ];

  return (
    <div className="flex flex-col h-full bg-gray-900 select-none">
      {/* Logo + 折叠 */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-800 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xs font-bold">E</span>
          </div>
          <span className="text-sm font-semibold text-gray-200 leading-tight">
            电气绘图机器人
          </span>
        </div>
        <button
          onClick={onCollapse}
          className="p-1 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-colors"
          title="折叠侧边栏"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>
      </div>

      {/* 新建对话 */}
      <div className="px-2 pt-3 pb-2 flex-shrink-0">
        <button
          onClick={handleNewSession}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-md
                     bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium
                     transition-colors shadow-sm"
        >
          <PlusIcon className="w-4 h-4" />
          新建对话
        </button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5 custom-scrollbar">
        {sessions.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">
            暂无历史对话
          </div>
        ) : (
          sessions.map((session) => (
            <SessionItem
              key={session.id}
              id={session.session_id}
              title={session.title}
              isActive={session.session_id === currentSessionId}
              onSelect={handleSelectSession}
              onDelete={handleDeleteSession}
            />
          ))
        )}
      </div>

      {/* 底部导航 */}
      <div className="px-2 py-2 border-t border-gray-800 space-y-0.5 flex-shrink-0">
        {navItems.map((item) => (
          <NavItem
            key={item.path}
            icon={item.icon}
            label={item.label}
            path={item.path}
            isActive={location.pathname === item.path}
            onClick={() => navigate(item.path)}
          />
        ))}
      </div>
    </div>
  );
};

export default Sidebar;
