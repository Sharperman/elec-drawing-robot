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

// 懒加载配置页
const StandardsConfig = lazy(() => import('@/components/config/StandardsConfig'));
const SymbolLibrary = lazy(() => import('@/components/config/SymbolLibrary'));
const SettingsPage = lazy(() => import('@/components/config/SettingsPage'));
const LogViewer = lazy(() => import('@/components/shared/LogViewer'));
const FeedbackRulesPage = lazy(() => import('@/components/config/FeedbackRulesPage'));
const TemplateLibrary = lazy(() => import('@/components/config/TemplateLibrary'));
const FontLineConfig = lazy(() => import('@/components/config/FontLineConfig'));
const VendorDocParser = lazy(() => import('@/components/config/VendorDocParser'));
const LearnPage = lazy(() => import('@/components/config/LearnPage'));
const KnowledgeLibrary = lazy(() => import('@/components/config/KnowledgeLibrary'));
const HermesPage = lazy(() => import('@/components/config/HermesPage'));

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
          success: { iconTheme: { primary: '#22c55e', secondary: '#fff' }, style: { border: '1px solid rgba(34, 197, 94, 0.3)' } },
          error: { iconTheme: { primary: '#ef4444', secondary: '#fff' }, style: { border: '1px solid rgba(239, 68, 68, 0.3)' } },
        }}
      />
      <Routes>
        <Route path="/" element={<AppShell />} />
        {[
          { path: '/standards', C: StandardsConfig },
          { path: '/symbols', C: SymbolLibrary },
          { path: '/settings', C: SettingsPage },
          { path: '/logs', C: LogViewer },
          { path: '/feedback-rules', C: FeedbackRulesPage },
          { path: '/templates', C: TemplateLibrary },
          { path: '/font-line', C: FontLineConfig },
          { path: '/vendor-docs', C: VendorDocParser },
          { path: '/learn', C: LearnPage },
          { path: '/knowledge', C: KnowledgeLibrary },
          { path: '/hermes', C: HermesPage },
        ].map(({ path, C }) => (
          <Route
            key={path}
            path={path}
            element={
              <AppShellWrapper>
                <Suspense fallback={<PageLoader />}>
                  <C />
                </Suspense>
              </AppShellWrapper>
            }
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </ErrorBoundary>
  );
};

const AppShellWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AppShell mainContent={children} />
);

export default App;
