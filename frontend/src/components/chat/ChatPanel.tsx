/**
 * 对话面板主组件
 */
import React, { useEffect } from 'react';
import { MessageSquare, RefreshCw } from 'lucide-react';

import MessageList from './MessageList';
import InputBar from './InputBar';
import { useChat } from '@/hooks/useChat';
import { useSessionStore } from '@/stores/sessionStore';
import LoadingSpinner from '@/components/shared/LoadingSpinner';

const ChatPanel: React.FC = () => {
  const { currentSessionId } = useSessionStore();

  const {
    messages,
    streamingMessage,
    isLoading,
    isStreaming,
    error,
    sendMessage,
    stopStreaming,
    loadHistory,
  } = useChat();

  // 切换会话时加载历史消息
  useEffect(() => {
    if (currentSessionId) {
      loadHistory(currentSessionId);
    }
  }, [currentSessionId]);

  return (
    <div className="flex flex-col h-full bg-gray-950">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-gray-200">对话</span>
        </div>
        {currentSessionId && (
          <button
            onClick={() => loadHistory(currentSessionId)}
            className="btn-ghost p-1 rounded"
            title="刷新消息"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* 消息列表 */}
      {!currentSessionId ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <MessageSquare className="w-12 h-12 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">请在左侧选择或创建一个会话</p>
          </div>
        </div>
      ) : (
        <MessageList
          messages={messages}
          streamingContent={streamingMessage?.content}
          isLoading={isLoading}
        />
      )}

      {/* 错误提示 */}
      {error && (
        <div className="mx-3 mb-2 px-3 py-2 bg-red-900/30 border border-red-800 
                        rounded-lg text-xs text-red-400">
          ⚠️ {error}
        </div>
      )}

      {/* 输入栏 */}
      <InputBar
        onSend={sendMessage}
        onStop={stopStreaming}
        isLoading={isLoading}
        isStreaming={isStreaming}
        disabled={!currentSessionId}
      />
    </div>
  );
};

export default ChatPanel;
