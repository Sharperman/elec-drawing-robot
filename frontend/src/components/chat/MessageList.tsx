/**
 * 消息列表 - 自动滚底
 */
import React, { useEffect, useRef } from 'react';

import MessageItem from './MessageItem';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import type { Message } from '@/types';

interface MessageListProps {
  messages: Message[];
  streamingContent?: string;
  isLoading: boolean;
}

const MessageList: React.FC<MessageListProps> = ({
  messages,
  streamingContent,
  isLoading,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 消息更新时自动滚底
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-8">
        <div className="w-16 h-16 rounded-full bg-blue-900/30 flex items-center justify-center mb-4">
          <span className="text-3xl">⚡</span>
        </div>
        <h3 className="text-gray-300 font-medium mb-2">开始绘制电气图纸</h3>
        <p className="text-gray-500 text-sm max-w-xs leading-relaxed">
          输入自然语言指令，如「在 (100,200) 处插入一个 10kV/0.4kV 变压器 T1」，
          系统将自动在 AutoCAD 中绘制。
        </p>
        <div className="mt-6 grid grid-cols-1 gap-2 w-full max-w-xs">
          {EXAMPLE_PROMPTS.map((prompt, i) => (
            <div
              key={i}
              className="text-xs text-gray-500 border border-gray-700 rounded-lg px-3 py-2 
                         hover:border-gray-500 hover:text-gray-400 cursor-default transition-colors"
            >
              {prompt}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1 selectable">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}

      {/* 流式输出中的消息 */}
      {streamingContent !== undefined && (
        <MessageItem
          message={{
            id: -1,
            session_id: '',
            role: 'assistant',
            content: streamingContent,
            is_streaming: true,
            created_at: new Date().toISOString(),
          }}
        />
      )}

      {/* 等待响应 loading */}
      {isLoading && !streamingContent && (
        <div className="flex items-start gap-3 py-2">
          <div className="w-7 h-7 rounded-full bg-blue-600/20 border border-blue-500/30 
                          flex items-center justify-center flex-shrink-0">
            <span className="text-xs">AI</span>
          </div>
          <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-3">
            <LoadingSpinner size="sm" text="思考中..." />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

const EXAMPLE_PROMPTS = [
  '在 (100,200) 插入三相断路器 QF1',
  '绘制 10kV 双母线接线图',
  '查询当前图纸中有哪些设备',
];

export default MessageList;
