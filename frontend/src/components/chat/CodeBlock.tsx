/**
 * CodeBlock.tsx
 * 代码块：语言标签 + 一键复制 + 视觉升级
 */
import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

interface CodeBlockProps {
  language: string;
  code: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-2 rounded-lg overflow-hidden border border-gray-700/50 shadow-lg">
      {/* 顶部栏 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700/30">
        <span className="text-[11px] font-medium text-blue-400 uppercase tracking-wider">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-xs
                     text-gray-400 hover:text-gray-200 hover:bg-gray-700/50
                     transition-all active:scale-95"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-green-400" />
              <span className="text-green-400">已复制</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>复制</span>
            </>
          )}
        </button>
      </div>

      {/* 代码区 */}
      <pre className="bg-gray-950 p-3 overflow-x-auto m-0 text-sm leading-relaxed">
        <code className={`language-${language} text-gray-300 font-mono`}>
          {code}
        </code>
      </pre>
    </div>
  );
};

export default CodeBlock;
