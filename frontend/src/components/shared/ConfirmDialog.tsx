/**
 * 确认对话框组件
 */
import React from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { clsx } from 'clsx';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  variant = 'warning',
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  const confirmBtnClass = clsx('btn', {
    'btn-danger': variant === 'danger',
    'btn-primary': variant === 'info',
    'bg-yellow-600 text-white hover:bg-yellow-700 btn': variant === 'warning',
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 背景遮罩 */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* 对话框 */}
      <div className="relative z-10 bg-gray-800 border border-gray-600 rounded-xl shadow-2xl w-full max-w-md mx-4 animate-fade-in">
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <div className="flex items-center gap-2">
            {variant !== 'info' && (
              <AlertTriangle
                className={clsx('w-5 h-5', {
                  'text-red-400': variant === 'danger',
                  'text-yellow-400': variant === 'warning',
                })}
              />
            )}
            <h3 className="text-base font-semibold text-gray-100">{title}</h3>
          </div>
          <button
            onClick={onCancel}
            className="btn-ghost p-1 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="px-5 pb-5">
          <p className="text-sm text-gray-300 leading-relaxed">{message}</p>

          {/* 操作按钮 */}
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={onCancel} className="btn-secondary">
              {cancelText}
            </button>
            <button onClick={onConfirm} className={confirmBtnClass}>
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
