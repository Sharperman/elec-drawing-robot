/**
 * ChatPanel.tsx
 * 对话面板主组件 - 升级版
 * 标题栏含会话信息 + CAD 状态 + 更多操作 + 运行模式
 */
import React, { useEffect, useCallback, useState } from 'react';
import { MessageSquare, RefreshCw, Trash2, Download, ChevronDown, FileText } from 'lucide-react';
import { clsx } from 'clsx';
import MessageList from './MessageList';
import InputBar from './InputBar';
import { useChat } from '@/hooks/useChat';
import { useSessionStore } from '@/stores/sessionStore';
import { useConnectionStore } from '@/stores/connectionStore';
import type { RunMode } from '@/types';

const ChatPanel: React.FC = () => {
  const { currentSessionId, sessions } = useSessionStore();
  const { isConnected, connectionError } = useConnectionStore();
  const [showMenu, setShowMenu] = useState(false);
  const [localReportPath, setLocalReportPath] = useState<string | null>(null);

  const {
    messages, streamingMessage, isLoading, isStreaming, error,
    agentSteps, reportPath: storeReportPath,
    sendMessage, stopStreaming, loadHistory, regenerateMessage, sendFeedback,
  } = useChat();

  // 同步 reportPath 到本地 state
  useEffect(() => {
    if (storeReportPath && storeReportPath !== localReportPath) {
      setLocalReportPath(storeReportPath);
    }
  }, [storeReportPath]);

  const handleReportOpen = useCallback(() => {
    const path = storeReportPath || localReportPath;
    if (path) {
      window.open(`file:///${path.replace(/\\/g, '/')}`, '_blank');
    }
  }, [storeReportPath, localReportPath]);

  const handleExampleClick = useCallback((prompt: string, mode?: RunMode) => {
    sendMessage(prompt, undefined, mode);
  }, [sendMessage]);

  const handleClearChat = () => {
    if (currentSessionId) {
      const { setMessages } = require('@/stores/chatStore').useChatStore.getState();
      setMessages(currentSessionId, []);
    }
    setShowMenu(false);
  };

  const currentSession = sessions.find((s) => s.session_id === currentSessionId);

  return (
    <div className="flex flex-col h-full bg-gray-950">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/50
                      glass-panel flex-shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600
                          flex items-center justify-center flex-shrink-0
                          shadow-sm shadow-blue-500/20">
            <MessageSquare className="w-3.5 h-3.5 text-white" />
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-gray-200 truncate">
              {currentSession?.title || '电气绘图助手'}
            </span>
            {currentSessionId && messages.length > 0 && (
              <span className="text-[10px] text-gray-600">{messages.length} 条消息</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* CAD 状态 */}
          <div
            className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px]
                       bg-gray-800/60 border border-gray-700/50"
            title={isConnected ? 'AutoCAD 已连接' : connectionError || 'AutoCAD 未连接'}
          >
            <div className={clsx(
              'w-1.5 h-1.5 rounded-full transition-colors duration-300',
              isConnected
                ? 'bg-green-400 glow-green'
                : 'bg-red-400 animate-pulse'
            )} />
            <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
              {isConnected ? 'CAD 在线' : 'CAD 离线'}
            </span>
          </div>

          {currentSessionId && (
            <>
              <button
                onClick={() => loadHistory(currentSessionId)}
                className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
                title="刷新消息"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>

              {/* 更多操作 */}
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="p-1.5 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
                {showMenu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
                    <div className="absolute right-0 top-8 z-50 w-44 py-1 rounded-lg
                                    bg-gray-800 border border-gray-700 shadow-xl">
                      <button
                        onClick={handleClearChat}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300
                                   hover:bg-gray-700 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-gray-500" />
                        清空对话
                      </button>
                      <button
                        onClick={() => { setShowMenu(false); handleReportOpen(); }}
                        disabled={!storeReportPath && !localReportPath}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs
                                   text-gray-300 hover:bg-gray-700 transition-colors
                                   disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <FileText className="w-3.5 h-3.5 text-gray-500" />
                        查看审查报告
                      </button>
                      <button
                        onClick={() => setShowMenu(false)}
                        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300
                                   hover:bg-gray-700 transition-colors"
                      >
                        <Download className="w-3.5 h-3.5 text-gray-500" />
                        导出对话
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
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
          agentSteps={agentSteps}
          isStreaming={isStreaming}
          onExampleClick={handleExampleClick}
          onRegenerate={regenerateMessage}
          onFeedback={sendFeedback}
        />
      )}

      {/* 错误提示 */}
      {error && (
        <div className="mx-3 mb-2 px-3 py-2 bg-red-900/20 border border-red-800/50 rounded-lg text-xs text-red-400">
          ⚠️ {error}
        </div>
      )}

      {/* 输入栏 */}
      <InputBar
        onSend={(msg, _img, mode) => sendMessage(msg, _img, (mode as RunMode) || 'auto')}
        onStop={stopStreaming}
        isLoading={isLoading}
        isStreaming={isStreaming}
        disabled={!currentSessionId}
      />
    </div>
  );
};

export default ChatPanel;
