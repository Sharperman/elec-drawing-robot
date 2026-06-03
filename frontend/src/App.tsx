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

// 懒加载配置页
const StandardsConfig = lazy(() => import('@/components/config/StandardsConfig'));
const SymbolLibrary = lazy(() => import('@/components/config/SymbolLibrary'));

const PageLoader: React.FC = () => (
  <div className="flex items-center justify-center h-full bg-gray-950">
    <LoadingSpinner size="lg" />
  </div>
);

const App: React.FC = () => {
  const [appReady, setAppReady] = useState(false);

  useEffect(() => {
    // 初始加载骨架屏展示 800ms，给用户良好的品牌过渡
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

// ─── 设置页 ─────────────────────────────────────────────────────

const SettingsPage: React.FC = () => {
  const { settings, updateSettings } = useSettingsStore();
  const [apiKey, setApiKey] = React.useState(settings?.openaiApiKey ?? '');
  const [baseUrl, setBaseUrl] = React.useState(settings?.openaiBaseUrl ?? '');
  const [modelName, setModelName] = React.useState(settings?.modelName ?? '');
  const [autocadVersion, setAutocadVersion] = React.useState(settings?.autocadVersion ?? '');
  const [snapshotInterval, setSnapshotInterval] = React.useState(settings?.snapshotInterval ?? 5);
  const [saved, setSaved] = React.useState(false);

  const handleSave = () => {
    updateSettings({
      openaiApiKey: apiKey,
      openaiBaseUrl: baseUrl,
      modelName,
      autocadVersion,
      snapshotInterval,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputCls =
    'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400 font-mono transition-all';

  return (
    <div className="flex flex-col h-full bg-gray-950 p-6 overflow-y-auto">
      <h1 className="text-lg font-semibold text-gray-100 mb-6">应用设置</h1>
      <div className="max-w-lg space-y-5">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">LLM API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">API Base URL</label>
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">模型名称</label>
          <input
            type="text"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="gpt-4o"
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">AutoCAD 版本</label>
          <input
            type="text"
            value={autocadVersion}
            onChange={(e) => setAutocadVersion(e.target.value)}
            placeholder="AutoCAD.Application"
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">截图刷新间隔（秒）</label>
          <input
            type="number"
            value={snapshotInterval}
            onChange={(e) => setSnapshotInterval(Number(e.target.value))}
            min={1}
            max={30}
            className={inputCls}
          />
        </div>
        <div className="flex justify-end pt-2">
          <button
            onClick={handleSave}
            className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm
                       font-medium transition-all shadow-sm shadow-blue-500/25
                       active:scale-95"
          >
            {saved ? '已保存 ✓' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;
