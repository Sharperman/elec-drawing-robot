/**
 * MessageList.tsx
 * 消息列表：空状态分组引导 + 日期分隔 + 回到底部按钮
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ChevronDown, Zap, Search, Lightbulb } from 'lucide-react';
import MessageItem from './MessageItem';
import StreamingSteps from './StreamingSteps';
import type { Message, AgentStep } from '@/types';

// ─── 示例提示词分组 ────────────────────────────────────────────

const EXAMPLE_GROUPS = [
  {
    icon: Zap,
    label: '绘图指令',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    prompts: [
      '在坐标 (100, 200) 插入三相断路器 QF1',
      '绘制 10kV 双母线接线图',
      '添加接地符号并标注 GND1',
    ],
  },
  {
    icon: Search,
    label: '查询分析',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    prompts: [
      '查询当前图纸所有设备清单',
      '分析当前图纸的保护配置',
      '查看所有图层信息',
    ],
  },
  {
    icon: Lightbulb,
    label: '智能建议',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    prompts: [
      '检查短路电流是否合理',
      '验证保护配合是否满足要求',
      '优化当前图纸的布线方案',
    ],
  },
];

// ─── 工具函数 ──────────────────────────────────────────────────

function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const msgDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diff = today.getTime() - msgDate.getTime();

  if (diff === 0) return '今天';
  if (diff === 86400000) return '昨天';
  return date.toLocaleDateString('zh-CN', {
    month: 'long', day: 'numeric', weekday: 'long',
  });
}

function shouldShowDateDivider(prev: Message | null, current: Message): boolean {
  if (!prev) return true;
  const prevDate = new Date(prev.created_at).toDateString();
  const currDate = new Date(current.created_at).toDateString();
  return prevDate !== currDate;
}

// ─── 空状态 ────────────────────────────────────────────────────

const EmptyState: React.FC<{
  onExampleClick: (prompt: string) => void;
}> = ({ onExampleClick }) => (
  <div className="flex flex-col items-center justify-center h-full px-6 py-12 overflow-y-auto">
    {/* 图标 */}
    <div className="empty-state-icon mb-6">
      <Zap className="w-9 h-9 text-white" />
      <div className="empty-state-dot">
        <div className="w-2 h-2 rounded-full bg-white" />
      </div>
    </div>

    <h2 className="text-lg font-semibold text-gray-200 mb-1">电气图纸绘制助手</h2>
    <p className="text-sm text-gray-500 mb-8 text-center max-w-md">
      通过自然语言指令驱动 AutoCAD 自动绘制电气图纸。
      试试下面的示例，或直接输入你的绘图需求。
    </p>

    {/* 分类示例卡片 */}
    <div className="w-full max-w-lg space-y-4">
      {EXAMPLE_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className={`w-6 h-6 rounded-lg ${group.bg} flex items-center justify-center`}>
              <group.icon className={`w-3.5 h-3.5 ${group.color}`} />
            </div>
            <span className="text-xs font-medium text-gray-400">{group.label}</span>
          </div>
          <div className="space-y-1.5">
            {group.prompts.map((prompt, idx) => (
              <button
                key={idx}
                onClick={() => onExampleClick(prompt)}
                className="example-card w-full"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  </div>
);

// ─── 主组件 ────────────────────────────────────────────────────

interface MessageListProps {
  messages: Message[];
  streamingContent?: string;
  isLoading: boolean;
  /** Agent 执行步骤（新协议） */
  agentSteps?: AgentStep[];
  isStreaming?: boolean;
  onExampleClick: (prompt: string) => void;
  onRegenerate: (msg: Message) => void;
  onFeedback: (msgId: number, type: 'positive' | 'negative') => void;
}

const MessageList: React.FC<MessageListProps> = ({
  messages, streamingContent,
  agentSteps = [], isStreaming = false,
  onExampleClick, onRegenerate, onFeedback,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // 判断是否在底部
  const checkAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const threshold = 80;
    setIsAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < threshold);
  }, []);

  // 自动滚底
  useEffect(() => {
    if (isAtBottom && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, streamingContent, isAtBottom]);

  // 监听滚动
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener('scroll', checkAtBottom, { passive: true });
    return () => el.removeEventListener('scroll', checkAtBottom);
  }, [checkAtBottom]);

  // 空状态
  if (messages.length === 0 && !streamingContent) {
    return <EmptyState onExampleClick={onExampleClick} />;
  }

  return (
    <div className="flex-1 relative overflow-hidden">
      {/* 消息列表 */}
      <div
        ref={containerRef}
        className="h-full overflow-y-auto px-4 py-3 custom-scrollbar"
      >
        <div className="max-w-3xl mx-auto space-y-0.5">
          {messages.map((msg, idx) => {
            const prev = idx > 0 ? messages[idx - 1] : null;
            const showDateDivider = shouldShowDateDivider(prev, msg);
            const isFirstInGroup = !prev || prev.role !== msg.role || showDateDivider;
            const isGrouped = !isFirstInGroup;

            return (
              <React.Fragment key={msg.id}>
                {showDateDivider && (
                  <div className="date-divider">
                    <span>{formatDateLabel(msg.created_at)}</span>
                  </div>
                )}
                <MessageItem
                  message={msg}
                  isGrouped={isGrouped}
                  isFirstInGroup={isFirstInGroup}
                  onRegenerate={() => onRegenerate(msg)}
                  onFeedback={(type) => onFeedback(msg.id, type)}
                />
              </React.Fragment>
            );
          })}

          {/* 流式消息 + Agent 步骤 */}
          {(streamingContent !== undefined && streamingContent !== null) || agentSteps.length > 0 ? (
            <div className="flex flex-col gap-1">
              {/* Agent 步骤时间线 */}
              <StreamingSteps
                steps={agentSteps}
                streamingText={streamingContent ?? ''}
                isStreaming={isStreaming}
              />
              {/* 纯文本流式（无步骤时回退到原有渲染） */}
              {agentSteps.length === 0 && streamingContent !== undefined && streamingContent !== null && (
                <MessageItem
                  message={{
                    id: -1,
                    session_id: '',
                    role: 'assistant',
                    content: streamingContent,
                    is_streaming: true,
                    created_at: new Date().toISOString(),
                  }}
                  isGrouped={false}
                  isFirstInGroup={true}
                />
              )}
            </div>
          ) : null}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* 回到底部按钮 */}
      {!isAtBottom && (
        <button
          onClick={() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })}
          className="absolute bottom-4 right-4 z-20 w-10 h-10 rounded-full
                     bg-blue-600/90 hover:bg-blue-500 text-white
                     shadow-lg shadow-blue-500/30 transition-all
                     flex items-center justify-center
                     animate-in fade-in slide-in-from-bottom-2 duration-200"
        >
          <ChevronDown className="w-5 h-5" />
        </button>
      )}
    </div>
  );
};

export default MessageList;
