/**
 * Chat Store - 管理对话消息列表、流式状态、反馈
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { Message } from '@/types';

interface StreamingMessage {
  content: string;
  sessionId: string;
}

interface ChatState {
  messages: Record<string, Message[]>;
  streamingMessage: StreamingMessage | null;
  isLoading: boolean;
  isStreaming: boolean;
  pendingPlan: string | null;
  error: string | null;
}

interface ChatActions {
  getMessages: (sessionId: string) => Message[];
  addMessage: (sessionId: string, message: Message) => void;
  setMessages: (sessionId: string, messages: Message[]) => void;
  startStreaming: (sessionId: string) => void;
  appendStreamToken: (token: string) => void;
  finishStreaming: (fullContent: string) => void;
  setLoading: (loading: boolean) => void;
  setPendingPlan: (plan: string | null) => void;
  setError: (error: string | null) => void;
  clearMessages: (sessionId: string) => void;
  /** 删除最后一条 assistant 消息（用于重新生成） */
  removeLastAssistantMessage: (sessionId: string) => Message | null;
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
        if (state.streamingMessage) {
          const { sessionId } = state.streamingMessage;
          if (!state.messages[sessionId]) {
            state.messages[sessionId] = [];
          }
          const newMessage: Message = {
            id: Date.now(),
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

    removeLastAssistantMessage: (sessionId: string): Message | null => {
      let removedMsg: Message | null = null;
      set((state) => {
        const msgs = state.messages[sessionId];
        if (msgs && msgs.length > 0) {
          // 从后向前找最后一条 assistant 消息
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === 'assistant') {
              removedMsg = { ...msgs[i] };
              msgs.splice(i, 1);
              break;
            }
          }
        }
      });
      return removedMsg;
    },

    reset: () => {
      set(initialState);
    },
  }))
);
