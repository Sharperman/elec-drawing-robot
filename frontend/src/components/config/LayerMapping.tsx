/**
 * LayerMapping.tsx
 * 图层映射配置表：展示并允许编辑规范中的图层配置（颜色/线型/线宽）
 */

import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/services/apiClient';
import { LayerConfig } from '@/types';
import {
  PencilSquareIcon,
  CheckIcon,
  XMarkIcon,
  PlusIcon,
} from '@heroicons/react/24/outline';

// ─── 类型 ─────────────────────────────────────────────────────────────────────

interface LayerMappingProps {
  standardId: string;
  layers: LayerConfig[];
}

interface LayerRowEditState {
  color_index: number;
  linetype: string;
  lineweight: string;
  description: string;
}

// ─── 常量 ─────────────────────────────────────────────────────────────────────

/** 常用 AutoCAD 线型 */
const LINETYPES = [
  'Continuous',
  'DASHED',
  'DASHED2',
  'DOTTED',
  'CENTER',
  'CENTER2',
  'HIDDEN',
  'HIDDEN2',
  'PHANTOM',
  'DASHDOT',
];

/** 常用线宽 (mm) */
const LINEWEIGHTS = ['DEFAULT', '0.13', '0.18', '0.25', '0.35', '0.50', '0.70', '1.00'];

/** AutoCAD 颜色索引 → CSS 颜色（常用 1-9） */
const ACI_COLORS: Record<number, string> = {
  1: '#FF0000',  // 红
  2: '#FFFF00',  // 黄
  3: '#00FF00',  // 绿
  4: '#00FFFF',  // 青
  5: '#0000FF',  // 蓝
  6: '#FF00FF',  // 品红
  7: '#FFFFFF',  // 白/黑
  8: '#808080',  // 灰
  9: '#C0C0C0',  // 浅灰
};

const aciToCss = (index: number): string =>
  ACI_COLORS[index] ?? `#${Math.floor(Math.random() * 0xffffff).toString(16).padStart(6, '0')}`;

// ─── API ──────────────────────────────────────────────────────────────────────

const updateLayerConfig = async ({
  standardId,
  layerName,
  data,
}: {
  standardId: string;
  layerName: string;
  data: Partial<LayerConfig>;
}): Promise<LayerConfig> => {
  const res = await apiClient.put(
    `/api/standards/${standardId}/layers/${encodeURIComponent(layerName)}`,
    data
  );
  return res.data.data;
};

// ─── 子组件：图层行 ────────────────────────────────────────────────────────────

interface LayerRowProps {
  layer: LayerConfig;
  standardId: string;
  onSaved: () => void;
}

