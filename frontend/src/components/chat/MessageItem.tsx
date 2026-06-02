/**
 * MessageItem.tsx
 * 单条消息渲染：用户气泡 / AI 卡片 / 系统消息 / 工具调用
 * 升级版：毛玻璃 AI 气泡、渐变头像、弹性动画
 */
import React, { useState, useDeferredValue } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { clsx } from 'clsx';
import { User, Bot, Copy, RefreshCw, ThumbsUp, ThumbsDown, Wrench, ChevronDown, ChevronUp } from 'lucide-react';
import type { Message } from '@/types';
import CodeBlock from './CodeBlock';

// ─── 工具调用解析 ──────────────────────────────────────────────

interface ToolCall {
  tool: string;
  input: Record<string, unknown>;
  output?: string;
}

function parseToolCalls(toolCallsStr?: string): ToolCall[] {
  if (!toolCallsStr) return [];
  try {
    const parsed = JSON.parse(toolCallsStr);
    return Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return [];
  }
}

// ─── 消息操作栏 ────────────────────────────────────────────────

const MessageActions: React.FC<{
  onCopy: () => void;
  onRegenerate?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
  copied: boolean;
}> = ({ onCopy, onRegenerate, onFeedback, copied }) => (
  <div className="msg-actions">
    <button onClick={onCopy} title={copied ? '已复制' : '复制'}>
      {copied ? (
        <span className="text-green-400 text-xs">✓</span>
      ) : (
        <Copy className="w-3.5 h-3.5" />
      )}
    </button>
    {onRegenerate && (
      <button onClick={onRegenerate} title="重新生成">
        <RefreshCw className="w-3.5 h-3.5" />
      </button>
    )}
    {onFeedback && (
      <>
        <button onClick={() => onFeedback('positive')} title="有帮助">
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>
        <button onClick={() => onFeedback('negative')} title="无帮助">
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
      </>
    )}
  </div>
);

// ─── 主组件 ────────────────────────────────────────────────────

interface MessageItemProps {
  message: Message;
  isGrouped: boolean;
  isFirstInGroup: boolean;
  onRegenerate?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
}

const MessageItem: React.FC<MessageItemProps> = ({
  message, isGrouped, isFirstInGroup,
  onRegenerate, onFeedback,
}) => {
  const [hovered, setHovered] = useState(false);
  const [copied, setCopied] = useState(false);
  const [toolExpanded, setToolExpanded] = useState(false);

  // 流式渲染时降低更新频率
  const deferredContent = useDeferredValue(message.content);

  const { role, is_streaming, tool_calls } = message;
  const toolCalls = parseToolCalls(tool_calls);
  const hasToolCalls = toolCalls.length > 0;

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 系统消息
  if (role === 'system') {
    return (
      <div className="msg-system">
        <div className="msg-system-badge">
          {deferredContent}
        </div>
      </div>
    );
  }

  const isUser = role === 'user';
  const showAvatar = isFirstInGroup && !isUser;

  return (
    <div
      className={clsx(
        'flex gap-3 px-1',
        isUser ? 'justify-end' : 'justify-start',
        isGrouped ? 'msg-grouped' : 'msg-first',
        !is_streaming && 'msg-animate-in',
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* AI 头像 */}
      {showAvatar && (
        <div className="avatar-ai flex-shrink-0 mt-0.5">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}
      {!showAvatar && !isUser && (
        <div className="w-[34px] flex-shrink-0" />
      )}

      {/* 气泡内容 */}
      <div className={clsx(
        'max-w-[80%] min-w-0',
        isUser ? 'order-1' : 'order-2',
      )}>
        <div className={clsx(
          'px-4 py-2.5',
          isUser ? 'bubble-user' : 'bubble-ai',
          is_streaming && 'streaming-cursor',
        )}>
          {/* Markdown 渲染 */}
          <div className="prose-chat selectable break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeStr = String(children).replace(/\n$/, '');
                  if (match) {
                    return <CodeBlock language={match[1]} code={codeStr} />;
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {deferredContent || (is_streaming ? '' : '...')}
            </ReactMarkdown>
          </div>

          {/* 工具调用 */}
          {hasToolCalls && (
            <div className="mt-2 space-y-1.5">
              {toolCalls.map((tc, idx) => (
                <div key={idx} className="tool-call-card">
                  <div
                    className="tool-call-header"
                    onClick={() => setToolExpanded(!toolExpanded)}
                  >
                    <Wrench className="w-3.5 h-3.5" />
                    <span className="flex-1 font-medium">{tc.tool}</span>
                    {toolExpanded
                      ? <ChevronUp className="w-3.5 h-3.5" />
                      : <ChevronDown className="w-3.5 h-3.5" />
                    }
                  </div>
                  {toolExpanded && (
                    <div className="tool-call-body">
                      {JSON.stringify(tc.input, null, 2)}
                      {tc.output && (
                        <>
                          {'\n\n→ '}{tc.output}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 操作栏 */}
        {hovered && !is_streaming && (
          <div className={clsx(
            'flex mt-1',
            isUser ? 'justify-end' : 'justify-start',
          )}>
            <MessageActions
              onCopy={handleCopy}
              onRegenerate={!isUser ? onRegenerate : undefined}
              onFeedback={!isUser ? onFeedback : undefined}
              copied={copied}
            />
          </div>
        )}
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="avatar-user flex-shrink-0 order-2 mt-0.5">
          <User className="w-4 h-4 text-white" />
        </div>
      )}
    </div>
  );
};

export default React.memo(MessageItem);
