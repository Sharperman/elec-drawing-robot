/**
 * TemplateLibrary.tsx
 * 图纸模板库 — P1-06
 *
 * 功能：
 * - 浏览强电/弱电系统图、平面布置图、接线图模板
 * - 按分类筛选
 * - 查看模板详情（元件列表、图层配置）
 * - 应用到当前 AutoCAD 图纸
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/services/apiClient';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import {
  Squares2X2Icon,
  BoltIcon,
  MapIcon,
  WrenchScrewdriverIcon,
  DocumentTextIcon,
  PlayIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';

// ─── 类型 ──────────────────────────────────────────────────────

interface TemplateSummary {
  id: string;
  name: string;
  category: string;
  description: string;
  voltage_level: string;
  element_count: number;
}

interface TemplateDetail extends TemplateSummary {
  elements: Array<{
    type: string;
    name: string;
    layer: string;
    params?: Record<string, string>;
  }>;
  layer_config: Array<{
    name: string;
    color: string;
    linetype: string;
    lineweight: number;
  }>;
}

// ─── API ────────────────────────────────────────────────────────

const fetchTemplates = async (): Promise<{
  templates: TemplateSummary[];
  categories: string[];
  total: number;
}> => {
  const res = await apiClient.get('/api/templates');
  return res.data.data;
};

const fetchTemplateDetail = async (id: string): Promise<TemplateDetail> => {
  const res = await apiClient.get(`/api/templates/${id}`);
  return res.data.data;
};

const applyTemplate = async (id: string): Promise<void> => {
  await apiClient.post(`/api/templates/${id}/apply`);
};

// ─── 分类图标 ──────────────────────────────────────────────────

const categoryIcons: Record<string, React.FC<{ className?: string }>> = {
  '强电系统图': BoltIcon,
  '弱电系统图': WrenchScrewdriverIcon,
  '平面布置图': MapIcon,
  '接线图': Squares2X2Icon,
};

function getCategoryIcon(cat: string): React.FC<{ className?: string }> {
  return categoryIcons[cat] || DocumentTextIcon;
}

// ─── 主组件 ────────────────────────────────────────────────────

const TemplateLibrary: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<TemplateDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const { data, isLoading } = useQuery({
    queryKey: ['templates', selectedCategory],
    queryFn: () => fetchTemplates(),
  });

  const applyMut = useMutation({
    mutationFn: applyTemplate,
    onSuccess: (_, id) => {
      showToast(`模板已应用，请查看 AutoCAD`);
    },
    onError: () => showToast('应用模板失败，请确认 AutoCAD 已连接', 'error'),
  });

  const templates = data?.templates ?? [];
  const categories = data?.categories ?? [];
  const filtered = selectedCategory
    ? templates.filter((t) => t.category === selectedCategory)
    : templates;

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetailData(null);
      return;
    }
    setExpandedId(id);
    setLoadingDetail(true);
    try {
      const detail = await fetchTemplateDetail(id);
      setDetailData(detail);
    } catch {
      showToast('加载模板详情失败', 'error');
    } finally {
      setLoadingDetail(false);
    }
  };

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

      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">图纸模板库</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            强电/弱电系统图、平面布置图、接线图的典型模板，点击应用即可在 AutoCAD 中生成
          </p>
        </div>
      </div>

      {/* 分类筛选 */}
      <div className="flex items-center gap-2 mb-5 flex-wrap">
        <button
          onClick={() => setSelectedCategory('')}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            !selectedCategory
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
          }`}
        >
          全部 ({templates.length})
        </button>
        {categories.map((cat) => {
          const Icon = getCategoryIcon(cat);
          const count = templates.filter((t) => t.category === cat).length;
          return (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {cat} ({count})
            </button>
          );
        })}
      </div>

      {/* 模板列表 */}
      {filtered.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <DocumentTextIcon className="w-12 h-12 text-gray-700 mx-auto mb-3 opacity-30" />
            <p className="text-sm text-gray-600">暂无该分类的模板</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((tpl) => {
            const Icon = getCategoryIcon(tpl.category);
            const isExpanded = expandedId === tpl.id;

            return (
              <div
                key={tpl.id}
                className={`bg-gray-900 border rounded-lg overflow-hidden transition-colors ${
                  isExpanded ? 'border-blue-600/50' : 'border-gray-800 hover:border-gray-700'
                }`}
              >
                {/* 模板头部 */}
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="w-5 h-5 text-blue-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-200">{tpl.name}</h3>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{tpl.description}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                          {tpl.voltage_level}
                        </span>
                        <span className="text-[10px] text-gray-600">
                          {tpl.element_count} 个元件
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-800">
                    <button
                      onClick={() => handleExpand(tpl.id)}
                      className="flex items-center gap-1 px-2.5 py-1 rounded text-xs text-gray-400
                                 hover:bg-gray-800 hover:text-gray-300 transition-colors"
                    >
                      {isExpanded ? (
                        <ChevronUpIcon className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDownIcon className="w-3.5 h-3.5" />
                      )}
                      {isExpanded ? '收起详情' : '查看详情'}
                    </button>
                    <button
                      onClick={() => applyMut.mutate(tpl.id)}
                      disabled={applyMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium
                                 bg-green-600 hover:bg-green-500 text-white transition-colors
                                 disabled:opacity-50 ml-auto"
                    >
                      <PlayIcon className="w-3.5 h-3.5" />
                      {applyMut.isPending ? '应用中...' : '应用模板'}
                    </button>
                  </div>
                </div>

                {/* 展开详情 */}
                {isExpanded && (
                  <div className="border-t border-gray-800 bg-gray-950/50 p-4 space-y-3">
                    {loadingDetail ? (
                      <div className="flex justify-center py-4">
                        <LoadingSpinner size="sm" />
                      </div>
                    ) : detailData ? (
                      <>
                        {/* 元件列表 */}
                        <div>
                          <h4 className="text-xs font-medium text-gray-400 mb-2">元件列表</h4>
                          <div className="space-y-1">
                            {detailData.elements.map((el, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-xs">
                                <span className="w-16 text-gray-500 flex-shrink-0">{el.type}</span>
                                <span className="text-gray-300">{el.name}</span>
                                <span className="text-[10px] text-gray-600 ml-auto">{el.layer}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* 图层配置 */}
                        <div>
                          <h4 className="text-xs font-medium text-gray-400 mb-2">图层配置</h4>
                          <div className="flex flex-wrap gap-1.5">
                            {detailData.layer_config.map((layer, idx) => (
                              <span
                                key={idx}
                                className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400"
                              >
                                {layer.name} ({layer.color}, {layer.linetype})
                              </span>
                            ))}
                          </div>
                        </div>
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default TemplateLibrary;
