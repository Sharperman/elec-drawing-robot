/**
 * FeedbackRulesPage.tsx
 * 用户偏好/学习规则管理页
 *
 * PRD 6.3: "用户偏好记录（已学习的修改意见列表，可启用/禁用/删除）"
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/services/apiClient';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ConfirmDialog from '@/components/shared/ConfirmDialog';
import {
  LightBulbIcon,
  TrashIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  SparklesIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { CheckCircleIcon as CheckCircleIconSolid } from '@heroicons/react/24/solid';

// ─── 类型 ──────────────────────────────────────────────────────

interface LearnedRule {
  id: number;
  rule_content: string;
  confidence: number;
  source_count: number;
  is_active: boolean;
  category?: string;
  created_at: string;
  updated_at: string;
}

// ─── API ────────────────────────────────────────────────────────

const fetchRules = async (): Promise<LearnedRule[]> => {
  const res = await apiClient.get('/api/feedback/rules');
  return res.data.data ?? [];
};

const toggleRule = async (id: number, isActive: boolean): Promise<void> => {
  await apiClient.patch(`/api/feedback/rules/${id}`, { is_active: isActive });
};

const deleteRule = async (id: number): Promise<void> => {
  await apiClient.delete(`/api/feedback/rules/${id}`);
};

const triggerRefine = async (): Promise<{ new_rules_count: number }> => {
  const res = await apiClient.post('/api/feedback/refine');
  return res.data.data;
};

// ─── 置信度颜色 ────────────────────────────────────────────────

function confidenceColor(conf: number): string {
  if (conf >= 0.8) return 'text-green-400 bg-green-500/10 border-green-500/30';
  if (conf >= 0.6) return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30';
  return 'text-gray-400 bg-gray-500/10 border-gray-500/30';
}

function confidenceLabel(conf: number): string {
  if (conf >= 0.8) return '高';
  if (conf >= 0.6) return '中';
  return '低';
}

// ─── 主组件 ────────────────────────────────────────────────────

const FeedbackRulesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<LearnedRule | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const { data: rules = [], isLoading } = useQuery({
    queryKey: ['feedback-rules'],
    queryFn: fetchRules,
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) => toggleRule(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedback-rules'] });
      showToast('规则状态已更新');
    },
    onError: () => showToast('更新失败', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedback-rules'] });
      setDeleteTarget(null);
      showToast('规则已删除');
    },
    onError: () => showToast('删除失败', 'error'),
  });

  const refineMut = useMutation({
    mutationFn: triggerRefine,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['feedback-rules'] });
      showToast(`提炼完成，新增 ${data.new_rules_count} 条规则`);
    },
    onError: () => showToast('提炼失败', 'error'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-950 p-6 overflow-y-auto custom-scrollbar">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm ${
          toast.type === 'success'
            ? 'bg-green-900/80 border border-green-700 text-green-200'
            : 'bg-red-900/80 border border-red-700 text-red-200'
        }`}>
          {toast.message}
        </div>
      )}

      {/* 删除确认 */}
      {deleteTarget && (
        <ConfirmDialog
          isOpen={!!deleteTarget}
          title="删除规则"
          message={`确定要删除规则「${deleteTarget.rule_content.slice(0, 50)}...」吗？此操作不可撤销。`}
          onConfirm={() => deleteMut.mutate(deleteTarget.id)}
          onCancel={() => setDeleteTarget(null)}
          confirmText="删除"
          variant="danger"
        />
      )}

      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">用户偏好与学习规则</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            从您的反馈中自动提炼的绘图偏好规则，可启用/禁用/删除
          </p>
        </div>
        <button
          onClick={() => refineMut.mutate()}
          disabled={refineMut.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-purple-600 hover:bg-purple-500
                     text-white text-sm font-medium transition-colors disabled:opacity-50"
        >
          <ArrowPathIcon className={`w-4 h-4 ${refineMut.isPending ? 'animate-spin' : ''}`} />
          {refineMut.isPending ? '提炼中...' : '手动提炼'}
        </button>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <SparklesIcon className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-gray-500">总规则数</span>
          </div>
          <span className="text-xl font-semibold text-gray-200">{rules.length}</span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircleIconSolid className="w-4 h-4 text-green-400" />
            <span className="text-xs text-gray-500">已启用</span>
          </div>
          <span className="text-xl font-semibold text-gray-200">
            {rules.filter((r) => r.is_active).length}
          </span>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheckIcon className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-500">高置信度</span>
          </div>
          <span className="text-xl font-semibold text-gray-200">
            {rules.filter((r) => r.confidence >= 0.8).length}
          </span>
        </div>
      </div>

      {/* 规则列表 */}
      {rules.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <LightBulbIcon className="w-12 h-12 text-gray-700 mx-auto mb-3 opacity-30" />
            <p className="text-sm text-gray-600">暂无学习规则</p>
            <p className="text-xs text-gray-700 mt-1">
              在对话中对 AI 回复点击 👍/👎 提交反馈，系统将自动提炼规则
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`bg-gray-900 border rounded-lg p-3 transition-colors ${
                rule.is_active ? 'border-gray-700' : 'border-gray-800 opacity-60'
              }`}
            >
              <div className="flex items-start gap-3">
                {/* 规则内容 */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 leading-relaxed">{rule.rule_content}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${confidenceColor(rule.confidence)}`}>
                      置信度 {confidenceLabel(rule.confidence)} ({(rule.confidence * 100).toFixed(0)}%)
                    </span>
                    <span className="text-[10px] text-gray-600">
                      来源 {rule.source_count} 条反馈
                    </span>
                    <span className="text-[10px] text-gray-700">
                      {new Date(rule.created_at).toLocaleDateString('zh-CN')}
                    </span>
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => toggleMut.mutate({ id: rule.id, isActive: !rule.is_active })}
                    disabled={toggleMut.isPending}
                    className={`p-1.5 rounded transition-colors ${
                      rule.is_active
                        ? 'text-green-400 hover:bg-green-500/10'
                        : 'text-gray-600 hover:bg-gray-700 hover:text-gray-400'
                    }`}
                    title={rule.is_active ? '禁用此规则' : '启用此规则'}
                  >
                    {rule.is_active ? (
                      <CheckCircleIconSolid className="w-4 h-4" />
                    ) : (
                      <XCircleIcon className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => setDeleteTarget(rule)}
                    className="p-1.5 rounded hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors"
                    title="删除规则"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FeedbackRulesPage;
