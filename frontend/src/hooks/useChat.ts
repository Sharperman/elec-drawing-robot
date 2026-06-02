/**
 * useChat Hook - 发送指令、SSE 流、确认执行、重新生成、反馈
 */
import { useCallback } from 'react';
import toast from 'react-hot-toast';

import apiClient from '@/services/apiClient';
import { sseClient } from '@/services/sseClient';
import { useChatStore } from '@/stores/chatStore';
import { useSessionStore } from '@/stores/sessionStore';
import type { Message, ChatConfirmRequest } from '@/types';

export function useChat() {
  const {
    getMessages,
    addMessage,
    setMessages,
    startStreaming,
    appendStreamToken,
    finishStreaming,
    setLoading,
    setError,
    removeLastAssistantMessage,
    isLoading,
    isStreaming,
    streamingMessage,
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

    // 开始 SSE 流式对话
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
    });
  }, [
    currentSessionId, isLoading, isStreaming,
    addMessage, startStreaming, appendStreamToken,
    finishStreaming, setError,
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

    // 删除最后一条 AI 消息
    removeLastAssistantMessage(currentSessionId);

    // 找到最后一条用户消息
    const msgs = getMessages(currentSessionId);
    const lastUserMsg = [...msgs].reverse().find(m => m.role === 'user');
    if (lastUserMsg) {
      // 用相同的用户消息重新发送
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
      await apiClient.post('/api/chat/feedback', {
        session_id: currentSessionId,
        message_id: messageId,
        feedback_type: type,
      });
      toast.success(type === 'positive' ? '感谢反馈 👍' : '已记录，我们会改进');
    } catch {
      // 静默处理（feedback 接口可能尚未实现）
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
      } else {
        toast('操作已取消', { icon: '🚫' });
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
    isLoading,
    isStreaming,
    error,
    sendMessage,
    stopStreaming,
    regenerateMessage,
    sendFeedback,
    confirmPlan,
    loadHistory,
  };
}
