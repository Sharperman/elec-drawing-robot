/**
 * InputBar.tsx
 * 输入栏：运行模式选择器 + 聚焦发光 + 流式进度条 + 发送按钮动画 + 快捷指令
 */
import React, { useState, useRef, useCallback, KeyboardEvent } from 'react';
import { clsx } from 'clsx';
import { Send, Square, Paperclip, Command } from 'lucide-react';
import QuickCommandPanel from './QuickCommandPanel';
import type { RunMode } from '@/types';

interface InputBarProps {
  onSend: (message: string, imageData?: string, mode?: RunMode) => void;
  onStop: () => void;
  isLoading: boolean;
  isStreaming: boolean;
  disabled?: boolean;
}

const MODES: { key: RunMode; label: string; icon: string; desc: string }[] = [
  { key: 'auto',  label: '/Auto',  icon: '🤖', desc: '自动判断模式' },
  { key: 'check', label: '/Check', icon: '📋', desc: '图纸审查（优先 DXF 文本解析 + 规范知识库）' },
  { key: 'draw',  label: '/Draw',  icon: '✏️',  desc: '绘图模式（优先 COM 模式）' },
];

const InputBar: React.FC<InputBarProps> = ({
  onSend, onStop, isLoading, isStreaming, disabled,
}) => {
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const [showCommands, setShowCommands] = useState(false);
  const [mode, setMode] = useState<RunMode>('auto');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = input.trim().length > 0 && !isLoading && !disabled;

  // 自动调整高度
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }
  }, []);

  const handleSend = () => {
    if (!canSend) return;
    onSend(input.trim(), undefined, mode);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setShowCommands(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowCommands(false);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);
    adjustHeight();

    // 检测快捷指令
    if (val === '/' || val.endsWith('\n/')) {
      setShowCommands(true);
    } else if (!val.startsWith('/')) {
      setShowCommands(false);
    }
  };

  const handleCommandSelect = (command: string) => {
    setInput(command + ' ');
    setShowCommands(false);
    textareaRef.current?.focus();
  };

  const currentMode = MODES.find(m => m.key === mode)!;

  return (
    <div className="flex-shrink-0">
      {/* 流式进度条 */}
      {isStreaming && (
        <div className="h-0.5 bg-gray-800">
          <div className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-blue-500
                          animate-pulse bg-[length:200%_100%]" />
        </div>
      )}

      {/* 运行模式选择器 */}
      <div className="px-3 pt-2 pb-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-500 mr-1">运行模式</span>
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              disabled={isStreaming}
              title={m.desc}
              className={clsx(
                'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium',
                'transition-all duration-200 border',
                isStreaming && 'opacity-40 cursor-not-allowed',
                mode === m.key
                  ? 'bg-blue-600/20 border-blue-500/50 text-blue-400 shadow-sm shadow-blue-500/20'
                  : 'bg-gray-800/50 border-gray-700/50 text-gray-500 hover:text-gray-300 hover:bg-gray-800',
              )}
            >
              <span>{m.icon}</span>
              <span>{m.label}</span>
            </button>
          ))}
          {/* 当前模式说明 */}
          <span className="text-[10px] text-gray-600 ml-2 truncate">
            {currentMode.desc}
          </span>
        </div>
      </div>

      {/* 快捷指令面板 */}
      {showCommands && (
        <div className="px-3 pb-1">
          <QuickCommandPanel
            filter={input.slice(1)}
            onSelect={handleCommandSelect}
            onClose={() => setShowCommands(false)}
          />
        </div>
      )}

      {/* 输入区域 */}
      <div className={clsx(
        'mx-3 mb-3 rounded-xl border transition-all duration-200',
        'bg-gray-800/50 backdrop-blur-sm',
        focused
          ? 'border-blue-500/50 glow-blue'
          : 'border-gray-700/50',
      )}>
        <div className="flex items-end gap-2 px-3 py-2">
          {/* 附件按钮 */}
          <button
            className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-700/50
                       transition-colors flex-shrink-0 mb-0.5"
            title="上传图纸截图"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* 输入框 */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={disabled ? '请先创建会话...' : '输入绘图指令，Enter 发送，Shift+Enter 换行...'}
            rows={1}
            disabled={disabled || isStreaming}
            className="flex-1 bg-transparent resize-none text-sm text-gray-200
                       placeholder-gray-600 outline-none py-1.5
                       disabled:opacity-50 disabled:cursor-not-allowed
                       min-h-[24px] max-h-[160px]"
          />

          {/* 发送/停止按钮 */}
          {isStreaming ? (
            <button
              onClick={onStop}
              className="flex-shrink-0 p-2 rounded-lg bg-red-500/20 hover:bg-red-500/30
                         text-red-400 transition-all active:scale-95"
              title="停止生成"
            >
              <Square className="w-4 h-4" fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!canSend}
              className={clsx(
                'flex-shrink-0 p-2 rounded-lg transition-all active:scale-95',
                canSend
                  ? 'bg-blue-600 text-white hover:bg-blue-500 shadow-sm shadow-blue-500/25 animate-pulse'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed',
              )}
              title="发送 (Enter)"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* 底部提示 */}
        <div className="flex items-center justify-between px-3 pb-2">
          <span className="text-[10px] text-gray-600 flex items-center gap-1">
            <Command className="w-3 h-3" />
            <span>输入 / 查看快捷指令</span>
          </span>
          {input.length > 0 && (
            <span className="text-[10px] text-gray-600">{input.length} 字</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default InputBar;
