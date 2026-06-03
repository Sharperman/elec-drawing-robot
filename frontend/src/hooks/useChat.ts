/**
 * useChat Hook - 发送指令、SSE 流、确认执行、重新生成、反馈
 * 支持新的结构化 Agent 步骤事件
 */
import { useCallback, useRef, useState } from 'react';
import toast from 'react-hot-toast';

import apiClient from '@/services/apiClient';
import { sseClient } from '@/services/sseClient';
import { useChatStore } from '@/stores/chatStore';
import { useSessionStore } from '@/stores/sessionStore';
import type { Message, ChatConfirmRequest, RunMode } from '@/types';

/** 确认计划数据结构 */
export interface PendingConfirmPlan {
  summary: string;
  operations: Array<{
    tool: string;
    description: string;
    params?: Record<string, unknown>;
  }>;
}

/** 最后发送的消息参数（用于确认后重发） */
interface LastSendParams {
  message: string;
  imageData?: string;
  mode: RunMode;
}

export function useChat() {
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirmPlan | null>(null);
  const lastSendParamsRef = useRef<LastSendParams | null>(null);
  const {
    getMessages,
    addMessage,
    setMessages,
    startStreaming,
    appendStreamToken,
    finishStreaming,
    addThinkingStep,
    addToolStartStep,
    updateToolEndStep,
    setLoading,
    setError,
    removeLastAssistantMessage,
    isLoading,
    isStreaming,
    streamingMessage,
    agentSteps,
    reportPath,
    setReportPath,
    error,
  } = useChatStore();

  const { currentSessionId } = useSessionStore();

  // ── 加载历史 ──
  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const resp = await apiClient.get<{ data: Message[] }>(
        `/api/chat/sessions/${sessionId}/messages`
      );
      if (resp.data.data) {
        setMessages(sessionId, resp.data.data);
      }
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  }, [setMessages]);

  // ── 发送消息（流式） ──
  const sendMessage = useCallback(async (
    message: string,
    imageData?: string,
    mode: RunMode = 'auto',
  ) => {
    if (!currentSessionId) {
      toast.error('请先选择或创建一个会话');
      return;
    }

    if (isLoading || isStreaming) {
      toast.error('正在处理上一条消息，请稍候');
      return;
    }

    // 乐观更新：立即添加用户消息
    const userMsg: Message = {
      id: Date.now(),
      session_id: currentSessionId,
      role: 'user',
      content: message,
      image_data: imageData,
      is_streaming: false,
      created_at: new Date().toISOString(),
    };
    addMessage(currentSessionId, userMsg);
    startStreaming(currentSessionId);
    setPendingConfirm(null);

    // 保存发送参数，用于确认后重发
    lastSendParamsRef.current = { message, imageData, mode };

    // 开始 SSE 流式对话（新协议）
    sseClient.connect(currentSessionId, message, {
      onToken: (token) => {
        appendStreamToken(token);
      },
      onDone: (fullText) => {
        finishStreaming(fullText);
      },
      onError: (err) => {
        setError(err);
        toast.error(`AI 响应失败: ${err.slice(0, 100)}`);
      },
      // 新回调：Agent 步骤
      onThinking: (content) => {
        addThinkingStep(content);
      },
      onToolStart: (toolName, toolInput) => {
        addToolStartStep(toolName, toolInput);
      },
      onToolEnd: (toolName, toolOutput) => {
        updateToolEndStep(toolName, toolOutput);
      },
      // 审查报告回调
      onReport: (reportPathFromServer) => {
        setReportPath(reportPathFromServer);
        toast.success('📋 图纸审查报告已生成');
      },
      onConfirmRequired: (plan) => {
        setPendingConfirm(plan);
      },
      onAutoReview: (result) => {
        // 自动校验结果通过 toast 提示
        if (result.issues.length === 0) {
          toast.success(`✅ 规范校验通过 (${result.pass_count}/${result.total_checks})`);
        } else {
          const errorCount = result.issues.filter(i => i.severity === 'error').length;
          const warnCount = result.issues.filter(i => i.severity === 'warning').length;
          if (errorCount > 0) {
            toast.error(`⚠️ 发现 ${errorCount} 项不合规、${warnCount} 项建议改进`);
          } else {
            toast(`💡 ${result.summary}`, { icon: '⚠️' });
          }
          // 追加系统消息展示校验结果
          const issuesText = result.issues.map(i =>
            `- **${i.severity === 'error' ? '🔴' : i.severity === 'warning' ? '🟡' : '🔵'} ${i.title}**: ${i.description}${i.rule_id ? ` (${i.rule_id})` : ''}`
          ).join('\n');
          addMessage(currentSessionId!, {
            id: Date.now(),
            session_id: currentSessionId!,
            role: 'system',
            content: `📋 **自动规范校验结果**\n\n${result.summary}\n\n${issuesText}\n\n通过: ${result.pass_count}/${result.total_checks}`,
            is_streaming: false,
            created_at: new Date().toISOString(),
          });
        }
      },
    }, mode);
  }, [
    currentSessionId, isLoading, isStreaming,
    addMessage, startStreaming, appendStreamToken,
    finishStreaming, setError,
    addThinkingStep, addToolStartStep, updateToolEndStep,
    setReportPath,
  ]);

  // ── 停止流式 ──
  const stopStreaming = useCallback(() => {
    sseClient.disconnect();
    const current = streamingMessage?.content ?? '';
    finishStreaming(current);
  }, [streamingMessage, finishStreaming]);

  // ── 重新生成 ──
  const regenerateMessage = useCallback((_aiMessage: Message) => {
    if (!currentSessionId) return;

    removeLastAssistantMessage(currentSessionId);

    const msgs = getMessages(currentSessionId);
    const lastUserMsg = [...msgs].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      sendMessage(lastUserMsg.content, lastUserMsg.image_data);
    }
  }, [currentSessionId, removeLastAssistantMessage, getMessages, sendMessage]);

  // ── 反馈 ──
  const sendFeedback = useCallback(async (
    messageId: number,
    type: 'positive' | 'negative',
  ) => {
    if (!currentSessionId) return;

    try {
      await apiClient.post('/api/feedback', {
        session_id: currentSessionId,
        message_id: messageId,
        feedback_type: type,
      });
      toast.success(type === 'positive' ? '感谢反馈 👍' : '已记录，我们会改进');
    } catch {
      // 静默处理
    }
  }, [currentSessionId]);

  // ── 确认执行计划 ──
  const confirmPlan = useCallback(async (confirm: boolean) => {
    if (!currentSessionId) return;

    try {
      setLoading(true);
      const body: ChatConfirmRequest = {
        session_id: currentSessionId,
        confirm,
      };
      await apiClient.post('/api/chat/confirm', body);

      if (confirm) {
        toast.success('操作计划已确认执行');
        // 清除确认状态
        setPendingConfirm(null);
        // 重新发送消息（后端会识别已确认并直接执行工具）
        const params = lastSendParamsRef.current;
        if (params) {
          // 用 draw_confirmed 模式重发，让后端跳过确认环节
          sendMessage(params.message, params.imageData, 'draw' as RunMode);
        }
      } else {
        toast('操作已取消', { icon: '🚫' });
        setPendingConfirm(null);
      }
    } catch (err) {
      toast.error('确认操作失败');
    } finally {
      setLoading(false);
    }
  }, [currentSessionId, setLoading]);

  return {
    messages: currentSessionId ? getMessages(currentSessionId) : [],
    streamingMessage,
    agentSteps,
    reportPath,
    isLoading,
    isStreaming,
    error,
    pendingConfirm,
    sendMessage,
    stopStreaming,
    regenerateMessage,
    sendFeedback,
    confirmPlan,
    loadHistory,
    setReportPath,
  };
}
