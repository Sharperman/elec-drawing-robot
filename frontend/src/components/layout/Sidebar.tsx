/**
 * Sidebar.tsx
 * 左侧边栏：Logo + 搜索 + 新建会话 + 历史会话（分组+时间+预览）+ 底部导航
 */
import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSessionStore } from '@/stores/sessionStore';
import apiClient from '@/services/apiClient';
import type { Session } from '@/types';
import { useChatStore } from '@/stores/chatStore';
import {
  PlusIcon, ChatBubbleLeftRightIcon, TrashIcon, Cog6ToothIcon,
  ChevronLeftIcon, BookOpenIcon, RectangleGroupIcon,
  MagnifyingGlassIcon, PencilIcon, XMarkIcon,
} from '@heroicons/react/24/outline';
import { ChatBubbleLeftRightIcon as ChatBubbleLeftRightIconSolid } from '@heroicons/react/24/solid';

// ─── 工具函数 ──────────────────────────────────────────────────

/** 生成相对时间字符串 */
function relativeTime(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diff = now - date;
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 7) return `${days}天前`;
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

/** 按时间分组 */
function groupByDate(sessions: Session[]): { label: string; items: Session[] }[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = today - 86400000;
  const weekAgo = today - 7 * 86400000;

  const groups: { label: string; items: Session[] }[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '最近 7 天', items: [] },
    { label: '更早', items: [] },
  ];

  for (const s of sessions) {
    const t = new Date(s.updated_at).getTime();
    if (t >= today) groups[0].items.push(s);
    else if (t >= yesterday) groups[1].items.push(s);
    else if (t >= weekAgo) groups[2].items.push(s);
    else groups[3].items.push(s);
  }

  return groups.filter((g) => g.items.length > 0);
}

// ─── 类型 ──────────────────────────────────────────────────────

interface SidebarProps {
  onCollapse: () => void;
}

// ─── SessionItem ───────────────────────────────────────────────

interface SessionItemProps {
  id: string;
  title: string;
  updatedAt: string;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

const SessionItem: React.FC<SessionItemProps> = ({
  id, title, updatedAt, isActive, onSelect, onDelete, onRename,
}) => {
  const [showActions, setShowActions] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [newTitle, setNewTitle] = useState(title);

  const handleRename = () => {
    if (newTitle.trim() && newTitle !== title) {
      onRename(id, newTitle.trim());
    }
    setRenaming(false);
  };

  return (
    <div
      className={`group relative flex flex-col px-3 py-2 rounded-lg cursor-pointer
                  text-sm transition-all
                  ${isActive
                    ? 'bg-blue-600/15 border border-blue-600/30'
                    : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200 border border-transparent'
                  }`}
      onClick={() => onSelect(id)}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* 标题行 */}
      <div className="flex items-center gap-2 min-w-0">
        {isActive ? (
          <ChatBubbleLeftRightIconSolid className="w-3.5 h-3.5 flex-shrink-0 text-blue-400" />
        ) : (
          <ChatBubbleLeftRightIcon className="w-3.5 h-3.5 flex-shrink-0" />
        )}

        {renaming ? (
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') setRenaming(false); }}
            className="flex-1 bg-gray-700 border border-gray-600 rounded px-1.5 py-0.5 text-xs
                       text-gray-100 outline-none focus:border-blue-500"
            autoFocus
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="flex-1 truncate text-xs leading-snug">{title || '新对话'}</span>
        )}

        {/* 操作按钮 */}
        {showActions && !renaming && (
          <div className="flex items-center gap-0.5 flex-shrink-0">
            <button
              onClick={(e) => { e.stopPropagation(); setRenaming(true); }}
              className="p-1 rounded hover:bg-gray-600 text-gray-500 hover:text-gray-300 transition-colors"
              title="重命名"
            >
              <PencilIcon className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(id); }}
              className="p-1 rounded hover:bg-red-500/20 hover:text-red-400 text-gray-500 transition-colors"
              title="删除"
            >
              <TrashIcon className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* 时间 */}
      <span className="text-[10px] text-gray-600 mt-0.5 ml-5.5">{relativeTime(updatedAt)}</span>
    </div>
  );
};

// ─── NavItem ───────────────────────────────────────────────────

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  desc?: string;
  isActive: boolean;
  onClick: () => void;
}

