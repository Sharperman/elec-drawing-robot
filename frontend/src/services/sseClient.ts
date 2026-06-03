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

interface SSEClientOptions {
  onToken: TokenCallback;
  onDone: DoneCallback;
  onError: ErrorCallback;
  /** 新增回调 */
  onThinking?: ThinkingCallback;
  onToolStart?: ToolStartCallback;
  onToolEnd?: ToolEndCallback;
  onReport?: ReportCallback;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private abortController: AbortController | null = null;

  /**
   * 开始 SSE 流式对话
   */
  connect(
    sessionId: string,
    message: string,
    options: SSEClientOptions,
    mode: string = 'auto',
  ): void {
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
        options.onError('SSE 连接中断');
        this.disconnect();
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
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  get isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }
}

// 全局单例
export const sseClient = new SSEClient();
