/**
 * StreamingSteps.tsx
 * 流式 Agent 步骤指示器 — 展示模型思考、调用工具、分析结果的完整过程
 *
 * 以时间线形式展示：
 * 1. 💭 思考中...（动画脉冲）
 * 2. 🔧 调用工具: XXX（工具名 + 输入参数）
 * 3. ✅ 工具完成: XXX（输出摘要）
 * 4. 📝 逐字生成的回复文本
 */
import React, { useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { Brain, Wrench, CheckCircle, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import type { AgentStep } from '@/types';

interface StreamingStepsProps {
  steps: AgentStep[];
  streamingText: string;
  isStreaming: boolean;
}

const STEP_ICONS: Record<AgentStep['type'], React.FC<{ className?: string }>> = {
  thinking: Brain,
  tool_call: Wrench,
  text: CheckCircle,
};

const STEP_LABELS: Record<AgentStep['type'], string> = {
  thinking: '思考中',
  tool_call: '调用工具',
  text: '回复中',
};

const StreamingSteps: React.FC<StreamingStepsProps> = ({ steps, streamingText, isStreaming }) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expandedTools, setExpandedTools] = React.useState<Record<string, boolean>>({});

  // 自动滚动到底部
  useEffect(() => {
    if (isStreaming) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [steps, streamingText, isStreaming]);

  const toggleTool = (stepId: string) => {
    setExpandedTools(prev => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  if (!isStreaming && steps.length === 0) return null;

  return (
    <div className="streaming-steps w-full max-w-[80%] ml-[46px]">
      {/* 步骤时间线 */}
      {steps.length > 0 && (
        <div className="steps-timeline space-y-0.5 mb-3">
          {steps.map((step, idx) => {
            const isLast = idx === steps.length - 1;
            const isRunning = step.status === 'running';
            const Icon = STEP_ICONS[step.type];

            return (
              <div key={step.id} className="step-row">
                {/* 时间线连接线 */}
                <div className="flex items-start gap-2.5">
                  <div className="step-indicator flex-shrink-0 flex flex-col items-center">
                    <div className={clsx(
                      'step-dot w-6 h-6 rounded-full flex items-center justify-center',
                      'transition-all duration-300',
                      step.type === 'thinking' && 'bg-amber-500/20 text-amber-400',
                      step.type === 'tool_call' && 'bg-blue-500/20 text-blue-400',
                      step.type === 'text' && 'bg-green-500/20 text-green-400',
                      isRunning && 'animate-pulse',
                    )}>
                      {isRunning ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Icon className="w-3.5 h-3.5" />
                      )}
                    </div>
                    {!isLast && (
                      <div className="step-line w-px flex-1 min-h-[12px] my-0.5 bg-gray-700/50" />
                    )}
                  </div>

                  {/* 步骤内容 */}
                  <div className="flex-1 min-w-0 pb-1">
                    <div className={clsx(
                      'step-card rounded-lg px-3 py-2',
                      'bg-gray-800/60 border border-gray-700/40',
                      'transition-all duration-300',
                      isRunning && 'border-l-2 border-l-blue-500',
                      !isRunning && 'opacity-75',
                    )}>
                      {/* 步骤标题行 */}
                      <div className="flex items-center gap-2 text-xs">
                        <span className={clsx(
                          'font-medium',
                          step.type === 'thinking' && 'text-amber-400',
                          step.type === 'tool_call' && 'text-blue-400',
                          step.type === 'text' && 'text-green-400',
                        )}>
                          {STEP_LABELS[step.type]}
                        </span>
                        {step.toolName && (
                          <span className="text-gray-300 font-mono text-[11px] truncate">
                            {step.toolName}
                          </span>
                        )}
                        {isRunning && (
                          <span className="ml-auto flex items-center gap-1 text-gray-500">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                            <span className="text-[10px]">执行中</span>
                          </span>
                        )}
                      </div>

                      {/* 思考内容 */}
                      {step.type === 'thinking' && step.thinkingContent && (
                        <p className="mt-1 text-xs text-gray-400 italic">
                          {step.thinkingContent}
                        </p>
                      )}

                      {/* 工具调用详情 */}
                      {step.type === 'tool_call' && (
                        <div className="mt-1.5">
                          {/* 输入参数 */}
                          {step.toolInput && (
                            <div
                              className="cursor-pointer"
                              onClick={() => toggleTool(step.id)}
                            >
                              <div className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors">
                                {expandedTools[step.id] ? (
                                  <ChevronUp className="w-3 h-3" />
                                ) : (
                                  <ChevronDown className="w-3 h-3" />
                                )}
                                <span>输入参数</span>
                              </div>
                              {expandedTools[step.id] && (
                                <pre className="mt-1 text-[10px] text-gray-400 bg-gray-900/60 rounded p-1.5 max-h-24 overflow-y-auto font-mono whitespace-pre-wrap break-all">
                                  {step.toolInput.length > 300
                                    ? step.toolInput.slice(0, 300) + '...'
                                    : step.toolInput}
                                </pre>
                              )}
                            </div>
                          )}

                          {/* 输出结果 */}
                          {step.toolOutput && (
                            <div className="mt-1 flex items-start gap-1.5 text-[10px]">
                              <span className="text-green-500 mt-0.5">→</span>
                              <span className="text-gray-300 truncate max-w-[300px]">
                                {step.toolOutput.length > 100
                                  ? step.toolOutput.slice(0, 100) + '...'
                                  : step.toolOutput}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 流式文本 */}
      {streamingText && (
        <div className="streaming-text-card rounded-lg px-4 py-2.5 bg-gray-800/40 border border-gray-700/30 mb-2">
          <div className="text-sm text-gray-200 whitespace-pre-wrap streaming-cursor">
            {streamingText}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

export default React.memo(StreamingSteps);
