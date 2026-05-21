/**
 * 单条消息组件
 * 支持 Markdown 渲染 + 流式文字光标
 */
import React from 'react';
import ReactMarkdown from 'react-markdown';
import { clsx } from 'clsx';
import { User, Bot } from 'lucide-react';
import type { Message } from '@/types';

interface MessageItemProps {
  message: Message;
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isStreaming = message.is_streaming;

  return (
    <div
      className={clsx(
        'flex items-start gap-2.5 py-1.5 animate-fade-in',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* 头像 */}
      <div
        className={clsx(
          'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
          isUser
            ? 'bg-blue-600/30 border border-blue-500/40'
            : 'bg-purple-600/20 border border-purple-500/30'
        )}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-blue-400" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-purple-400" />
        )}
      </div>

      {/* 消息气泡 */}
      <div
        className={clsx(
          'max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm',
          isUser
            ? 'bg-blue-600 text-white rounded-tr-sm'
            : 'bg-gray-800 border border-gray-700 text-gray-100 rounded-tl-sm'
        )}
      >
        {/* 图片预览 */}
        {message.image_data && (
          <div className="mb-2">
            <img
              src={message.image_data}
              alt="上传的图片"
              className="max-w-full max-h-48 rounded-lg object-contain"
            />
          </div>
        )}

        {/* 文字内容 */}
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <div className={clsx('prose-chat', { 'streaming-cursor': isStreaming })}>
            <ReactMarkdown
              components={{
                // 代码块处理
                code({ className, children, ...props }) {
                  const isInline = !className;
                  return isInline ? (
                    <code className="px-1 py-0.5 rounded bg-gray-700 text-blue-300 font-mono text-xs" {...props}>
                      {children}
                    </code>
                  ) : (
                    <pre className="p-3 rounded-md bg-gray-900 overflow-x-auto mb-2">
                      <code className="text-gray-300 font-mono text-xs">{children}</code>
                    </pre>
                  );
                },
                // 段落处理
                p({ children }) {
                  return <p className="mb-1.5 last:mb-0 leading-relaxed">{children}</p>;
                },
                // 列表处理
                ul({ children }) {
                  return <ul className="pl-4 mb-2 space-y-0.5 list-disc">{children}</ul>;
                },
                ol({ children }) {
                  return <ol className="pl-4 mb-2 space-y-0.5 list-decimal">{children}</ol>;
                },
                // 强调
                strong({ children }) {
                  return <strong className="font-semibold text-gray-50">{children}</strong>;
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* 工具调用展示 */}
        {message.tool_calls && !isUser && (
          <ToolCallsPreview toolCallsJson={message.tool_calls} />
        )}

        {/* 时间戳 */}
        <div
          className={clsx(
            'mt-1 text-xs opacity-50',
            isUser ? 'text-right' : 'text-left'
          )}
        >
          {formatTime(message.created_at)}
        </div>
      </div>
    </div>
  );
};

// 工具调用预览
const ToolCallsPreview: React.FC<{ toolCallsJson: string }> = ({ toolCallsJson }) => {
  let calls: Array<{ tool: string; result?: string }> = [];
  try {
    calls = JSON.parse(toolCallsJson);
  } catch (_) {
    return null;
  }

  return (
    <div className="mt-2 border-t border-gray-700/50 pt-2 space-y-1">
      {calls.map((call, i) => (
        <div key={i} className="text-xs text-gray-500 flex items-center gap-1">
          <span className="text-blue-400">🔧</span>
          <span className="font-mono">{call.tool}</span>
          {call.result && (
            <span className="text-green-400 truncate">→ {call.result.slice(0, 50)}</span>
          )}
        </div>
      ))}
    </div>
  );
};

function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (_) {
    return '';
  }
}

export default MessageItem;
