/**
 * useChat Hook - 发送指令、接收 SSE 流、确认执行
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
    isLoading,
    isStreaming,
    streamingMessage,
    error,
  } = useChatStore();

  const { currentSessionId } = useSessionStore();

  /**
   * 加载会话历史消息
   */
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

  /**
   * 发送消息（流式）
   *
   * @param message 用户消息文本
   * @param imageData 可选图片 base64
   */
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

  /**
   * 停止流式输出
   */
  const stopStreaming = useCallback(() => {
    sseClient.disconnect();
    const current = streamingMessage?.content ?? '';
    finishStreaming(current);
  }, [streamingMessage, finishStreaming]);

  /**
   * 确认执行 Agent 计划
   */
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
    confirmPlan,
    loadHistory,
  };
}
