/**
 * ConfirmCard.tsx
 * 用户确认预览卡片 - 绘图操作前显示操作计划，用户确认/取消
 */
import React from 'react';
import { Check, X, AlertTriangle, Wrench, PenTool, Pencil, Search } from 'lucide-react';
import { clsx } from 'clsx';
import type { PendingConfirmPlan } from '@/hooks/useChat';

interface ConfirmCardProps {
  plan: PendingConfirmPlan;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

/** 工具图标映射 */
const TOOL_ICONS: Record<string, React.FC<{ className?: string }>> = {
  InsertElement: PenTool,
  DrawConnection: Wrench,
  AddAnnotation: Pencil,
  ModifyElement: Wrench,
  QueryDrawing: Search,
};

/** 工具名称中文映射 */
const TOOL_LABELS: Record<string, string> = {
  InsertElement: '插入图元',
  DrawConnection: '绘制连线',
  AddAnnotation: '添加标注',
  ModifyElement: '修改图元',
  QueryDrawing: '查询图纸',
};

const ConfirmCard: React.FC<ConfirmCardProps> = ({ plan, onConfirm, onCancel, isLoading }) => {
  return (
    <div className="mx-3 mb-3 rounded-xl border border-amber-500/30 bg-amber-500/5
                    backdrop-blur-sm overflow-hidden animate-in fade-in slide-in-from-bottom-2
                    duration-300">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-amber-500/10">
        <div className="w-7 h-7 rounded-lg bg-amber-500/20 flex items-center justify-center">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-amber-300">确认执行操作</h3>
          <p className="text-xs text-amber-400/70 mt-0.5">
            请确认以下操作计划，确认后将通过 AutoCAD 执行
          </p>
        </div>
      </div>

      {/* 操作摘要 */}
      <div className="px-4 py-3">
        <p className="text-sm text-gray-200 leading-relaxed">{plan.summary}</p>
      </div>

      {/* 操作列表 */}
      {plan.operations.length > 0 && (
        <div className="px-4 pb-3 space-y-2">
          <span className="text-[10px] text-gray-600 uppercase tracking-wider">
            操作明细（{plan.operations.length} 项）
          </span>
          {plan.operations.map((op, idx) => {
            const Icon = TOOL_ICONS[op.tool] || Wrench;
            return (
              <div
                key={idx}
                className="flex items-start gap-3 px-3 py-2 rounded-lg
                           bg-gray-800/50 border border-gray-700/30"
              >
                <div className="w-6 h-6 rounded-md bg-gray-700/50 flex items-center justify-center
                                flex-shrink-0 mt-0.5">
                  <Icon className="w-3.5 h-3.5 text-gray-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-[10px] text-gray-500">
                    {TOOL_LABELS[op.tool] || op.tool}
                  </span>
                  <p className="text-xs text-gray-300 mt-0.5">{op.description}</p>
                </div>
                <span className="text-[10px] text-gray-600 flex-shrink-0">
                  #{idx + 1}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center gap-2 px-4 pb-3 pt-1">
        <button
          onClick={onCancel}
          disabled={isLoading}
          className={clsx(
            'flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium',
            'border border-gray-600 text-gray-400 hover:text-gray-200 hover:bg-gray-800',
            'transition-all duration-200',
            isLoading && 'opacity-50 cursor-not-allowed',
          )}
        >
          <X className="w-3.5 h-3.5" />
          取消
        </button>
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className={clsx(
            'flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium flex-1',
            'bg-amber-600 hover:bg-amber-500 text-white',
            'shadow-sm shadow-amber-500/25 transition-all duration-200',
            'active:scale-[0.98]',
            isLoading && 'opacity-50 cursor-not-allowed',
          )}
        >
          <Check className="w-3.5 h-3.5" />
          {isLoading ? '执行中...' : '确认执行'}
        </button>
      </div>
    </div>
  );
};

export default ConfirmCard;
