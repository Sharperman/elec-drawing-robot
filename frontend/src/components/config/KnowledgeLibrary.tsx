/**
 * KnowledgeLibrary — 用户知识库管理页面
 * 上传设计手册/规程/策划文件，自动 OCR + 向量化
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import apiClient from '@/services/apiClient';

interface KnowledgeDoc {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  page_count: number;
  doc_category: string;
  processing_status: string;
  processing_error?: string;
  chunk_count: number;
  total_tokens: number;
  ocr_engine: string;
  quality_score: number;
  quality_notes: string;
  has_latex: boolean;
  image_count: number;
  table_count: number;
  created_at: string;
}

interface ChunkData {
  index: number;
  text: string;
  metadata: Record<string, string>;
}

interface ImageData {
  path: string;
  page: number;
  width: number;
  height: number;
  caption: string;
}

interface DocDetail {
  chunks: ChunkData[];
  images: ImageData[];
  tables: string[];
  has_latex: boolean;
  latex_count: number;
  total_chunks: number;
}

interface SearchResult {
  document: string;
  metadata: Record<string, string>;
  score: number;
}

const STATUS_LABELS: Record<string, string> = {
  pending: '等待处理',
  extracting: '提取中',
  ocr: 'OCR 中',
  quality_check: '质量检查',
  chunking: '分块中',
  embedding: '向量化',
  ready: '就绪',
  error: '错误',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-500/20 text-gray-400',
  extracting: 'bg-blue-500/20 text-blue-400',
  ocr: 'bg-purple-500/20 text-purple-400',
  quality_check: 'bg-amber-500/20 text-amber-400',
  chunking: 'bg-cyan-500/20 text-cyan-400',
  embedding: 'bg-indigo-500/20 text-indigo-400',
  ready: 'bg-emerald-500/20 text-emerald-400',
  error: 'bg-red-500/20 text-red-400',
};

const FILE_ICONS: Record<string, string> = {
  pdf: '\u{1F4C4}', docx: '\u{1F4DD}', pptx: '\u{1F4CA}', txt: '\u{1F4C3}',
  jpg: '\u{1F5BC}', jpeg: '\u{1F5BC}', png: '\u{1F5BC}',
};

const CATEGORIES = ['全部', '设计手册', '规程', '策划文件', '厂家资料', '其他'];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const KnowledgeLibrary: React.FC = () => {
  const [docs, setDocs] = useState<KnowledgeDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState('全部');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState('');
  const [detailDoc, setDetailDoc] = useState<KnowledgeDoc | null>(null);
  const [detail, setDetail] = useState<DocDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const fetchDocs = useCallback(async () => {
    try {
      const cat = category === '全部' ? undefined : category;
      const params: Record<string, string> = {};
      if (cat) params.category = cat;
      const res = await apiClient.get('/api/knowledge/documents', { params });
      if (res.data?.data) setDocs(res.data.data.items ?? []);
    } catch { /* ignore */ }
  }, [category]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // 轮询未完成的文档状态
  useEffect(() => {
    const hasProcessing = docs.some(d => d.processing_status !== 'ready' && d.processing_status !== 'error');
    if (hasProcessing) {
      pollRef.current = setInterval(fetchDocs, 3000);
      return () => clearInterval(pollRef.current);
    }
    return undefined;
  }, [docs, fetchDocs]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const form = new FormData();
      for (let i = 0; i < files.length; i++) form.append('files', files[i]);
      const res = await apiClient.post(
        `/api/knowledge/upload?doc_category=${encodeURIComponent(category === '全部' ? '其他' : category)}`,
        form
      );
      const data = res.data?.data;
      const accepted = data?.uploaded?.filter((u: Record<string, string>) => u.status === 'accepted').length ?? 0;
      const skipped = data?.uploaded?.filter((u: Record<string, string>) => u.status !== 'accepted').length ?? 0;
      setMessage(`已上传 ${accepted} 个文件${skipped > 0 ? `，跳过了 ${skipped} 个不支持的格式` : ''}`);
      fetchDocs();
    } catch {
      setMessage('上传失败，请重试');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: number, filename: string) => {
    if (!confirm(`确定删除 "${filename}"？这将同时删除其向量数据。`)) return;
    try {
      await apiClient.delete(`/api/knowledge/documents/${id}`);
      fetchDocs();
    } catch { /* ignore */ }
  };

  const handleReprocess = async (id: number) => {
    try {
      await apiClient.post(`/api/knowledge/documents/${id}/reprocess`);
      fetchDocs();
    } catch { /* ignore */ }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const res = await apiClient.get('/api/knowledge/search', { params: { q: searchQuery, top_k: 5 } });
      setSearchResults(res.data?.data?.results ?? []);
    } catch { /* ignore */ }
    finally { setSearching(false); }
  };

  const handleViewDetail = async (doc: KnowledgeDoc) => {
    setDetailDoc(doc);
    setDetail(null);
    setLoadingDetail(true);
    try {
      const res = await apiClient.get(`/api/knowledge/documents/${doc.id}/chunks`);
      setDetail(res.data?.data ?? null);
    } catch { /* ignore */ }
    finally { setLoadingDetail(false); }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-6 pb-3">
        <h2 className="text-lg font-medium text-white">知识库管理</h2>
        <p className="text-sm text-slate-400 mt-1">
          上传设计手册、规程、策划文件，自动 OCR 并建立可检索的知识库
        </p>
      </div>

      {/* Upload + Search bar */}
      <div className="px-6 pb-4 flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.pptx,.txt,.jpg,.jpeg,.png,.bmp,.tiff"
          onChange={handleUpload}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500
                     text-white text-sm font-medium transition-all active:scale-95
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? '上传中...' : '上传文档'}
        </button>

        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-slate-300
                     focus:outline-none focus:border-blue-500"
        >
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>

        <div className="flex-1 min-w-[200px] flex items-center gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="搜索知识库..."
            className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm text-slate-300
                       placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-3 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm transition-all"
          >
            {searching ? '...' : '搜索'}
          </button>
        </div>
      </div>

      {message && (
        <div className="px-6 pb-3">
          <p className="text-sm text-emerald-400">{message}</p>
        </div>
      )}

      {/* Search results */}
      {searchResults.length > 0 && (
        <div className="px-6 pb-4">
          <h3 className="text-sm font-medium text-slate-300 mb-2">搜索结果</h3>
          <div className="space-y-2">
            {searchResults.map((r, i) => (
              <div key={i} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 text-sm text-slate-300">
                <div className="text-xs text-slate-500 mb-1">
                  {r.metadata?.filename ?? '未知文档'} · 相似度 {(r.score * 100).toFixed(0)}%
                </div>
                <p className="line-clamp-3">{r.document}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document grid */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className="relative rounded-xl bg-slate-800/80 border border-slate-700/50
                         hover:border-slate-600/80 transition-colors p-4 cursor-pointer"
              onClick={() => handleViewDetail(doc)}
            >
              {/* Status badge */}
              <span className={`absolute top-3 right-3 px-2 py-0.5 rounded-full text-[10px] font-medium
                ${STATUS_COLORS[doc.processing_status] ?? 'bg-gray-500/20 text-gray-400'}`}>
                {STATUS_LABELS[doc.processing_status] ?? doc.processing_status}
              </span>

              {/* File icon + name */}
              <div className="flex items-start gap-3 mb-3 pr-16">
                <span className="text-2xl">{FILE_ICONS[doc.file_type] ?? '\u{1F4CE}'}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {doc.file_type.toUpperCase()} · {formatSize(doc.file_size)}
                    {doc.page_count > 0 && ` · ${doc.page_count} 页`}
                  </p>
                </div>
              </div>

              {/* Processing details */}
              {doc.processing_status === 'ready' && (
                <div className="text-[11px] text-slate-500 space-y-0.5 mb-3">
                  <p>Chunks: {doc.chunk_count} · Tokens: ~{doc.total_tokens?.toLocaleString() ?? 0}</p>
                  {doc.ocr_engine && <p>OCR: {doc.ocr_engine} · 质量: {((doc.quality_score ?? 0) * 100).toFixed(0)}%</p>}
                  {(doc.image_count > 0 || doc.table_count > 0 || doc.has_latex) && (
                    <p className="flex items-center gap-2 text-amber-400/80">
                      {doc.image_count > 0 && <span>{'\u{1F5BC}'}{doc.image_count}</span>}
                      {doc.table_count > 0 && <span>{'\u{1F4CA}'}{doc.table_count}</span>}
                      {doc.has_latex && <span>{'\u{1F4D0}'}公式</span>}
                    </p>
                  )}
                </div>
              )}
              {doc.processing_status === 'error' && doc.processing_error && (
                <p className="text-[11px] text-red-400 mb-2 line-clamp-2">{doc.processing_error}</p>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                {doc.processing_status === 'error' && (
                  <button onClick={() => handleReprocess(doc.id)}
                    className="text-[11px] text-amber-400 hover:text-amber-300 transition-colors">
                    重试
                  </button>
                )}
                <button onClick={() => handleDelete(doc.id, doc.filename)}
                  className="text-[11px] text-slate-500 hover:text-red-400 transition-colors ml-auto">
                  删除
                </button>
              </div>
            </div>
          ))}

          {docs.length === 0 && (
            <div className="col-span-full flex flex-col items-center justify-center py-16 text-slate-500">
              <span className="text-4xl mb-3">{'\u{1F4DA}'}</span>
              <p className="text-sm">知识库为空</p>
              <p className="text-xs mt-1">上传 PDF / DOCX / PPTX 文档开始构建</p>
            </div>
          )}
        </div>
      </div>

      {/* Detail Panel */}
      {detailDoc && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 pb-8 px-4 bg-black/60" onClick={() => setDetailDoc(null)}>
          <div className="w-full max-w-4xl max-h-[85vh] overflow-y-auto rounded-2xl bg-slate-900 border border-slate-700 p-6"
               onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-medium text-white">{detailDoc.filename}</h3>
                <p className="text-sm text-slate-400 mt-1">
                  {detailDoc.file_type.toUpperCase()} · {formatSize(detailDoc.file_size)}
                  {detailDoc.page_count > 0 && ` · ${detailDoc.page_count}页`} · {detailDoc.ocr_engine} OCR
                </p>
              </div>
              <button onClick={() => setDetailDoc(null)}
                className="p-2 rounded-lg hover:bg-slate-700 text-slate-400 transition-colors">
                { '\u2715' }
              </button>
            </div>

            {loadingDetail ? (
              <p className="text-slate-400 text-sm">加载中...</p>
            ) : detail ? (
              <div className="space-y-6">
                {/* Stats */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="rounded-xl bg-slate-800/50 p-4 text-center">
                    <p className="text-2xl font-medium text-white">{detail.total_chunks}</p>
                    <p className="text-xs text-slate-500 mt-1">文本分块</p>
                  </div>
                  <div className="rounded-xl bg-slate-800/50 p-4 text-center">
                    <p className="text-2xl font-medium text-amber-400">{detail.images.length}</p>
                    <p className="text-xs text-slate-500 mt-1">图片</p>
                  </div>
                  <div className="rounded-xl bg-slate-800/50 p-4 text-center">
                    <p className="text-2xl font-medium text-cyan-400">{detail.tables.length}</p>
                    <p className="text-xs text-slate-500 mt-1">表格</p>
                  </div>
                  <div className="rounded-xl bg-slate-800/50 p-4 text-center">
                    <p className="text-2xl font-medium text-purple-400">{detail.latex_count}</p>
                    <p className="text-xs text-slate-500 mt-1">公式</p>
                  </div>
                </div>

                {/* Images */}
                {detail.images.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-300 mb-3">提取的图片 ({detail.images.length})</h4>
                    <div className="grid grid-cols-3 gap-3">
                      {detail.images.slice(0, 9).map((img, i) => (
                        <div key={i} className="rounded-lg bg-slate-800 p-2 text-center">
                          <p className="text-[10px] text-slate-500 mb-1">第{img.page}页 {img.width}×{img.height}</p>
                          {img.caption && <p className="text-[11px] text-slate-400 mb-1 line-clamp-2">{img.caption}</p>}
                          <p className="text-[10px] text-slate-600 truncate">{img.path.split('/').pop()}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tables */}
                {detail.tables.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-slate-300 mb-3">提取的表格 ({detail.tables.length})</h4>
                    {detail.tables.slice(0, 3).map((tab, i) => (
                      <pre key={i} className="p-3 rounded-lg bg-slate-800 text-xs text-slate-300 overflow-x-auto mb-2 font-mono whitespace-pre-wrap">{tab}</pre>
                    ))}
                  </div>
                )}

                {/* Text chunks */}
                <div>
                  <h4 className="text-sm font-medium text-slate-300 mb-3">文本分块预览 (前10个)</h4>
                  <div className="space-y-2">
                    {detail.chunks.slice(0, 10).map((c) => (
                      <div key={c.index} className="p-3 rounded-lg bg-slate-800/50 text-xs text-slate-400 leading-relaxed">
                        <span className="text-slate-600 mr-2">#{c.index+1}</span>
                        {c.text}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-slate-500 text-sm">请等待文档处理完成后再查看</p>
            )}

            <div className="mt-6 pt-4 border-t border-slate-800 flex justify-end">
              <button onClick={() => setDetailDoc(null)}
                className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-sm text-slate-300 transition-colors">
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default KnowledgeLibrary;
