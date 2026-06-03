/**
 * SSE 流式响应客户端
 * 管理 EventSource 生命周期，处理结构化 Agent 事件
 */
import { BASE_URL } from './apiClient';
import type { SSEEvent } from '@/types';

type TokenCallback = (token: string) => void;
type DoneCallback = (fullText: string) => void;
type ErrorCallback = (error: string) => void;

/** 新增：结构化事件回调 */
type ThinkingCallback = (content: string) => void;
type ToolStartCallback = (toolName: string, toolInput: string) => void;
type ToolEndCallback = (toolName: string, toolOutput: string) => void;
/** 审查报告回调 */
type ReportCallback = (reportPath: string) => void;
/** 确认请求回调 */
type ConfirmRequiredCallback = (plan: { summary: string; operations: Array<{ tool: string; description: string; params?: Record<string, unknown> }> }) => void;
/** 自动校验回调 */
type AutoReviewCallback = (result: { summary: string; issues: Array<{ severity: string; title: string; description: string; rule_id?: string }>; pass_count: number; total_checks: number; drawing_name?: string }) => void;

interface SSEClientOptions {
  onToken: TokenCallback;
  onDone: DoneCallback;
  onError: ErrorCallback;
  /** 新增回调 */
  onThinking?: ThinkingCallback;
  onToolStart?: ToolStartCallback;
  onToolEnd?: ToolEndCallback;
  onReport?: ReportCallback;
  onConfirmRequired?: ConfirmRequiredCallback;
  onAutoReview?: AutoReviewCallback;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private abortController: AbortController | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelayMs: number = 2000;
  private lastConnectParams: {
    sessionId: string;
    message: string;
    options: SSEClientOptions;
    mode: string;
  } | null = null;

  /**
   * 开始 SSE 流式对话
   */
  connect(
    sessionId: string,
    message: string,
    options: SSEClientOptions,
    mode: string = 'auto',
  ): void {
    // 保存连接参数，用于重连
    this.lastConnectParams = { sessionId, message, options, mode };

    this.disconnect();

    const params = new URLSearchParams({
      session_id: sessionId,
      message,
      mode,
    });

    const url = `${BASE_URL}/api/chat/stream?${params.toString()}`;

    try {
      this.eventSource = new EventSource(url);

      this.eventSource.onmessage = (event: MessageEvent<string>) => {
        try {
          const evt: SSEEvent = JSON.parse(event.data);

          switch (evt.type) {
            case 'thinking':
              options.onThinking?.(evt.content ?? '');
              break;

            case 'tool_start':
              options.onToolStart?.(evt.tool_name ?? '', evt.tool_input ?? '');
              break;

            case 'tool_end':
              options.onToolEnd?.(evt.tool_name ?? '', evt.tool_output ?? '');
              break;

            case 'text':
              options.onToken(evt.content ?? '');
              break;

            case 'done':
              this.reconnectAttempts = 0; // 成功完成，重置重连计数
              options.onDone('');
              this.disconnect();
              break;

            case 'error':
              options.onError(evt.content ?? '');
              this.disconnect();
              break;

                case 'report':
                  options.onReport?.(evt.path ?? '');
                  break;
                case 'confirm_required':
                  if (evt.plan) {
                    options.onConfirmRequired?.(evt.plan);
                  }
                  break;
                case 'auto_review':
                  if (evt.result) {
                    options.onAutoReview?.(evt.result);
                  }
                  break;

            case 'confirm_required':
              if (evt.plan) {
                options.onConfirmRequired?.(evt.plan);
              }
              break;

            case 'auto_review':
              if (evt.result) {
                options.onAutoReview?.(evt.result);
              }
              break;

            default:
              // 兼容旧协议：type 缺失时当做 token
              {
                const legacy = evt as unknown as { token?: string; done?: boolean; full?: string };
                if (legacy.token) {
                  options.onToken(legacy.token);
                }
                if (legacy.done) {
                  options.onDone(legacy.full ?? '');
                  this.disconnect();
                }
              }
          }
        } catch (_parseErr) {
          // 忽略非 JSON 数据
        }
      };

      this.eventSource.onerror = (_event: Event) => {
        const es = this.eventSource;
        if (es && es.readyState === EventSource.CLOSED) {
          // 正常关闭，不重连
          return;
        }
        // 尝试重连
        this.tryReconnect();
      };

    } catch (err) {
      options.onError(`无法建立 SSE 连接: ${String(err)}`);
    }
  }

  /**
   * 使用 fetch + ReadableStream 进行流式请求（备用方案）
   */
  async connectWithFetch(
    _sessionId: string,
    _message: string,
    _imageData: string | undefined,
    options: SSEClientOptions
  ): Promise<void> {
    this.abortController = new AbortController();

    try {
      const response = await fetch(`${BASE_URL}/api/chat/stream`, {
        method: 'GET',
        signal: this.abortController.signal,
        headers: { 'Accept': 'text/event-stream' },
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const evt: SSEEvent = JSON.parse(data);
              switch (evt.type) {
                case 'thinking':
                  options.onThinking?.(evt.content ?? '');
                  break;
                case 'tool_start':
                  options.onToolStart?.(evt.tool_name ?? '', evt.tool_input ?? '');
                  break;
                case 'tool_end':
                  options.onToolEnd?.(evt.tool_name ?? '', evt.tool_output ?? '');
                  break;
                case 'text':
                  fullText += (evt.content ?? '');
                  options.onToken(evt.content ?? '');
                  break;
                case 'done':
                  options.onDone(fullText);
                  return;
                case 'error':
                  options.onError(evt.content ?? '');
                  return;
              }
            } catch (_) {
              // 忽略
            }
          }
        }
      }

      options.onDone(fullText);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        options.onError(String(err));
      }
    }
  }

  /**
   * 断开 SSE 连接
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.lastConnectParams = null;
    this.reconnectAttempts = 0;

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * 尝试重新连接（指数退避）
   */
  private tryReconnect(): void {
    if (!this.lastConnectParams) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.lastConnectParams.options.onError(
        `SSE 连接中断，已重试 ${this.maxReconnectAttempts} 次，请刷新页面重试`
      );
      return;
    }

    this.reconnectAttempts += 1;
    const delay = this.reconnectDelayMs * Math.pow(1.5, this.reconnectAttempts - 1);
    const { sessionId, message, options, mode } = this.lastConnectParams;

    options.onError(`连接中断，${Math.round(delay / 1000)}秒后自动重连（${this.reconnectAttempts}/${this.maxReconnectAttempts}）`);

    this.reconnectTimer = setTimeout(() => {
      if (!this.lastConnectParams) return;
      // 用 fetch 方案重连（EventSource 不支持自定义 header，但 GET 足够）
      this.connect(sessionId, message, options, mode);
    }, delay);
  }

  get isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }
}

// 全局单例
export const sseClient = new SSEClient();
