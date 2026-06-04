/**
 * 根组件 - 路由 + Toast + 初始加载骨架屏
 */
import React, { Suspense, lazy, useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import AppShell from '@/components/layout/AppShell';
import AppSkeleton from '@/components/shared/AppSkeleton';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ErrorBoundary from '@/components/shared/ErrorBoundary';
import { useSettingsStore } from '@/stores/settingsStore';
import apiClient from '@/services/apiClient';
import type { LLMProvider, CreateProviderRequest, TestProviderResponse } from '@/types';

// 懒加载配置页
const StandardsConfig = lazy(() => import('@/components/config/StandardsConfig'));
const SymbolLibrary = lazy(() => import('@/components/config/SymbolLibrary'));
const LogViewer = lazy(() => import('@/components/shared/LogViewer'));
const FeedbackRulesPage = lazy(() => import('@/components/config/FeedbackRulesPage'));
const TemplateLibrary = lazy(() => import('@/components/config/TemplateLibrary'));
const FontLineConfig = lazy(() => import('@/components/config/FontLineConfig'));
const VendorDocParser = lazy(() => import('@/components/config/VendorDocParser'));
const LearnPage = lazy(() => import('@/components/config/LearnPage'));

const PageLoader: React.FC = () => (
  <div className="flex items-center justify-center h-full bg-gray-950">
    <LoadingSpinner size="lg" />
  </div>
);

const App: React.FC = () => {
  const [appReady, setAppReady] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setAppReady(true), 800);
    return () => clearTimeout(timer);
  }, []);

  if (!appReady) {
    return <AppSkeleton />;
  }

  return (
    <ErrorBoundary>
    <BrowserRouter>
      <Toaster
        position="top-center"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            borderRadius: '0.75rem',
            fontSize: '0.875rem',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
          },
          success: {
            iconTheme: { primary: '#22c55e', secondary: '#fff' },
            style: {
              border: '1px solid rgba(34, 197, 94, 0.3)',
            },
          },
          error: {
            iconTheme: { primary: '#ef4444', secondary: '#fff' },
            style: {
              border: '1px solid rgba(239, 68, 68, 0.3)',
            },
          },
        }}
      />
      <Routes>
        <Route path="/" element={<AppShell />} />
        <Route
          path="/standards"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <StandardsConfig />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/symbols"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <SymbolLibrary />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/settings"
          element={
            <AppShellWrapper>
              <SettingsPage />
            </AppShellWrapper>
          }
        />
        <Route
          path="/logs"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <LogViewer />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/feedback-rules"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <FeedbackRulesPage />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/templates"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <TemplateLibrary />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/font-line"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <FontLineConfig />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/vendor-docs"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <VendorDocParser />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route
          path="/learn"
          element={
            <AppShellWrapper>
              <Suspense fallback={<PageLoader />}>
                <LearnPage />
              </Suspense>
            </AppShellWrapper>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
};

// ─── AppShellWrapper ────────────────────────────────────────────

const AppShellWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <AppShell mainContent={children} />;
};

// ─── 设置页（含 LLM 管理）──────────────────────────────────────

/** 消隐 API Key：仅显示前后 4 位 */
function maskKey(key: string): string {
  if (key.length <= 8) return '*'.repeat(key.length);
  return key.slice(0, 4) + '*'.repeat(key.length - 8) + key.slice(-4);
}

// ─── LLM 编辑弹窗 ──────────────────────────────────────────

interface LLMEditorProps {
  provider?: LLMProvider | null;
  onClose: () => void;
  onSaved: () => void;
}

