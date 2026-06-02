/**
 * Toast 通知组件（封装 react-hot-toast）
 */
import React from 'react';
import toast from 'react-hot-toast';
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface ShowToastOptions {
  duration?: number;
}

export function showToast(
  type: ToastType,
  message: string,
  options?: ShowToastOptions
): string {
  const duration = options?.duration ?? 4000;

  const icons: Record<ToastType, React.ReactNode> = {
    success: <CheckCircle className="w-4 h-4 text-green-400" />,
    error: <XCircle className="w-4 h-4 text-red-400" />,
    warning: <AlertCircle className="w-4 h-4 text-yellow-400" />,
    info: <Info className="w-4 h-4 text-blue-400" />,
  };

  return toast(message, {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    icon: icons[type] as any,
    duration,
    style: {
      background: '#1e293b',
      color: '#e2e8f0',
      border: '1px solid #334155',
      borderRadius: '0.5rem',
      fontSize: '0.875rem',
    },
  });
}

// 快捷方法
export const toastSuccess = (msg: string) => showToast('success', msg);
export const toastError = (msg: string) => showToast('error', msg);
export const toastWarning = (msg: string) => showToast('warning', msg);
export const toastInfo = (msg: string) => showToast('info', msg);

// 导出默认 toast
export { toast };
