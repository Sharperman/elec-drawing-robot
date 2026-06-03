/**
 * Chat Store - 管理对话消息列表、流式状态、Agent 步骤
 */
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { Message, AgentStep } from '@/types';

interface StreamingMessage {
  content: string;
  sessionId: string;
}

interface ChatState {
  messages: Record<string, Message[]>;
  streamingMessage: StreamingMessage | null;
  /** Agent 执行步骤（流式时实时更新） */
  agentSteps: AgentStep[];
  isLoading: boolean;
  isStreaming: boolean;
  pendingPlan: string | null;
  error: string | null;
  /** 审查报告路径 */
  reportPath: string | null;
}

interface ChatActions {
  getMessages: (sessionId: string) => Message[];
  addMessage: (sessionId: string, message: Message) => void;
  setMessages: (sessionId: string, messages: Message[]) => void;
  startStreaming: (sessionId: string) => void;
  appendStreamToken: (token: string) => void;
  finishStreaming: (fullContent: string) => void;
  /** Agent 步骤操作 */
  addThinkingStep: (content: string) => void;
  addToolStartStep: (toolName: string, toolInput: string) => void;
  updateToolEndStep: (toolName: string, toolOutput: string) => void;
  clearAgentSteps: () => void;
  setLoading: (loading: boolean) => void;
  setPendingPlan: (plan: string | null) => void;
  setError: (error: string | null) => void;
  /** 审查报告 */
  setReportPath: (path: string | null) => void;
  clearMessages: (sessionId: string) => void;
  removeLastAssistantMessage: (sessionId: string) => Message | null;
  reset: () => void;
}

let stepIdCounter = 0;
function nextStepId(): string {
  stepIdCounter += 1;
  return `step-${stepIdCounter}-${Date.now()}`;
}

const initialState: ChatState = {
  messages: {},
  streamingMessage: null,
  agentSteps: [],
  isLoading: false,
  isStreaming: false,
  pendingPlan: null,
  error: null,
  reportPath: null,
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
        state.agentSteps = [];
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
        // 不清除 agentSteps，让历史消息可以展示
      });
    },

    addThinkingStep: (content: string) => {
      set((state) => {
        state.agentSteps.push({
          id: nextStepId(),
          type: 'thinking',
          status: 'running',
          thinkingContent: content,
        });
      });
    },

    addToolStartStep: (toolName: string, toolInput: string) => {
      set((state) => {
        // 标记上一个 thinking 步骤为 done
        const lastThinking = [...state.agentSteps].reverse().find(s => s.type === 'thinking' && s.status === 'running');
        if (lastThinking) {
          lastThinking.status = 'done';
        }
        state.agentSteps.push({
          id: nextStepId(),
          type: 'tool_call',
          status: 'running',
          toolName,
          toolInput,
        });
      });
    },

    updateToolEndStep: (toolName: string, toolOutput: string) => {
      set((state) => {
        // 找到最后一个 running 状态的 tool_call
        const steps = state.agentSteps;
        for (let i = steps.length - 1; i >= 0; i--) {
          if (steps[i].type === 'tool_call' && steps[i].status === 'running' && steps[i].toolName === toolName) {
            steps[i].toolOutput = toolOutput;
            steps[i].status = 'done';
            break;
          }
        }
      });
    },

    clearAgentSteps: () => {
      set((state) => {
        state.agentSteps = [];
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

    setReportPath: (path: string | null) => {
      set((state) => {
        state.reportPath = path;
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
