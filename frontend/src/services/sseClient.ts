/**
 * SSE 流式响应客户端
 * 管理 EventSource 生命周期，处理 token 流
 */
import { BASE_URL } from './apiClient';
import type { SSEChunk } from '@/types';

type TokenCallback = (token: string) => void;
type DoneCallback = (fullText: string) => void;
type ErrorCallback = (error: string) => void;

interface SSEClientOptions {
  onToken: TokenCallback;
  onDone: DoneCallback;
  onError: ErrorCallback;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private abortController: AbortController | null = null;

  /**
   * 开始 SSE 流式对话
   *
   * @param sessionId 会话 ID
   * @param message 用户消息
   * @param options 回调函数集合
   */
  connect(
    sessionId: string,
    message: string,
    options: SSEClientOptions
  ): void {
    // 断开已有连接
    this.disconnect();

    const params = new URLSearchParams({
      session_id: sessionId,
      message,
    });

    const url = `${BASE_URL}/api/chat/stream?${params.toString()}`;

    try {
      this.eventSource = new EventSource(url);

      this.eventSource.onmessage = (event: MessageEvent<string>) => {
        try {
          const chunk: SSEChunk = JSON.parse(event.data);

          if (chunk.error) {
            options.onError(chunk.error);
            this.disconnect();
            return;
          }

          if (chunk.done) {
            options.onDone(chunk.full ?? '');
            this.disconnect();
          } else if (chunk.token) {
            options.onToken(chunk.token);
          }
        } catch (parseErr) {
          // 忽略非 JSON 数据（如注释行）
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
   * 适合 POST 请求携带 body 的场景
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
              const chunk: SSEChunk = JSON.parse(data);
              if (chunk.done) {
                options.onDone(chunk.full ?? fullText);
                return;
              } else if (chunk.token) {
                fullText += chunk.token;
                options.onToken(chunk.token);
              }
            } catch (_) {
              // 忽略解析错误
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

  /**
   * 检查是否正在连接
   */
  get isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }
}

// 全局单例
export const sseClient = new SSEClient();
