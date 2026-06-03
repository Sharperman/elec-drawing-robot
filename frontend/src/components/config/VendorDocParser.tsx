/**
 * VendorDocParser.tsx
 * 厂家资料解析 — P1-03
 *
 * PRD US-04: 导入厂家设备资料（PDF/图片），
 * 提取设备参数并生成设备符号和材料表。
 */
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import apiClient from '@/services/apiClient';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import {
  DocumentTextIcon,
  ArrowUpTrayIcon,
  XMarkIcon,
  PlayIcon,
  TableCellsIcon,
  CubeIcon,
} from '@heroicons/react/24/outline';

// ─── 类型 ──────────────────────────────────────────────────────

interface EquipmentItem {
  name: string;
  model: string;
  quantity: number;
  params: Record<string, string>;
  dimensions: string;
}

interface MaterialItem {
  name: string;
  spec: string;
  quantity: number;
  unit: string;
}

interface ParseResult {
  equipment: EquipmentItem[];
  material_list: MaterialItem[];
}

// ─── 主组件 ────────────────────────────────────────────────────

const VendorDocParser: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [activeTab, setActiveTab] = useState<'equipment' | 'materials'>('equipment');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setResult(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/bmp': ['.bmp'],
      'image/tiff': ['.tif', '.tiff'],
      'image/webp': ['.webp'],
    },
    maxFiles: 1,
    maxSize: 20 * 1024 * 1024,
  });

  const handleParse = async () => {
    if (!file) return;
    setParsing(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await apiClient.post('/api/vendor-docs/parse', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data.data);
      showToast(`解析完成，识别到 ${res.data.data?.equipment?.length ?? 0} 台设备`);
    } catch {
      showToast('解析失败，请重试', 'error');
    } finally {
      setParsing(false);
    }
  };

  const handleApply = async () => {
    if (!result) return;
    setApplying(true);
    try {
      await apiClient.post('/api/vendor-docs/apply', result);
      showToast('设备已应用到 AutoCAD 图纸');
    } catch {
      showToast('应用失败，请确认 AutoCAD 已连接', 'error');
    } finally {
      setApplying(false);
    }
  };

  const clearFile = () => {
    setFile(null);
    setResult(null);
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
          <h1 className="text-lg font-semibold text-gray-100">厂家资料解析</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            导入厂家设备资料（PDF 或图片），自动提取设备参数并生成材料表
          </p>
        </div>
      </div>

      {/* 上传区域 */}
      {!file ? (
        <div
          {...getRootProps()}
          className={`flex-1 flex flex-col items-center justify-center border-2 border-dashed
                      rounded-xl transition-all cursor-pointer min-h-[300px]
                      ${isDragActive
                        ? 'border-blue-500 bg-blue-500/5'
                        : 'border-gray-700 hover:border-gray-600 hover:bg-gray-900/30'
                      }`}
        >
          <input {...getInputProps()} />
          <ArrowUpTrayIcon className={`w-12 h-12 mb-4 ${isDragActive ? 'text-blue-400' : 'text-gray-600'}`} />
          <p className="text-sm text-gray-400 mb-1">
            {isDragActive ? '松开以上传文件' : '拖拽设备资料文件到此处，或点击选择'}
          </p>
          <p className="text-xs text-gray-600">
            支持 PDF、JPG、PNG、BMP、TIFF、WebP，最大 20MB
          </p>
        </div>
      ) : (
        <>
          {/* 已选文件 */}
          <div className="flex items-center gap-3 p-3 bg-gray-900 border border-gray-800 rounded-lg mb-4">
            <DocumentTextIcon className="w-8 h-8 text-blue-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-200 truncate">{file.name}</p>
              <p className="text-xs text-gray-600">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            {!parsing && (
              <button
                onClick={clearFile}
                className="p-1.5 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={handleParse}
              disabled={parsing}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500
                         text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {parsing ? (
                <>
                  <LoadingSpinner size="sm" />
                  解析中...
                </>
              ) : (
                <>
                  <DocumentTextIcon className="w-4 h-4" />
                  开始解析
                </>
              )}
            </button>
            {result && result.equipment.length > 0 && (
              <button
                onClick={handleApply}
                disabled={applying}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500
                           text-white text-sm font-medium transition-colors disabled:opacity-50"
              >
                <PlayIcon className="w-4 h-4" />
                {applying ? '应用中...' : '应用到 AutoCAD'}
              </button>
            )}
          </div>

          {/* 解析结果 */}
          {result && (
            <div className="flex-1">
              {/* Tab */}
              <div className="flex items-center gap-1 mb-4 bg-gray-900 rounded-lg p-1 w-fit">
                <button
                  onClick={() => setActiveTab('equipment')}
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'equipment'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  <CubeIcon className="w-3.5 h-3.5" />
                  设备清单 ({result.equipment.length})
                </button>
                <button
                  onClick={() => setActiveTab('materials')}
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    activeTab === 'materials'
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                >
                  <TableCellsIcon className="w-3.5 h-3.5" />
                  材料表 ({result.material_list.length})
                </button>
              </div>

              {/* 设备清单 */}
              {activeTab === 'equipment' && (
                <div className="space-y-2">
                  {result.equipment.length === 0 ? (
                    <p className="text-sm text-gray-600 text-center py-8">未识别到设备</p>
                  ) : (
                    result.equipment.map((eq, idx) => (
                      <div key={idx} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                            <CubeIcon className="w-4 h-4 text-blue-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <h4 className="text-sm font-medium text-gray-200">{eq.name}</h4>
                              {eq.model && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                                  {eq.model}
                                </span>
                              )}
                              <span className="text-xs text-gray-600 ml-auto">
                                ×{eq.quantity || 1}
                              </span>
                            </div>
                            {Object.keys(eq.params).length > 0 && (
                              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
                                {Object.entries(eq.params).map(([key, val]) => (
                                  <div key={key} className="flex items-baseline gap-1 text-xs">
                                    <span className="text-gray-600">{key}:</span>
                                    <span className="text-gray-300">{val}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {eq.dimensions && (
                              <p className="text-xs text-gray-600 mt-1">外形尺寸: {eq.dimensions}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 材料表 */}
              {activeTab === 'materials' && (
                <div className="space-y-2">
                  {result.material_list.length === 0 ? (
                    <p className="text-sm text-gray-600 text-center py-8">未生成材料表</p>
                  ) : (
                    <>
                      {/* 表头 */}
                      <div className="flex items-center gap-2 px-3 py-2 bg-gray-800/50 rounded text-[10px] text-gray-500 font-medium">
                        <span className="w-8">#</span>
                        <span className="flex-1">名称</span>
                        <span className="w-40">规格</span>
                        <span className="w-16 text-right">数量</span>
                        <span className="w-12 text-right">单位</span>
                      </div>
                      {result.material_list.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-2 px-3 py-2 bg-gray-900 border border-gray-800 rounded text-xs">
                          <span className="w-8 text-gray-600">{idx + 1}</span>
                          <span className="flex-1 text-gray-200">{item.name}</span>
                          <span className="w-40 text-gray-400 truncate">{item.spec}</span>
                          <span className="w-16 text-right text-gray-300">{item.quantity}</span>
                          <span className="w-12 text-right text-gray-500">{item.unit}</span>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default VendorDocParser;
