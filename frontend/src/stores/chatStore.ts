/**
 * Chat Store - 管理对话消息列表、流式状态、pending 命令
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { Message } from '@/types';

interface StreamingMessage {
  content: string;
  sessionId: string;
}

interface ChatState {
  // 消息列表（session_id → messages）
  messages: Record<string, Message[]>;
  // 当前流式输出中的消息
  streamingMessage: StreamingMessage | null;
  // 是否正在等待 AI 响应
  isLoading: boolean;
  // 是否正在流式输出
  isStreaming: boolean;
  // 待确认的操作计划
  pendingPlan: string | null;
  // 错误信息
  error: string | null;
}

interface ChatActions {
  // 获取指定会话的消息
  getMessages: (sessionId: string) => Message[];
  // 添加消息
  addMessage: (sessionId: string, message: Message) => void;
  // 批量设置消息（从服务端加载历史）
  setMessages: (sessionId: string, messages: Message[]) => void;
  // 开始流式输出
  startStreaming: (sessionId: string) => void;
  // 追加流式 token
  appendStreamToken: (token: string) => void;
  // 完成流式输出
  finishStreaming: (fullContent: string) => void;
  // 设置加载状态
  setLoading: (loading: boolean) => void;
  // 设置待确认计划
  setPendingPlan: (plan: string | null) => void;
  // 设置错误
  setError: (error: string | null) => void;
  // 清空指定会话消息
  clearMessages: (sessionId: string) => void;
  // 清除所有状态
  reset: () => void;
}

const initialState: ChatState = {
  messages: {},
  streamingMessage: null,
  isLoading: false,
  isStreaming: false,
  pendingPlan: null,
  error: null,
};

export const useChatStore = create<ChatState & ChatActions>()(
  immer((set, get) => ({
    ...initialState,

    getMessages: (sessionId: string) => {
      return get().messages[sessionId] ?? [];
    },

    addMessage: (sessionId: string, message: Message) => {
      set((state) => {
        if (!state.messages[sessionId]) {
          state.messages[sessionId] = [];
        }
        state.messages[sessionId].push(message);
      });
    },

    setMessages: (sessionId: string, messages: Message[]) => {
      set((state) => {
        state.messages[sessionId] = messages;
      });
    },

    startStreaming: (sessionId: string) => {
      set((state) => {
        state.isStreaming = true;
        state.isLoading = true;
        state.streamingMessage = { content: '', sessionId };
        state.error = null;
      });
    },

    appendStreamToken: (token: string) => {
      set((state) => {
        if (state.streamingMessage) {
          state.streamingMessage.content += token;
        }
      });
    },

    finishStreaming: (fullContent: string) => {
      set((state) => {
        state.isStreaming = false;
        state.isLoading = false;
        // 将流式消息作为完整消息添加到列表
        if (state.streamingMessage) {
          const { sessionId } = state.streamingMessage;
          if (!state.messages[sessionId]) {
            state.messages[sessionId] = [];
          }
          const newMessage: Message = {
            id: Date.now(), // 临时 ID
            session_id: sessionId,
            role: 'assistant',
            content: fullContent || state.streamingMessage.content,
            is_streaming: false,
            created_at: new Date().toISOString(),
          };
          state.messages[sessionId].push(newMessage);
        }
        state.streamingMessage = null;
      });
    },

    setLoading: (loading: boolean) => {
      set((state) => {
        state.isLoading = loading;
      });
    },

    setPendingPlan: (plan: string | null) => {
      set((state) => {
        state.pendingPlan = plan;
      });
    },

    setError: (error: string | null) => {
      set((state) => {
        state.error = error;
        state.isLoading = false;
        state.isStreaming = false;
        state.streamingMessage = null;
      });
    },

    clearMessages: (sessionId: string) => {
      set((state) => {
        state.messages[sessionId] = [];
      });
    },

    reset: () => {
      set(initialState);
    },
  }))
);
