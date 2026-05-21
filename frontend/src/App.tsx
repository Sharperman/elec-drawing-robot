/**
 * 根组件 - 配置路由
 * AppShell 作为外壳包裹所有页面，子路由渲染到聊天面板区域
 */
import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import AppShell from '@/components/layout/AppShell';
import LoadingSpinner from '@/components/shared/LoadingSpinner';

// 懒加载配置页（减少主包体积）
const StandardsConfig = lazy(() => import('@/components/config/StandardsConfig'));
const SymbolLibrary = lazy(() => import('@/components/config/SymbolLibrary'));

/** 页面加载占位 */
const PageLoader: React.FC = () => (
  <div className="flex items-center justify-center h-full bg-gray-950">
    <LoadingSpinner size="lg" />
  </div>
);

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
          },
          success: { iconTheme: { primary: '#22c55e', secondary: '#fff' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
        }}
      />
      <Routes>
        {/*
          AppShell 内部固定渲染 ChatPanel（左中）和 AutoCADPreview（右）。
          配置类页面全屏替换聊天区域，通过 AppShell 内部 outlet 渲染（此处简化
          为直接渲染配置页，AppShell 根据路由自适应）。
         */}
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
  );
};

// ─── 辅助组件：带 AppShell 外壳的页面包裹 ────────────────────────────────────

/**
 * AppShellWrapper
 * 将配置页包裹在 AppShell 骨架内（保留 Sidebar + StatusBar），
 * 聊天面板区域替换为传入的 children。
 */
const AppShellWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 将 children 注入到 AppShell 的聊天区域
  // 通过 React context 传递（简化：直接用 AppShell 的 override prop）
  return <AppShell mainContent={children} />;
};

// ─── 简易设置页（占位，后续可完善） ─────────────────────────────────────────────

const SettingsPage: React.FC = () => {
  const [apiKey, setApiKey] = React.useState('');
  const [saved, setSaved] = React.useState(false);

  // 从 settingsStore 读取
  const { settings, updateSettings } = React.useMemo(() => {
    // 动态 import store 避免循环依赖
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { useSettingsStore } = require('@/stores/settingsStore');
    return useSettingsStore.getState();
  }, []);

  React.useEffect(() => {
    setApiKey(settings?.openaiApiKey ?? '');
  }, [settings?.openaiApiKey]);

  const handleSave = () => {
    updateSettings?.({ openaiApiKey: apiKey });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 p-6 overflow-y-auto">
      <h1 className="text-lg font-semibold text-gray-100 mb-6">应用设置</h1>
      <div className="max-w-lg space-y-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">OpenAI API Key</label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm
                       text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500
                       font-mono transition-colors"
          />
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm
                       font-medium transition-colors"
          >
            {saved ? '已保存 ✓' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default App;
