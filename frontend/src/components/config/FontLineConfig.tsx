/**
 * FontLineConfig.tsx
 * 字体与线型全局配置页 — P0-05 补充
 *
 * PRD 6.3 要求配置字体（字高、字体名）和线型（名称、样式）
 */
import React, { useState, useEffect } from 'react';
import apiClient from '@/services/apiClient';
import { PlusIcon, TrashIcon, PencilSquareIcon } from '@heroicons/react/24/outline';

// ─── 类型 ──────────────────────────────────────────────────────

interface FontConfig {
  name: string;
  height: number;
  width_factor: number;
  oblique_angle: number;
}

interface LineTypeConfig {
  name: string;
  description: string;
  pattern: string;
  recommended_use: string;
}

// ─── 字体编辑行 ────────────────────────────────────────────────

const FontRow: React.FC<{
  font: FontConfig;
  index: number;
  onChange: (idx: number, field: string, value: string | number) => void;
  onDelete: (idx: number) => void;
}> = ({ font, index, onChange, onDelete }) => (
  <div className="flex items-center gap-2 py-2 border-b border-gray-800/50 last:border-0">
    <input
      value={font.name}
      onChange={(e) => onChange(index, 'name', e.target.value)}
      placeholder="字体名"
      className="w-32 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                 placeholder-gray-600 focus:outline-none focus:border-blue-500"
    />
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-gray-600">字高</span>
      <input
        type="number"
        value={font.height}
        onChange={(e) => onChange(index, 'height', Number(e.target.value))}
        min={0.5}
        max={50}
        step={0.5}
        className="w-16 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                   focus:outline-none focus:border-blue-500"
      />
      <span className="text-[10px] text-gray-600">mm</span>
    </div>
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-gray-600">宽高比</span>
      <input
        type="number"
        value={font.width_factor}
        onChange={(e) => onChange(index, 'width_factor', Number(e.target.value))}
        min={0.5}
        max={2}
        step={0.1}
        className="w-14 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                   focus:outline-none focus:border-blue-500"
      />
    </div>
    <button
      onClick={() => onDelete(index)}
      className="p-1 rounded hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors ml-auto"
      title="删除"
    >
      <TrashIcon className="w-3.5 h-3.5" />
    </button>
  </div>
);

// ─── 线型编辑行 ────────────────────────────────────────────────

const LineTypeRow: React.FC<{
  lt: LineTypeConfig;
  index: number;
  onChange: (idx: number, field: string, value: string) => void;
  onDelete: (idx: number) => void;
}> = ({ lt, index, onChange, onDelete }) => (
  <div className="flex items-center gap-2 py-2 border-b border-gray-800/50 last:border-0">
    <input
      value={lt.name}
      onChange={(e) => onChange(index, 'name', e.target.value)}
      placeholder="线型名"
      className="w-28 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                 placeholder-gray-600 focus:outline-none focus:border-blue-500"
    />
    <input
      value={lt.description}
      onChange={(e) => onChange(index, 'description', e.target.value)}
      placeholder="描述"
      className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                 placeholder-gray-600 focus:outline-none focus:border-blue-500"
    />
    <input
      value={lt.pattern}
      onChange={(e) => onChange(index, 'pattern', e.target.value)}
      placeholder="线型图案"
      className="w-24 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200 font-mono
                 placeholder-gray-600 focus:outline-none focus:border-blue-500"
    />
    <input
      value={lt.recommended_use}
      onChange={(e) => onChange(index, 'recommended_use', e.target.value)}
      placeholder="推荐用途"
      className="w-28 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200
                 placeholder-gray-600 focus:outline-none focus:border-blue-500"
    />
    <button
      onClick={() => onDelete(index)}
      className="p-1 rounded hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors ml-auto"
      title="删除"
    >
      <TrashIcon className="w-3.5 h-3.5" />
    </button>
  </div>
);

// ─── 主组件 ────────────────────────────────────────────────────

