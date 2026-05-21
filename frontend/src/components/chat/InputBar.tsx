/**
 * 输入栏组件
 * 文字输入 + 语音按钮（P1占位）+ 附件按钮 + 发送
 */
import React, { useState, useRef, KeyboardEvent, useCallback } from 'react';
import { Send, Paperclip, Mic, Square, X } from 'lucide-react';
import { clsx } from 'clsx';

import FileUpload from './FileUpload';
import { useImageUpload } from '@/hooks/useImageUpload';
import { useSessionStore } from '@/stores/sessionStore';

interface InputBarProps {
  onSend: (message: string, imageData?: string) => void;
  onStop?: () => void;
  isLoading: boolean;
  isStreaming: boolean;
  disabled?: boolean;
}

const InputBar: React.FC<InputBarProps> = ({
  onSend,
  onStop,
  isLoading,
  isStreaming,
  disabled = false,
}) => {
  const [inputText, setInputText] = useState('');
  const [showUpload, setShowUpload] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { currentSessionId } = useSessionStore();

  const { previewUrl, imageData, handleImageFile, clearImage, isUploading } =
    useImageUpload(currentSessionId ?? undefined);

  const canSend = inputText.trim().length > 0 || imageData != null;
  const isBusy = isLoading || isStreaming || disabled;

  const handleSend = useCallback(() => {
    if (!canSend || isBusy) return;

    const message = inputText.trim();
    const img = imageData ?? undefined;

    onSend(message || '请分析上传的图片中的电气元件', img);
    setInputText('');
    clearImage();
    setShowUpload(false);

    // 重置 textarea 高度
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [canSend, isBusy, inputText, imageData, onSend, clearImage]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    // 自动调整高度
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  };

  const handleFileSelected = async (file: File) => {
    await handleImageFile(file);
  };

  return (
    <div className="border-t border-gray-700 bg-gray-900 px-3 pt-2 pb-3">
      {/* 图片预览区（上传后显示） */}
      {previewUrl && (
        <div className="mb-2 pl-1">
          <FileUpload
            onFileSelected={handleFileSelected}
            onClear={clearImage}
            previewUrl={previewUrl}
            isUploading={isUploading}
          />
        </div>
      )}

      {/* 拖拽上传区（点击附件按钮后展开） */}
      {showUpload && !previewUrl && (
        <div className="mb-2">
          <FileUpload
            onFileSelected={handleFileSelected}
            onClear={clearImage}
            className="w-full"
          />
        </div>
      )}

      {/* 输入区 */}
      <div className="flex items-end gap-2">
        {/* 附件按钮 */}
        <button
          onClick={() => setShowUpload((prev) => !prev)}
          className={clsx(
            'btn-ghost p-1.5 rounded-lg flex-shrink-0',
            showUpload && 'bg-gray-700 text-blue-400'
          )}
          title="上传图片"
          disabled={isBusy}
        >
          {showUpload ? <X className="w-4 h-4" /> : <Paperclip className="w-4 h-4" />}
        </button>

        {/* 文字输入 */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? '请先选择或创建会话...'
                : isStreaming
                ? 'AI 正在响应...'
                : '输入绘图指令（Enter 发送，Shift+Enter 换行）'
            }
            disabled={isBusy && !isStreaming}
            rows={1}
            className={clsx(
              'input-base resize-none pr-1 leading-5 transition-all min-h-[36px]',
              (isBusy && !isStreaming) && 'opacity-50 cursor-not-allowed'
            )}
          />
        </div>

        {/* 语音按钮（P1 占位） */}
        <button
          className="btn-ghost p-1.5 rounded-lg flex-shrink-0 opacity-40 cursor-not-allowed"
          title="语音输入（即将推出）"
          disabled
        >
          <Mic className="w-4 h-4" />
        </button>

        {/* 发送/停止按钮 */}
        {isStreaming ? (
          <button
            onClick={onStop}
            className="btn bg-red-600 text-white hover:bg-red-700 p-2 rounded-lg flex-shrink-0"
            title="停止生成"
          >
            <Square className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!canSend || isBusy}
            className={clsx(
              'p-2 rounded-lg flex-shrink-0 transition-colors',
              canSend && !isBusy
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            )}
            title="发送 (Enter)"
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 提示文字 */}
      <div className="mt-1.5 text-xs text-gray-600 text-center">
        AI 可能出错，请对 AutoCAD 操作结果进行确认
      </div>
    </div>
  );
};

export default InputBar;
