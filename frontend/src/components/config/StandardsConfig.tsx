/**
 * StandardsConfig.tsx
 * 绘图规范配置页：规范模板列表、激活/停用、创建/编辑/删除
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/services/apiClient';
import { DrawingStandard } from '@/types';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ConfirmDialog from '@/components/shared/ConfirmDialog';
import LayerMapping from './LayerMapping';
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  DocumentDuplicateIcon,
} from '@heroicons/react/24/outline';
import { CheckCircleIcon as CheckCircleIconSolid } from '@heroicons/react/24/solid';

// ─── API ──────────────────────────────────────────────────────────────────────

const fetchStandards = async (): Promise<DrawingStandard[]> => {
  const res = await apiClient.get('/api/standards');
  return res.data.data ?? [];
};

const createStandard = async (data: Partial<DrawingStandard>): Promise<DrawingStandard> => {
  const res = await apiClient.post('/api/standards', data);
  return res.data.data;
};

const updateStandard = async ({
  id,
  data,
}: {
  id: string;
  data: Partial<DrawingStandard>;
}): Promise<DrawingStandard> => {
  const res = await apiClient.put(`/api/standards/${id}`, data);
  return res.data.data;
};

const deleteStandard = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/standards/${id}`);
};

const activateStandard = async (id: string): Promise<void> => {
  await apiClient.post(`/api/standards/${id}/activate`);
};

// ─── 表单组件 ─────────────────────────────────────────────────────────────────

interface StandardFormProps {
  initial?: Partial<DrawingStandard>;
  onSubmit: (data: Partial<DrawingStandard>) => void;
  onCancel: () => void;
  isLoading: boolean;
}

const StandardForm: React.FC<StandardFormProps> = ({
  initial,
  onSubmit,
  onCancel,
  isLoading,
}) => {
  const [name, setName] = useState(initial?.name ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [version, setVersion] = useState(initial?.version ?? '1.0');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), description: description.trim(), version: version.trim() });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-xs text-gray-400 mb-1">规范名称 *</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="如：GB/T 4728 电气图形符号标准"
          className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm
                     text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500
                     transition-colors"
          required
        />
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">版本</label>
        <input
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          placeholder="1.0"
          className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm
                     text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500
                     transition-colors"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">描述</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="规范用途说明…"
          className="w-full bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm
                     text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500
                     transition-colors resize-none"
        />
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-md text-sm text-gray-400 hover:text-white
                     hover:bg-gray-700 transition-colors"
        >
          取消
        </button>
        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="px-4 py-1.5 rounded-md text-sm bg-blue-600 hover:bg-blue-500 text-white
                     font-medium transition-colors disabled:opacity-50"
        >
          {isLoading ? '保存中…' : initial ? '保存修改' : '创建规范'}
        </button>
      </div>
    </form>
  );
};

// ─── 主组件 ────────────────────────────────────────────────────────────────────

/**
 * StandardsConfig — 绘图规范配置页
 *
 * 功能：
 * - 列出所有绘图规范模板
 * - 激活/停用规范
 * - 创建/编辑/删除规范
 * - 展开查看图层映射详情（LayerMapping）
 */
