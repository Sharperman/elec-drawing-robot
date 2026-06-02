/**
 * AppSkeleton.tsx
 * 应用首次加载时的品牌骨架屏
 * 展示品牌 Logo + 加载动画
 */
import React from 'react';
import { Zap } from 'lucide-react';

const AppSkeleton: React.FC = () => {
  return (
    <div className="h-screen w-screen bg-gray-950 flex flex-col items-center justify-center select-none">
      {/* Logo */}
      <div className="skeleton-logo">
        <Zap className="w-10 h-10 text-white" />
      </div>

      {/* 应用名 */}
      <h1 className="mt-6 text-xl font-bold text-white tracking-tight">
        电气图纸绘制机器人
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        AI-Powered Electrical Drawing Robot
      </p>

      {/* 加载动画 */}
      <div className="mt-8 flex flex-col items-center gap-3">
        <div className="dot-pulse">
          <span />
          <span />
          <span />
        </div>
        <p className="text-xs text-gray-600">正在连接后端服务...</p>
      </div>
    </div>
  );
};

export default AppSkeleton;
