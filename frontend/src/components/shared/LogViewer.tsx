/**
 * LogViewer.tsx - 后端日志查看器
 * 支持按级别过滤、关键词搜索、分页浏览
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Terminal, RefreshCw, Filter, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import apiClient from '@/services/apiClient';

interface LogFile {
  name: string;
  path: string;
  size_bytes: number;
  modified: string;
}

interface LogContent {
  file: string;
  total_lines: number;
  page: number;
  page_size: number;
  lines: string[];
  has_more: boolean;
}

const LOG_LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR'] as const;
type LogLevel = (typeof LOG_LEVELS)[number];

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'text-gray-500',
  INFO: 'text-blue-400',
  WARNING: 'text-yellow-400',
  ERROR: 'text-red-400',
};

const LogViewer: React.FC = () => {
  const [logFiles, setLogFiles] = useState<LogFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('app.log');
  const [logContent, setLogContent] = useState<LogContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState<LogLevel>('ALL');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // 加载日志文件列表
  const loadFiles = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/logs/list');
      if (res.data?.code === 0 && res.data.data) {
        setLogFiles(res.data.data);
        if (res.data.data.length > 0 && !selectedFile) {
          setSelectedFile(res.data.data[0].name);
        }
      }
    } catch (e) {
      console.warn('[LogViewer] Failed to load log files', e);
    }
  }, []);

  // 加载日志内容
  const loadContent = useCallback(async () => {
    if (!selectedFile) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ file: selectedFile, page: String(page) });
      if (level !== 'ALL') params.set('level', level);
      if (search) params.set('search', search);
      const res = await apiClient.get(`/api/logs/view?${params.toString()}`);
      if (res.data?.code === 0 && res.data.data) {
        setLogContent(res.data.data);
      } else {
        setError('加载日志失败');
      }
    } catch (e) {
      setError(`加载失败: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [selectedFile, level, search, page]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(loadContent, 5000);
    return () => clearInterval(timer);
  }, [autoRefresh, loadContent]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const highlightLine = (line: string) => {
    let levelClass = '';
    if (line.includes('| ERROR')) levelClass = LEVEL_COLORS.ERROR;
    else if (line.includes('| WARNING')) levelClass = LEVEL_COLORS.WARNING;
    else if (line.includes('| INFO')) levelClass = LEVEL_COLORS.INFO;
    else if (line.includes('| DEBUG')) levelClass = LEVEL_COLORS.DEBUG;
    return <span className={levelClass}>{line}</span>;
  };

  const totalPages = logContent ? Math.ceil(logContent.total_lines / logContent.page_size) : 0;

  return (
    <div className="flex flex-col h-full bg-gray-950">
      {/* 标题栏 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800/50 flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-gray-200">系统日志</span>
          {logContent && (
            <span className="text-[10px] text-gray-600">
              {logContent.total_lines} 行
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={clsx(
              'px-2 py-1 text-[10px] rounded transition-colors',
              autoRefresh
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-gray-800 text-gray-500 border border-gray-700 hover:text-gray-300'
            )}
          >
            {autoRefresh ? '自动刷新中' : '自动刷新'}
          </button>
          <button
            onClick={loadContent}
            disabled={loading}
            className="p-1.5 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200 transition-colors"
            title="刷新"
          >
            <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-gray-800/30 flex-shrink-0 bg-gray-900/50">
        {/* 文件选择 */}
        <select
          value={selectedFile}
          onChange={(e) => { setSelectedFile(e.target.value); setPage(1); }}
          className="bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700
                     focus:outline-none focus:border-emerald-500/50"
        >
          {logFiles.filter(f => !f.name.endsWith('.zip')).map(f => (
            <option key={f.name} value={f.name}>
              {f.name} ({formatSize(f.size_bytes)})
            </option>
          ))}
        </select>

        {/* 级别过滤 */}
        <div className="flex items-center gap-1.5">
          <Filter className="w-3 h-3 text-gray-500" />
          <div className="flex gap-0.5">
            {LOG_LEVELS.map(l => (
              <button
                key={l}
                onClick={() => { setLevel(l); setPage(1); }}
                className={clsx(
                  'px-1.5 py-0.5 text-[10px] rounded transition-colors',
                  level === l
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-gray-800 text-gray-500 border border-gray-700 hover:text-gray-300'
                )}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* 搜索 */}
        <div className="flex items-center gap-1.5 ml-auto">
          <Search className="w-3 h-3 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            onKeyDown={(e) => { if (e.key === 'Enter') loadContent(); }}
            placeholder="搜索..."
            className="bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700
                       w-32 focus:outline-none focus:border-emerald-500/50
                       placeholder:text-gray-600"
          />
        </div>
      </div>

      {/* 日志内容 */}
      <div className="flex-1 overflow-auto">
        {error && (
          <div className="px-4 py-2 text-xs text-red-400 bg-red-500/10 border-b border-red-500/20">
            {error}
          </div>
        )}

        {loading && !logContent && (
          <div className="flex items-center justify-center h-32 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" />
            加载中...
          </div>
        )}

        {logContent && (
          <div className="font-mono text-[11px] leading-relaxed">
            {logContent.lines.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-gray-600 text-xs">
                暂无匹配的日志
              </div>
            ) : (
              logContent.lines.map((line, i) => (
                <div
                  key={`${logContent.page}-${i}`}
                  className="px-4 py-0.5 hover:bg-gray-800/30 border-b border-gray-800/20
                             text-gray-400 whitespace-pre"
                >
                  {highlightLine(line)}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* 分页栏 */}
      {logContent && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-gray-800/50
                        flex-shrink-0 bg-gray-900/50">
          <span className="text-[10px] text-gray-600">
            第 {logContent.page}/{totalPages} 页，共 {logContent.total_lines} 行
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200
                         disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={!logContent.has_more}
              className="p-1 rounded hover:bg-gray-800 text-gray-400 hover:text-gray-200
                         disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LogViewer;
