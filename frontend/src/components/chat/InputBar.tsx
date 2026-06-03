/**
 * InputBar.tsx
 * 输入栏：运行模式选择器 + 聚焦发光 + 流式进度条 + 发送按钮动画 + 快捷指令
 */
import React, { useState, useRef, useCallback, KeyboardEvent, useEffect } from 'react';
import { clsx } from 'clsx';
import { Send, Square, Paperclip, Command, X, Mic, MicOff } from 'lucide-react';
import QuickCommandPanel from './QuickCommandPanel';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
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
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [attachedImageName, setAttachedImageName] = useState<string>('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const canSend = (input.trim().length > 0 || !!attachedImage) && !isLoading && !disabled;

  // 自动调整高度
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    }
  }, []);

  // 语音输入
  const {
    isListening,
    transcript,
    isSupported: voiceSupported,
    startListening,
    stopListening,
  } = useSpeechRecognition();

  // 语音文本同步到输入框
  useEffect(() => {
    if (isListening && transcript) {
      setInput(transcript);
      adjustHeight();
    }
  }, [transcript, isListening, adjustHeight]);

  // 语音结束时自动发送
  const handleVoiceToggle = () => {
    if (isListening) {
      const finalText = stopListening();
      if (finalText) {
        setInput(finalText);
        // 自动发送
        setTimeout(() => {
          onSend(finalText, attachedImage || undefined, mode);
          setInput('');
          setAttachedImage(null);
          setAttachedImageName('');
          if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
          }
        }, 300);
      }
    } else {
      startListening();
    }
  };

  const handleSend = () => {
    if (!canSend) return;
    onSend(input.trim(), attachedImage || undefined, mode);
    setInput('');
    setAttachedImage(null);
    setAttachedImageName('');
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

  // 附件处理
  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 验证类型
    const validTypes = ['image/jpeg', 'image/png', 'image/bmp', 'image/tiff', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      return;
    }
    // 验证大小（10MB）
    if (file.size > 10 * 1024 * 1024) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      setAttachedImage(base64);
      setAttachedImageName(file.name);
    };
    reader.readAsDataURL(file);

    // 重置 input 以允许重复选择同一文件
    e.target.value = '';
  };

  const handleRemoveImage = () => {
    setAttachedImage(null);
    setAttachedImageName('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
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

      {/* 附件图片预览 */}
      {attachedImage && (
        <div className="px-3 pb-2">
          <div className="relative inline-block">
            <img
              src={`data:image/png;base64,${attachedImage}`}
              alt={attachedImageName}
              className="max-h-20 max-w-48 rounded-lg object-contain border border-gray-600"
            />
            <button
              onClick={handleRemoveImage}
              className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-700
                         border border-gray-500 flex items-center justify-center
                         hover:bg-red-600 transition-colors"
            >
              <X className="w-3 h-3 text-white" />
            </button>
            <span className="block text-[10px] text-gray-500 mt-0.5 truncate max-w-[180px]">
              {attachedImageName}
            </span>
          </div>
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
          {/* 隐藏文件输入 */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/bmp,image/tiff,image/webp"
            onChange={handleFileChange}
            className="hidden"
          />

          {/* 附件按钮 */}
          <button
            onClick={handleAttachClick}
            disabled={isStreaming}
            className={clsx(
              'p-1.5 rounded-lg transition-colors flex-shrink-0 mb-0.5',
              attachedImage
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50',
              isStreaming && 'opacity-40 cursor-not-allowed',
            )}
            title="上传图纸截图"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* 语音按钮（P1-01） */}
          {voiceSupported && (
            <button
              onClick={handleVoiceToggle}
              disabled={isStreaming && !isListening}
              className={clsx(
                'p-1.5 rounded-lg transition-all flex-shrink-0 mb-0.5',
                isListening
                  ? 'text-red-400 bg-red-500/20 animate-pulse shadow-sm shadow-red-500/20'
                  : 'text-gray-500 hover:text-gray-300 hover:bg-gray-700/50',
                (isStreaming && !isListening) && 'opacity-40 cursor-not-allowed',
              )}
              title={isListening ? '松开停止录音' : '语音输入'}
            >
              {isListening ? (
                <MicOff className="w-4 h-4" />
              ) : (
                <Mic className="w-4 h-4" />
              )}
            </button>
          )}

          {/* 输入框 */}
          <textarea
            ref={textareaRef}
            value={isListening ? transcript : input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={
              isListening
                ? '🎤 正在聆听...'
                : disabled
                  ? '请先创建会话...'
                  : '输入绘图指令，Enter 发送，Shift+Enter 换行...'
            }
            rows={1}
            disabled={disabled || isStreaming}
            className={clsx(
              'flex-1 bg-transparent resize-none text-sm text-gray-200',
              'placeholder-gray-600 outline-none py-1.5',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'min-h-[24px] max-h-[160px]',
              isListening && 'placeholder-red-400/60',
            )}
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