const FontLineConfig: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'font' | 'linetype'>('font');
  const [fonts, setFonts] = useState<FontConfig[]>([
    { name: 'gbcbig.shx', height: 3.5, width_factor: 0.7, oblique_angle: 0 },
    { name: 'gbcbig.shx', height: 5.0, width_factor: 0.7, oblique_angle: 0 },
    { name: '宋体', height: 3.5, width_factor: 0.8, oblique_angle: 0 },
  ]);
  const [lineTypes, setLineTypes] = useState<LineTypeConfig[]>([
    { name: 'Continuous', description: '实线', pattern: '_______', recommended_use: '可见轮廓、主要设备' },
    { name: 'Dashed', description: '虚线', pattern: '_ _ _ _', recommended_use: '隐藏轮廓、预留位置' },
    { name: 'Center', description: '点划线', pattern: '___._.___', recommended_use: '轴线、对称中心线' },
    { name: 'Phantom', description: '双点划线', pattern: '___..___', recommended_use: '假想轮廓、移动范围' },
    { name: 'Dot', description: '点线', pattern: '.......', recommended_use: '辅助线、边界线' },
  ]);
  const [saved, setSaved] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleFontChange = (idx: number, field: string, value: string | number) => {
    setFonts((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const handleLineTypeChange = (idx: number, field: string, value: string) => {
    setLineTypes((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };

  const addFont = () => {
    setFonts((prev) => [...prev, { name: '', height: 3.5, width_factor: 0.7, oblique_angle: 0 }]);
  };

  const addLineType = () => {
    setLineTypes((prev) => [...prev, { name: '', description: '', pattern: '', recommended_use: '' }]);
  };

  const deleteFont = (idx: number) => setFonts((prev) => prev.filter((_, i) => i !== idx));
  const deleteLineType = (idx: number) => setLineTypes((prev) => prev.filter((_, i) => i !== idx));

  const handleSave = async () => {
    try {
      // 通过当前激活规范的 API 保存字体和线型配置
      const res = await apiClient.get('/api/standards');
      const standards = res.data.data ?? [];
      const active = standards.find((s: { is_active: boolean }) => s.is_active);
      if (!active) {
        showToast('没有激活的规范，请先在绘图规范页激活一个规范', 'error');
        return;
      }
      await apiClient.put(`/api/standards/${active.id}`, {
        ...active,
        font_configs: fonts,
        line_type_configs: lineTypes,
      });
      setSaved(true);
      showToast('字体和线型配置已保存');
      setTimeout(() => setSaved(false), 2000);
    } catch {
      showToast('保存失败，请重试', 'error');
    }
  };

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

      {/* 标题 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">字体与线型配置</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            管理全局字体样式和线型定义，应用于所有图纸
          </p>
        </div>
        <button
          onClick={handleSave}
          className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm
                     font-medium transition-all shadow-sm shadow-blue-500/25 active:scale-95"
        >
          {saved ? '已保存 ✓' : '保存配置'}
        </button>
      </div>

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 mb-5 bg-gray-900 rounded-lg p-1 w-fit">
        <button
          onClick={() => setActiveTab('font')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
            activeTab === 'font'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          字体配置 ({fonts.length})
        </button>
        <button
          onClick={() => setActiveTab('linetype')}
          className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
            activeTab === 'linetype'
              ? 'bg-blue-600 text-white'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          线型配置 ({lineTypes.length})
        </button>
      </div>

      {/* 内容 */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        {activeTab === 'font' ? (
          <>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-300">字体样式</h3>
              <button
                onClick={addFont}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-blue-400
                           hover:bg-blue-500/10 transition-colors"
              >
                <PlusIcon className="w-3.5 h-3.5" />
                添加字体
              </button>
            </div>
            {/* 表头 */}
            <div className="flex items-center gap-2 pb-1.5 border-b border-gray-800 text-[10px] text-gray-600">
              <span className="w-32">字体名称</span>
              <span className="w-16">字高(mm)</span>
              <span className="w-14">宽高比</span>
              <span className="ml-auto mr-8">操作</span>
            </div>
            {fonts.map((font, idx) => (
              <FontRow
                key={idx}
                font={font}
                index={idx}
                onChange={handleFontChange}
                onDelete={deleteFont}
              />
            ))}
          </>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-300">线型定义</h3>
              <button
                onClick={addLineType}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-blue-400
                           hover:bg-blue-500/10 transition-colors"
              >
                <PlusIcon className="w-3.5 h-3.5" />
                添加线型
              </button>
            </div>
            {/* 表头 */}
            <div className="flex items-center gap-2 pb-1.5 border-b border-gray-800 text-[10px] text-gray-600">
              <span className="w-28">线型名称</span>
              <span className="flex-1">描述</span>
              <span className="w-24">图案</span>
              <span className="w-28">推荐用途</span>
              <span className="ml-auto mr-8">操作</span>
            </div>
            {lineTypes.map((lt, idx) => (
              <LineTypeRow
                key={idx}
                lt={lt}
                index={idx}
                onChange={handleLineTypeChange}
                onDelete={deleteLineType}
              />
            ))}
          </>
        )}
      </div>

      {/* 说明 */}
      <div className="mt-4 p-3 bg-gray-900/50 border border-gray-800/50 rounded-lg">
        <p className="text-xs text-gray-600">
          💡 <strong>提示</strong>：字体和线型配置会关联到当前激活的绘图规范。修改后点击"保存配置"生效。
          推荐字体：工程制图使用 gbcbig.shx 或 simplex.shx；线型遵循 GB/T 18229 CAD 制图规则。
        </p>
      </div>
    </div>
  );
};

export default FontLineConfig;