const LLMEditorModal: React.FC<LLMEditorProps> = ({ provider, onClose, onSaved }) => {
  const isEdit = !!provider;
  const [name, setName] = useState(provider?.provider_name ?? '');
  const [baseUrl, setBaseUrl] = useState(provider?.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(provider?.model ?? '');
  const [temperature, setTemperature] = useState(provider?.temperature ?? 1.0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!name.trim() || !baseUrl.trim() || !apiKey.trim() || !model.trim()) {
      setError('所有字段必填');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const body: CreateProviderRequest = {
        provider_name: name.trim(),
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        model: model.trim(),
        temperature,
      };
      await apiClient.post('/api/llm/providers', body);
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const inputCls = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400 transition-all';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-100 mb-4">
          {isEdit ? '编辑供应商' : '添加供应商'}
        </h3>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">供应商名称</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="如 OpenAI / MiMo / DeepSeek" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">API Base URL</label>
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">API Key</label>
            <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={isEdit ? '留空则保留现有 Key' : 'sk-...'} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">模型名称</label>
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="如 gpt-4o / mimo-v2.5" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">温度 (0-2)</label>
            <input type="number" value={temperature} onChange={(e) => setTemperature(Number(e.target.value))} min={0} max={2} step={0.1} className={inputCls} />
          </div>
        </div>
        {error && <div className="mt-3 text-xs text-red-400">{error}</div>}
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm transition-colors">取消</button>
          <button onClick={handleSave} disabled={saving} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-all disabled:opacity-50">
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};

const SettingsPage: React.FC = () => {
  const { settings, updateSettings } = useSettingsStore();

  // ─── AutoCAD 设置 ───
  const [autocadVersion, setAutocadVersion] = useState(settings?.autocadVersion ?? '');
  const [snapshotInterval, setSnapshotInterval] = useState(settings?.snapshotInterval ?? 5);
  const [saved, setSaved] = useState(false);

  // ─── LLM 管理 ───
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResults, setTestResults] = useState<Record<number, TestProviderResponse>>({});
  const [visibleKeys, setVisibleKeys] = useState<Set<number>>(new Set());
  const [syncing, setSyncing] = useState(false);

  const fetchProviders = async () => {
    try {
      const res = await apiClient.get('/api/llm/providers');
      if (res.data?.code === 0) setProviders(res.data.data ?? []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchProviders(); }, []);

  const handleTest = async (id: number) => {
    setTestingId(id);
    try {
      const res = await apiClient.post(`/api/llm/providers/${id}/test`);
      setTestResults((prev) => ({ ...prev, [id]: res.data?.data ?? res.data }));
      fetchProviders();
    } catch { /* ignore */ }
    finally { setTestingId(null); }
  };

  const handleActivate = async (id: number, role: 'primary' | 'vision') => {
    try {
      await apiClient.post(`/api/llm/providers/${id}/activate`, { role });
      fetchProviders();
    } catch { /* ignore */ }
  };

  const handleDeleteProvider = async (id: number) => {
    if (!confirm('确定删除该供应商配置？')) return;
    try {
      await apiClient.delete(`/api/llm/providers/${id}`);
      fetchProviders();
    } catch { /* ignore */ }
  };

  const handleSyncEnv = async () => {
    setSyncing(true);
    try { await apiClient.post('/api/llm/env'); } catch { /* ignore */ }
    setTimeout(() => setSyncing(false), 1500);
  };

  const toggleKeyVisibility = (id: number) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleSave = () => {
    updateSettings({ autocadVersion, snapshotInterval });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputCls = 'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400 font-mono transition-all';

  const primaryProvider = providers.find((p) => p.is_primary);
  const visionProvider = providers.find((p) => p.is_vision);

  return (
    <div className="flex flex-col h-full bg-gray-950 p-6 overflow-y-auto">

      {/* ============ LLM 供应商管理 ============ */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-gray-100">LLM 供应商</h2>
            <p className="text-xs text-gray-500 mt-0.5">独立配置主力模型和多模态模型，修改后自动同步 .env</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSyncEnv}
              disabled={syncing}
              className="px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs transition-colors disabled:opacity-50"
            >
              {syncing ? '已同步 ✓' : '同步到 .env'}
            </button>
            <button
              onClick={() => { setEditingProvider(null); setEditorOpen(true); }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
              添加供应商
            </button>
          </div>
        </div>

        {/* 激活状态卡片 */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-2 h-2 rounded-full bg-blue-400" />
              <span className="text-xs text-gray-400">主力 LLM（文本推理）</span>
            </div>
            {primaryProvider ? (
              <div>
                <div className="text-sm font-medium text-gray-100">{primaryProvider.provider_name}</div>
                <div className="text-xs text-gray-500 font-mono mt-0.5">{primaryProvider.model}</div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">未配置</div>
            )}
          </div>
          <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-2 h-2 rounded-full bg-purple-400" />
              <span className="text-xs text-gray-400">多模态 LLM（视觉分析）</span>
            </div>
            {visionProvider ? (
              <div>
                <div className="text-sm font-medium text-gray-100">{visionProvider.provider_name}</div>
                <div className="text-xs text-gray-500 font-mono mt-0.5">{visionProvider.model}</div>
              </div>
            ) : (
              <div className="text-xs text-gray-600">未配置（将使用主力 LLM）</div>
            )}
          </div>
        </div>

        {/* Provider 列表 */}
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-500 border-t-transparent" />
          </div>
        ) : providers.length === 0 ? (
          <div className="text-center py-10 text-gray-600">
            <div className="text-3xl mb-2">🤖</div>
            <div className="text-sm">暂无 LLM 供应商配置</div>
            <div className="text-xs mt-1">点击「添加供应商」开始配置</div>
          </div>
        ) : (
          <div className="space-y-2">
            {providers.map((p) => (
              <div key={p.id} className="bg-gray-900/70 border border-gray-800 rounded-xl p-3 hover:border-gray-700 transition-all">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-gray-100">{p.provider_name}</span>
                      {p.is_primary && <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">主力</span>}
                      {p.is_vision && <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30">多模态</span>}
                      {p.test_status === 'ok' && <span className="w-1.5 h-1.5 rounded-full bg-green-500" title="连接正常" />}
                      {p.test_status === 'fail' && <span className="w-1.5 h-1.5 rounded-full bg-red-500" title="连接失败" />}
                    </div>
                    <div className="space-y-0.5 text-xs text-gray-500">
                      <div className="font-mono">{p.model}</div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-gray-600">Key:</span>
                        <span className="font-mono text-gray-400">
                          {visibleKeys.has(p.id) ? p.api_key.replace(/\*/g, '•') : maskKey(p.api_key)}
                        </span>
                        <button onClick={() => toggleKeyVisibility(p.id)} className="text-gray-600 hover:text-gray-400 transition-colors" title={visibleKeys.has(p.id) ? '隐藏' : '显示'}>
                          {visibleKeys.has(p.id)
                            ? <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                            : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                          }
                        </button>
                      </div>
                      <div className="text-gray-600 truncate">{p.base_url}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                    {!p.is_primary && (
                      <button onClick={() => handleActivate(p.id, 'primary')} className="p-1.5 rounded-lg hover:bg-blue-500/20 text-gray-500 hover:text-blue-400 transition-all" title="设为主力 LLM">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
                      </button>
                    )}
                    {!p.is_vision && (
                      <button onClick={() => handleActivate(p.id, 'vision')} className="p-1.5 rounded-lg hover:bg-purple-500/20 text-gray-500 hover:text-purple-400 transition-all" title="设为多模态 LLM">
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                      </button>
                    )}
                    <button onClick={() => handleTest(p.id)} disabled={testingId === p.id} className="p-1.5 rounded-lg hover:bg-green-500/20 text-gray-500 hover:text-green-400 transition-all disabled:opacity-50" title="测试连接">
                      {testingId === p.id
                        ? <div className="w-3.5 h-3.5 animate-spin rounded-full border-2 border-green-500 border-t-transparent" />
                        : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      }
                    </button>
                    <button onClick={() => { setEditingProvider(p); setEditorOpen(true); }} className="p-1.5 rounded-lg hover:bg-gray-700 text-gray-500 hover:text-gray-300 transition-all" title="编辑">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                    </button>
                    <button onClick={() => handleDeleteProvider(p.id)} className="p-1.5 rounded-lg hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-all" title="删除">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                  </div>
                </div>
                {testResults[p.id] && (
                  <div className={`mt-2 p-2.5 rounded-lg text-xs ${testResults[p.id].status === 'ok' ? 'bg-green-500/10 border border-green-500/20 text-green-400' : 'bg-red-500/10 border border-red-500/20 text-red-400'}`}>
                    {testResults[p.id].status === 'ok'
                      ? <>连接成功 — {testResults[p.id].elapsed_ms}ms — 模型: {testResults[p.id].model}{testResults[p.id].response && <div className="text-green-500/70 mt-0.5">响应: {testResults[p.id].response}</div>}</>
                      : <div>{testResults[p.id].error}</div>
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ============ AutoCAD 设置 ============ */}
      <div className="border-t border-gray-800 pt-5">
        <h2 className="text-base font-semibold text-gray-100 mb-4">AutoCAD 设置</h2>
        <div className="max-w-lg space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">AutoCAD 版本</label>
            <input type="text" value={autocadVersion} onChange={(e) => setAutocadVersion(e.target.value)} placeholder="AutoCAD.Application" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">截图刷新间隔（秒）</label>
            <input type="number" value={snapshotInterval} onChange={(e) => setSnapshotInterval(Number(e.target.value))} min={1} max={30} className={inputCls} />
          </div>
          <div className="flex justify-end pt-1">
            <button
              onClick={handleSave}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-all shadow-sm shadow-blue-500/25 active:scale-95"
            >
              {saved ? '已保存 ✓' : '保存设置'}
            </button>
          </div>
        </div>
      </div>

      {/* 编辑弹窗 */}
      {editorOpen && (
        <LLMEditorModal
          provider={editingProvider}
          onClose={() => { setEditorOpen(false); setEditingProvider(null); }}
          onSaved={() => { setEditorOpen(false); setEditingProvider(null); fetchProviders(); }}
        />
      )}
    </div>
  );
};

export default App;
