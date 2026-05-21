/**
 * 加载中 Spinner 组件
 */
import React from 'react';
import { clsx } from 'clsx';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  text?: string;
}

const sizeClasses = {
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-8 h-8 border-[3px]',
};

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  className,
  text,
}) => {
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <div
        className={clsx(
          'rounded-full border-gray-600 border-t-blue-400 animate-spin',
          sizeClasses[size]
        )}
      />
      {text && <span className="text-gray-400 text-sm">{text}</span>}
    </div>
  );
};

export default LoadingSpinner;