const NavItem: React.FC<NavItemProps> = ({ icon, label, desc, isActive, onClick }) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all
                ${isActive
                  ? 'bg-blue-600/15 text-blue-300 border-l-2 border-blue-500'
                  : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200 border-l-2 border-transparent'
                }`}
  >
    <span className="w-5 h-5 flex-shrink-0">{icon}</span>
    <div className="flex flex-col items-start min-w-0">
      <span className="text-xs font-medium">{label}</span>
      {desc && <span className="text-[10px] text-gray-600">{desc}</span>}
    </div>
  </button>
);

// ─── 主组件 ────────────────────────────────────────────────────

const Sidebar: React.FC<SidebarProps> = ({ onCollapse }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessions, currentSessionId, setCurrentSession, setSessions, addSession, removeSession, updateSession } =
    useSessionStore();
  const { setMessages } = useChatStore();

  const [searchQuery, setSearchQuery] = useState('');

  // ─── 启动时从后端加载会话列表 ───────────────────────────────
  useEffect(() => {
    let cancelled = false;
    const loadSessions = async () => {
      try {
        const res = await apiClient.get('/api/chat/sessions');
        const apiData = res.data; // ApiResponse
        if (!cancelled && apiData?.code === 0 && apiData.data) {
          setSessions(apiData.data);
        }
      } catch (e) {
        console.warn('[Sidebar] 加载会话列表失败（后端未启动？）', e);
      }
    };
    loadSessions();
    return () => { cancelled = true; };
  }, [setSessions]);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase();
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  const grouped = useMemo(() => groupByDate(filteredSessions), [filteredSessions]);

  const handleNewSession = async () => {
    try {
      const res = await apiClient.post<{ data: Session }>('/api/chat/sessions', { title: '新对话' });
      addSession(res.data.data);
      setCurrentSession(res.data.data.session_id);
    } catch {
      const tempId = `local-${Date.now()}`;
      const tempSession = {
        id: 0, session_id: tempId, title: '新对话', is_active: true,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
        entity_count: 0,
      } as unknown as Session;
      addSession(tempSession);
      setCurrentSession(tempId);
    }
    navigate('/');
  };

  const handleSelectSession = async (id: string) => {
    setCurrentSession(id);
    navigate('/');

    // 从后端加载该会话的消息历史
    try {
      const res = await apiClient.get(`/api/chat/sessions/${encodeURIComponent(id)}/messages`);
      const apiData = res.data; // ApiResponse
      if (apiData?.code === 0 && apiData.data) {
        setMessages(id, apiData.data);
      }
    } catch (e) {
      console.warn('[Sidebar] 加载消息历史失败', e);
    }
  };

  const handleDeleteSession = async (id: string) => {
    // 先调后端删除，再更新本地状态
    try {
      await apiClient.delete(`/api/chat/sessions/${encodeURIComponent(id)}`);
    } catch (e) {
      console.warn('[Sidebar] 后端删除会话失败，仅本地移除', e);
    }
    removeSession(id);
  };

  const handleRenameSession = (id: string, title: string) => {
    updateSession(id, { title });
  };

  const navItems = [
    { icon: <BookOpenIcon className="w-5 h-5" />, label: '绘图规范', desc: 'GB/T 4728', path: '/standards' },
    { icon: <RectangleGroupIcon className="w-5 h-5" />, label: '图元符号库', desc: '20 个符号', path: '/symbols' },
    { icon: <Cog6ToothIcon className="w-5 h-5" />, label: '设置', desc: 'LLM / CAD', path: '/settings' },
  ];

  return (
    <div className="flex flex-col h-full bg-gray-900/80 backdrop-blur-sm select-none">
      {/* Logo 区 */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-800/50 flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600
                          flex items-center justify-center flex-shrink-0
                          shadow-lg shadow-blue-500/20">
            <span className="text-white text-xs font-bold">E</span>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-gray-200 leading-tight">
              电气绘图机器人
            </span>
            <span className="text-[10px] text-gray-600 leading-tight">v1.0.2</span>
          </div>
        </div>
        <button
          onClick={onCollapse}
          className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
          title="折叠侧边栏"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>
      </div>

      {/* 新建对话 */}
      <div className="px-2.5 pt-3 pb-1 flex-shrink-0">
        <button
          onClick={handleNewSession}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg
                     bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400
                     text-white text-sm font-medium transition-all shadow-sm shadow-blue-500/25
                     active:scale-[0.98]"
        >
          <PlusIcon className="w-4 h-4" />
          新建对话
        </button>
      </div>

      {/* 搜索框 */}
      <div className="px-2.5 pt-2 pb-1 flex-shrink-0">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索会话..."
            className="w-full bg-gray-800/60 border border-gray-700/50 rounded-lg pl-8 pr-2
                       py-1.5 text-xs text-gray-300 placeholder-gray-600
                       focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50
                       transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <XMarkIcon className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto px-2.5 py-1 space-y-1 custom-scrollbar">
        {grouped.length === 0 ? (
          <div className="text-center py-8 text-gray-600 text-xs">
            {searchQuery ? '没有匹配的会话' : '暂无历史对话'}
          </div>
        ) : (
          grouped.map((group) => (
            <div key={group.label}>
              <div className="text-[10px] text-gray-600 px-3 py-2 font-medium uppercase tracking-wider">
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.items.map((session) => (
                  <SessionItem
                    key={session.id}
                    id={session.session_id}
                    title={session.title}
                    updatedAt={session.updated_at}
                    isActive={session.session_id === currentSessionId}
                    onSelect={handleSelectSession}
                    onDelete={handleDeleteSession}
                    onRename={handleRenameSession}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 底部导航 */}
      <div className="px-2.5 py-2 border-t border-gray-800/50 space-y-0.5 flex-shrink-0">
        {navItems.map((item) => (
          <NavItem
            key={item.path}
            icon={item.icon}
            label={item.label}
            desc={item.desc}
            isActive={location.pathname === item.path}
            onClick={() => navigate(item.path)}
          />
        ))}
      </div>
    </div>
  );
};

export default Sidebar;
