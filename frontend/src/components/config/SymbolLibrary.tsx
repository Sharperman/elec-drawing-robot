/**
 * SymbolLibrary.tsx
 * 电气图元符号库浏览页：搜索、分类筛选、查看详情、创建/编辑/删除
 */

import React, { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/services/apiClient';
import { Symbol as ElecSymbol } from '@/types';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ConfirmDialog from '@/components/shared/ConfirmDialog';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  RectangleGroupIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

// ─── API ──────────────────────────────────────────────────────────────────────

const fetchSymbols = async (search?: string): Promise<ElecSymbol[]> => {
  const params = search ? { search } : {};
  const res = await apiClient.get('/api/symbols', { params });
  // 后端返回 {total, page, page_size, items}，取 items 字段
  return res.data.data?.items ?? [];
};

const createSymbol = async (data: Partial<ElecSymbol>): Promise<ElecSymbol> => {
  const res = await apiClient.post('/api/symbols', data);
  return res.data.data;
};

const updateSymbol = async ({
  id,
  data,
}: {
  id: string;
  data: Partial<ElecSymbol>;
}): Promise<ElecSymbol> => {
  const res = await apiClient.put(`/api/symbols/${id}`, data);
  return res.data.data;
};

const deleteSymbol = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/symbols/${id}`);
};

// ─── 图元卡片组件 ─────────────────────────────────────────────────────────────

interface SymbolCardProps {
  symbol: ElecSymbol;
  onEdit: (sym: ElecSymbol) => void;
  onDelete: (sym: ElecSymbol) => void;
}

const SymbolCard: React.FC<SymbolCardProps> = ({ symbol, onEdit, onDelete }) => {
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-lg p-3 hover:border-gray-600
                 transition-colors cursor-default group relative"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* 图标占位（若无 SVG 显示首字母） */}
      <div
        className="w-full h-20 rounded-md bg-gray-800 flex items-center justify-center mb-2
                   border border-gray-700 overflow-hidden"
      >
        {symbol.svg_data ? (
          <div
            className="w-full h-full flex items-center justify-center p-2"
            dangerouslySetInnerHTML={{ __html: symbol.svg_data }}
          />
        ) : (
          <div className="flex flex-col items-center gap-1">
            <RectangleGroupIcon className="w-8 h-8 text-gray-600" />
            <span className="text-xs text-gray-600 font-mono">
              {symbol.block_name?.slice(0, 8) ?? 'N/A'}
            </span>
          </div>
        )}
      </div>

      {/* 图元名称 */}
      <p className="text-xs font-medium text-gray-300 truncate" title={symbol.name}>
        {symbol.name}
      </p>

      {/* 分类标签 */}
      <div className="flex items-center gap-1 mt-1 flex-wrap">
        {symbol.category && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700/60 text-gray-500">
            {symbol.category}
          </span>
        )}
        {symbol.standard && (
          <span className="text-xs px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-500/70">
            {symbol.standard}
          </span>
        )}
      </div>

      {/* 操作按钮浮层 */}
      {showActions && (
        <div className="absolute top-2 right-2 flex items-center gap-1
                        bg-gray-800/90 backdrop-blur-sm rounded-md px-1 py-0.5 shadow">
          <button
            onClick={() => onEdit(symbol)}
            className="p-1 hover:text-blue-400 text-gray-400 transition-colors"
            title="编辑"
          >
            <PencilSquareIcon className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(symbol)}
            className="p-1 hover:text-red-400 text-gray-400 transition-colors"
            title="删除"
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};

// ─── 图元表单 ─────────────────────────────────────────────────────────────────

interface SymbolFormProps {
  initial?: Partial<ElecSymbol>;
  onSubmit: (data: Partial<ElecSymbol>) => void;
  onCancel: () => void;
  isLoading: boolean;
}

const SymbolForm: React.FC<SymbolFormProps> = ({ initial, onSubmit, onCancel, isLoading }) => {
  const [form, setForm] = useState({
    name: initial?.name ?? '',
    category: initial?.category ?? '',
    block_name: initial?.block_name ?? '',
    standard: initial?.standard ?? 'GB/T 4728',
    description: initial?.description ?? '',
    aliases: (initial?.aliases ?? []).join(', '),
  });

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.block_name.trim()) return;
    onSubmit({
      ...form,
      aliases: form.aliases
        .split(',')
        .map((a) => a.trim())
        .filter(Boolean),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-400 mb-1">图元名称 *</label>
          <input
            value={form.name}
            onChange={set('name')}
            required
            className="input-field text-sm"
            placeholder="如：断路器"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">块名称 (Block) *</label>
          <input
            value={form.block_name}
            onChange={set('block_name')}
            required
            className="input-field text-sm font-mono"
            placeholder="如：CB_BREAKER"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">分类</label>
          <input
            value={form.category}
            onChange={set('category')}
            className="input-field text-sm"
            placeholder="如：保护元件"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">标准</label>
          <input
            value={form.standard}
            onChange={set('standard')}
            className="input-field text-sm"
            placeholder="GB/T 4728"
          />
        </div>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">别名（逗号分隔）</label>
        <input
          value={form.aliases}
          onChange={set('aliases')}
          className="input-field text-sm"
          placeholder="如：开关, breaker, 空开"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">描述</label>
        <textarea
          value={form.description}
          onChange={set('description')}
          rows={2}
          className="input-field text-sm resize-none"
          placeholder="图元功能说明…"
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
          disabled={isLoading}
          className="px-4 py-1.5 rounded-md text-sm bg-blue-600 hover:bg-blue-500 text-white
                     font-medium transition-colors disabled:opacity-50"
        >
          {isLoading ? '保存中…' : initial ? '保存修改' : '添加图元'}
        </button>
      </div>
    </form>
  );
};

// ─── 主组件 ────────────────────────────────────────────────────────────────────

/**
 * SymbolLibrary — GB/T 4728 电气图元符号库浏览页
 *
 * 功能：
 * - 全量/搜索展示所有图元
 * - 按分类筛选
 * - 新增/编辑/删除图元
 * - 图元卡片展示（含 SVG 预览）
 */
const SymbolLibrary: React.FC = () => {
  const queryClient = useQueryClient();

  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('全部');
  const [showCreate, setShowCreate] = useState(false);
  const [editingSymbol, setEditingSymbol] = useState<ElecSymbol | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ElecSymbol | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  // ── 查询 ──────────────────────────────────────────────────────────────────

  const { data: symbols = [], isLoading } = useQuery({
    queryKey: ['symbols', searchQuery],
    queryFn: () => fetchSymbols(searchQuery || undefined),
  });

  // 动态提取分类列表
  const categories = ['全部', ...Array.from(new Set(symbols.map((s) => s.category).filter(Boolean)))];

  // 按分类过滤
  const filteredSymbols =
    categoryFilter === '全部'
      ? symbols
      : symbols.filter((s) => s.category === categoryFilter);

  // 搜索触发
  const handleSearch = useCallback(() => {
    setSearchQuery(searchInput.trim());
  }, [searchInput]);

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  const clearSearch = () => {
    setSearchInput('');
    setSearchQuery('');
  };

  // ── 变更 ──────────────────────────────────────────────────────────────────

  const createMut = useMutation({
    mutationFn: createSymbol,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symbols'] });
      setShowCreate(false);
      showToast('图元添加成功');
    },
    onError: () => showToast('添加失败', 'error'),
  });

  const updateMut = useMutation({
    mutationFn: updateSymbol,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symbols'] });
      setEditingSymbol(null);
      showToast('图元已更新');
    },
    onError: () => showToast('更新失败', 'error'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteSymbol,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symbols'] });
      setDeleteTarget(null);
      showToast('图元已删除');
    },
    onError: () => showToast('删除失败', 'error'),
  });

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-gray-950">
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
          title="删除图元"
          message={`确定要删除图元「${deleteTarget.name}」吗？`}
          onConfirm={() => deleteMut.mutate(String(deleteTarget.id))}
          onCancel={() => setDeleteTarget(null)}
          confirmText="删除"
          variant="danger"
        />
      )}

      {/* 编辑弹层 */}
      {editingSymbol && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 w-full max-w-lg shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-200">编辑图元</h3>
              <button onClick={() => setEditingSymbol(null)} className="text-gray-500 hover:text-white">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <SymbolForm
              initial={editingSymbol}
              onSubmit={(data) => updateMut.mutate({ id: String(editingSymbol.id), data })}
              onCancel={() => setEditingSymbol(null)}
              isLoading={updateMut.isPending}
            />
          </div>
        </div>
      )}

      {/* 页面头部 */}
      <div className="px-6 pt-6 pb-4 flex-shrink-0 border-b border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-lg font-semibold text-gray-100">图元符号库</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              GB/T 4728 标准电气图形符号库（{symbols.length} 个图元）
            </p>
          </div>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500
                       text-white text-sm font-medium transition-colors"
          >
            <PlusIcon className="w-4 h-4" />
            添加图元
          </button>
        </div>

        {/* 搜索栏 */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <MagnifyingGlassIcon
              className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
            />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              placeholder="搜索图元名称或别名…"
              className="w-full pl-9 pr-8 py-1.5 bg-gray-800 border border-gray-700 rounded-lg
                         text-sm text-gray-200 placeholder-gray-600 focus:outline-none
                         focus:border-blue-500 transition-colors"
            />
            {searchInput && (
              <button
                onClick={clearSearch}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>
          <button
            onClick={handleSearch}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm text-gray-300
                       transition-colors"
          >
            搜索
          </button>
        </div>

        {/* 分类筛选标签 */}
        <div className="flex items-center gap-2 mt-3 flex-wrap">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors
                          ${categoryFilter === cat
                            ? 'bg-blue-600/30 text-blue-300 border border-blue-600/40'
                            : 'bg-gray-800 text-gray-500 hover:text-gray-300 hover:bg-gray-700 border border-transparent'
                          }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* 新建表单 */}
      {showCreate && (
        <div className="px-6 pt-4 pb-2 flex-shrink-0 border-b border-gray-800 bg-gray-900/50">
          <h3 className="text-sm font-medium text-gray-300 mb-3">添加新图元</h3>
          <SymbolForm
            onSubmit={(data) => createMut.mutate(data)}
            onCancel={() => setShowCreate(false)}
            isLoading={createMut.isPending}
          />
        </div>
      )}

      {/* 图元网格 */}
      <div className="flex-1 overflow-y-auto px-6 py-4 custom-scrollbar">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <LoadingSpinner size="lg" />
          </div>
        ) : filteredSymbols.length === 0 ? (
          <div className="text-center py-16 text-gray-600">
            <RectangleGroupIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">
              {searchQuery ? `未找到与「${searchQuery}」匹配的图元` : '暂无图元，点击「添加图元」'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-3">
            {filteredSymbols.map((sym) => (
              <SymbolCard
                key={sym.id}
                symbol={sym}
                onEdit={(s) => setEditingSymbol(s)}
                onDelete={(s) => setDeleteTarget(s)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SymbolLibrary;