const LayerRow: React.FC<LayerRowProps> = ({ layer, standardId, onSaved }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editState, setEditState] = useState<LayerRowEditState>({
    color_index: layer.color_index,
    linetype: layer.linetype,
    lineweight: layer.lineweight,
    description: layer.description ?? '',
  });

  const mut = useMutation({
    mutationFn: updateLayerConfig,
    onSuccess: () => {
      setIsEditing(false);
      onSaved();
    },
  });

  const handleSave = () => {
    mut.mutate({ standardId, layerName: layer.layer_name, data: editState });
  };

  const handleCancel = () => {
    setEditState({
      color_index: layer.color_index,
      linetype: layer.linetype,
      lineweight: layer.lineweight,
      description: layer.description ?? '',
    });
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <tr className="bg-gray-800/50">
        <td className="px-3 py-2 text-xs font-mono text-blue-300">{layer.layer_name}</td>

        {/* 颜色索引 */}
        <td className="px-3 py-2">
          <div className="flex items-center gap-2">
            <div
              className="w-4 h-4 rounded-sm border border-gray-700 flex-shrink-0"
              style={{ backgroundColor: aciToCss(editState.color_index) }}
            />
            <input
              type="number"
              min={1}
              max={256}
              value={editState.color_index}
              onChange={(e) =>
                setEditState((s) => ({ ...s, color_index: Number(e.target.value) }))
              }
              className="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs
                         text-gray-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </td>

        {/* 线型 */}
        <td className="px-3 py-2">
          <select
            value={editState.linetype}
            onChange={(e) => setEditState((s) => ({ ...s, linetype: e.target.value }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs
                       text-gray-200 focus:outline-none focus:border-blue-500"
          >
            {LINETYPES.map((lt) => (
              <option key={lt} value={lt}>{lt}</option>
            ))}
          </select>
        </td>

        {/* 线宽 */}
        <td className="px-3 py-2">
          <select
            value={editState.lineweight}
            onChange={(e) => setEditState((s) => ({ ...s, lineweight: e.target.value }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs
                       text-gray-200 focus:outline-none focus:border-blue-500"
          >
            {LINEWEIGHTS.map((lw) => (
              <option key={lw} value={lw}>{lw}</option>
            ))}
          </select>
        </td>

        {/* 描述 */}
        <td className="px-3 py-2">
          <input
            value={editState.description}
            onChange={(e) => setEditState((s) => ({ ...s, description: e.target.value }))}
            className="w-full bg-gray-700 border border-gray-600 rounded px-2 py-0.5 text-xs
                       text-gray-200 focus:outline-none focus:border-blue-500"
          />
        </td>

        {/* 操作 */}
        <td className="px-3 py-2">
          <div className="flex items-center gap-1">
            <button
              onClick={handleSave}
              disabled={mut.isPending}
              className="p-1 rounded hover:bg-green-700/40 text-green-400 transition-colors"
              title="保存"
            >
              <CheckIcon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleCancel}
              className="p-1 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-colors"
              title="取消"
            >
              <XMarkIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="hover:bg-gray-800/30 transition-colors group">
      <td className="px-3 py-2 text-xs font-mono text-gray-300">{layer.layer_name}</td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-2">
          <div
            className="w-3.5 h-3.5 rounded-sm border border-gray-700"
            style={{ backgroundColor: aciToCss(layer.color_index) }}
            title={`ACI: ${layer.color_index}`}
          />
          <span className="text-xs text-gray-400">{layer.color_index}</span>
        </div>
      </td>
      <td className="px-3 py-2 text-xs text-gray-400 font-mono">{layer.linetype}</td>
      <td className="px-3 py-2 text-xs text-gray-400">{layer.lineweight}</td>
      <td className="px-3 py-2 text-xs text-gray-500">{layer.description ?? '—'}</td>
      <td className="px-3 py-2">
        <button
          onClick={() => setIsEditing(true)}
          className="p-1 rounded hover:bg-gray-700 text-gray-600 hover:text-gray-300
                     transition-colors opacity-0 group-hover:opacity-100"
          title="编辑图层"
        >
          <PencilSquareIcon className="w-3.5 h-3.5" />
        </button>
      </td>
    </tr>
  );
};

// ─── 主组件 ────────────────────────────────────────────────────────────────────

/**
 * LayerMapping — 图层映射配置表
 *
 * 内嵌在 StandardsConfig 规范展开区域中
 * 支持逐行编辑图层颜色/线型/线宽
 */
const LayerMapping: React.FC<LayerMappingProps> = ({ standardId, layers }) => {
  const queryClient = useQueryClient();

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['standards'] });
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          图层配置（{layers.length} 个）
        </h4>
      </div>

      {layers.length === 0 ? (
        <div className="text-center py-6 text-gray-600 text-xs">
          <p>暂无图层配置</p>
          <p className="mt-1 opacity-70">可通过 API 添加图层配置</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-gray-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-900 text-gray-500">
                <th className="px-3 py-2 text-left font-medium">图层名称</th>
                <th className="px-3 py-2 text-left font-medium">颜色 (ACI)</th>
                <th className="px-3 py-2 text-left font-medium">线型</th>
                <th className="px-3 py-2 text-left font-medium">线宽 (mm)</th>
                <th className="px-3 py-2 text-left font-medium">描述</th>
                <th className="px-3 py-2 text-left font-medium w-16"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {layers.map((layer) => (
                <LayerRow
                  key={layer.layer_name}
                  layer={layer}
                  standardId={standardId}
                  onSaved={handleSaved}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default LayerMapping;