const StandardsConfig: React.FC = () => {
  const queryClient = useQueryClient();

  // 展开详情的规范 ID
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // 编辑状态
  const [editingId, setEditingId] = useState<string | null>(null);
  // 新建弹层
  const [showCreate, setShowCreate] = useState(false);
  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState<DrawingStandard | null>(null);
  // Toast
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── 查询 ──────────────────────────────────────────────────────────────────

  const { data: standards = [], isLoading } = useQuery({
    queryKey: ['standards'],
    queryFn: fetchStandards,
  });

  // ── 变更 ──────────────────────────────────────────────────────────────────

  const createMut = useMutation({
    mutationFn: createStandard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['standards'] });
      setShowCreate(false);
      showToast('规范创建成功');
    },
    onError: () => showToast('创建失败，请重试', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: updateStandard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['standards'] });
      setEditingId(null);
      showToast('规范已更新');
    },
    onError: () => showToast('更新失败，请重试', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteStandard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['standards'] });
      setDeleteTarget(null);
      showToast('规范已删除');
    },
    onError: () => showToast('删除失败，请重试', 'error'),
  });

  const activateMut = useMutation({
    mutationFn: activateStandard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['standards'] });
      showToast('规范已激活');
    },
    onError: () => showToast('激活失败，请重试', 'error'),
  });  // ── 渲染 ──────────────────────────────────────────────────────────────────

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

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <ConfirmDialog
          isOpen={!!deleteTarget}
          title="删除规范"
          message={`确定要删除规范「${deleteTarget.name}」吗？此操作不可撤销。`}
          onConfirm={() => deleteMut.mutate(String(deleteTarget.id))}
          onCancel={() => setDeleteTarget(null)}
          confirmText="删除"
          variant="danger"
        />
      )}

      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">绘图规范配置</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            管理国标（GB/T 4728）电气图纸绘制规范和图层配置
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500
                     text-white text-sm font-medium transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          新建规范
        </button>
      </div>

      {/* 新建表单 */}
      {showCreate && (
        <div className="mb-4 bg-gray-900 border border-gray-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">创建新规范</h3>
          <StandardForm
            onSubmit={(data) => createMut.mutate(data)}
            onCancel={() => setShowCreate(false)}
            isLoading={createMut.isPending}
          />
        </div>
      )}

      {/* 规范列表 */}
      <div className="space-y-3">
        {standards.length === 0 ? (
          <div className="text-center py-16 text-gray-600">
            <DocumentDuplicateIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">暂无绘图规范，点击「新建规范」添加</p>
          </div>
        ) : (
          standards.map((std) => (
            <div
              key={std.id}
              className={`bg-gray-900 border rounded-lg overflow-hidden transition-colors
                          ${std.is_active
                            ? 'border-blue-600/50 shadow-[0_0_0_1px_rgba(37,99,235,0.2)]'
                            : 'border-gray-800'
                          }`}
            >
              {/* 规范头部 */}
              <div className="flex items-center gap-3 px-4 py-3">
                {/* 激活状态图标 */}
                <button
                  onClick={() => !std.is_active && activateMut.mutate(String(std.id))}
                  disabled={std.is_active || activateMut.isPending}
                  title={std.is_active ? '当前激活规范' : '点击激活此规范'}
                  className="flex-shrink-0"
                >
                  {std.is_active ? (
                    <CheckCircleIconSolid className="w-5 h-5 text-blue-500" />
                  ) : (
                    <CheckCircleIcon className="w-5 h-5 text-gray-600 hover:text-blue-400 transition-colors" />
                  )}
                </button>

                {/* 规范信息 */}
                <div className="flex-1 min-w-0">
                  {editingId === std.id.toString() ? (
                    <StandardForm
                      initial={std}
              onSubmit={(data) => updateMut.mutate({ id: String(std.id), data })}
                    onCancel={() => setEditingId(null)}
                      isLoading={updateMut.isPending}
                    />
                  ) : (
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200">{std.name}</span>
                        {std.is_active && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-600/20 text-blue-400 border border-blue-600/30">
                            激活中
                          </span>
                        )}
                        <span className="text-xs text-gray-600">v{std.version}</span>
                      </div>
                      {std.description && (
                        <p className="text-xs text-gray-500 mt-0.5 truncate">{std.description}</p>
                      )}
                    </div>
                  )}
                </div>

                {/* 操作按钮 */}
                {editingId !== std.id && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => setEditingId(std.id.toString())}
                      className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300
                                 transition-colors"
                      title="编辑规范"
                    >
                      <PencilSquareIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setDeleteTarget(std)}
                      disabled={std.is_active}
                      className="p-1.5 rounded hover:bg-red-900/30 text-gray-500 hover:text-red-400
                                 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title={std.is_active ? '激活中的规范无法删除' : '删除规范'}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setExpandedId(expandedId === std.id.toString() ? null : std.id.toString())}
                      className="p-1.5 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300
                                 transition-colors"
                      title="查看图层配置"
                    >
                      <ChevronRightIcon
                        className={`w-4 h-4 transition-transform ${
                          expandedId === std.id.toString() ? 'rotate-90' : ''
                        }`}
                      />
                    </button>
                  </div>
                )}
              </div>

              {/* 展开：图层映射详情 */}
              {expandedId === std.id.toString() && (
                <div className="border-t border-gray-800 bg-gray-950/50">
                  <LayerMapping standardId={String(std.id)} layers={std.layers ?? std.layer_configs ?? []} />
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default StandardsConfig;
