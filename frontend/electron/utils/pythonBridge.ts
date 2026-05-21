/**
 * PythonBridge - 管理 Python FastAPI 子进程的生命周期
 * 负责启动/停止后端服务、健康检查、日志转发
 */
import { ChildProcess, spawn } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';

// ============================================================
// 类型定义
// ============================================================

interface PythonBridgeOptions {
  /** Python 脚本路径 */
  scriptPath: string;
  /** 监听端口 */
  port: number;
  /** 日志回调 */
  onLog: (msg: string) => void;
  /** 错误回调 */
  onError: (err: string) => void;
  /** 状态变化回调 */
  onStatusChange: (status: PythonStatus) => void;
}

interface PythonStatus {
  running: boolean;
  pid: number | null;
  port: number;
}

// ============================================================
// PythonBridge 实现
// ============================================================

export class PythonBridge {
  private process: ChildProcess | null = null;
  private options: PythonBridgeOptions;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private startupRetries: number = 0;
  private readonly maxStartupRetries: number = 3;
  private readonly healthCheckIntervalMs: number = 10000;
  private readonly startupTimeoutMs: number = 30000;

  constructor(options: PythonBridgeOptions) {
    this.options = options;
  }

  /**
   * 获取当前运行状态
   */
  getStatus(): PythonStatus {
    return {
      running: this.process !== null && this.process.exitCode === null,
      pid: this.process?.pid ?? null,
      port: this.options.port,
    };
  }

  /**
   * 启动 Python 子进程
   */
  async start(): Promise<void> {
    if (this.getStatus().running) {
      this.options.onLog('Python backend is already running');
      return;
    }

    if (!existsSync(this.options.scriptPath)) {
      throw new Error(`Python script not found: ${this.options.scriptPath}`);
    }

    return new Promise<void>((resolve, reject) => {
      const pythonExecutable = this.findPythonExecutable();
      const env = {
        ...process.env,
        PYTHONPATH: path.dirname(path.dirname(this.options.scriptPath)),
        PYTHONUNBUFFERED: '1',
      };

      this.options.onLog(`Starting Python backend: ${pythonExecutable} ${this.options.scriptPath}`);

      this.process = spawn(pythonExecutable, [this.options.scriptPath], {
        env,
        cwd: path.dirname(path.dirname(this.options.scriptPath)),
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let started = false;
      const startupTimeout = setTimeout(() => {
        if (!started) {
          reject(new Error(`Python backend startup timeout after ${this.startupTimeoutMs}ms`));
        }
      }, this.startupTimeoutMs);

      // 监听 stdout
      this.process.stdout?.on('data', (data: Buffer) => {
        const msg = data.toString().trim();
        this.options.onLog(msg);

        // 检测 FastAPI 启动成功的日志标志
        if (msg.includes('Application startup complete') || msg.includes('Uvicorn running on')) {
          if (!started) {
            started = true;
            clearTimeout(startupTimeout);
            this.startHealthCheck();
            this.options.onStatusChange(this.getStatus());
            resolve();
          }
        }
      });

      // 监听 stderr
      this.process.stderr?.on('data', (data: Buffer) => {
        const msg = data.toString().trim();
        // uvicorn 把部分信息输出到 stderr，区分处理
        if (msg.includes('Application startup complete') || msg.includes('Uvicorn running on')) {
          this.options.onLog(msg);
          if (!started) {
            started = true;
            clearTimeout(startupTimeout);
            this.startHealthCheck();
            this.options.onStatusChange(this.getStatus());
            resolve();
          }
        } else {
          this.options.onError(msg);
        }
      });

      // 进程退出处理
      this.process.on('exit', (code, signal) => {
        this.options.onLog(`Python backend exited: code=${code} signal=${signal}`);
        this.process = null;
        this.stopHealthCheck();
        this.options.onStatusChange(this.getStatus());

        if (!started) {
          clearTimeout(startupTimeout);
          reject(new Error(`Python backend exited unexpectedly: code=${code}`));
        }
      });

      // 进程错误处理
      this.process.on('error', (err) => {
        this.options.onError(`Process error: ${err.message}`);
        this.process = null;
        this.stopHealthCheck();
        this.options.onStatusChange(this.getStatus());

        if (!started) {
          clearTimeout(startupTimeout);
          reject(err);
        }
      });
    });
  }

  /**
   * 停止 Python 子进程
   */
  async stop(): Promise<void> {
    this.stopHealthCheck();

    if (!this.process) {
      return;
    }

    return new Promise<void>((resolve) => {
      const proc = this.process!;
      this.process = null;

      // 优雅关闭：先发 SIGTERM，超时后 SIGKILL
      const killTimeout = setTimeout(() => {
        try {
          proc.kill('SIGKILL');
        } catch (_) {
          // ignore
        }
        resolve();
      }, 5000);

      proc.on('exit', () => {
        clearTimeout(killTimeout);
        this.options.onStatusChange(this.getStatus());
        resolve();
      });

      try {
        proc.kill('SIGTERM');
      } catch (err) {
        clearTimeout(killTimeout);
        resolve();
      }
    });
  }

  /**
   * 启动健康检查定时器
   */
  private startHealthCheck(): void {
    this.stopHealthCheck();
    this.healthCheckInterval = setInterval(async () => {
      const isAlive = await this.checkHealth();
      if (!isAlive && this.getStatus().running) {
        this.options.onError('Python backend health check failed');
      }
    }, this.healthCheckIntervalMs);
  }

  /**
   * 停止健康检查定时器
   */
  private stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  /**
   * 执行健康检查 HTTP 请求
   */
  private async checkHealth(): Promise<boolean> {
    try {
      const response = await fetch(`http://localhost:${this.options.port}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      return response.ok;
    } catch (_) {
      return false;
    }
  }

  /**
   * 查找 Python 可执行路径
   * 优先使用虚拟环境中的 python
   */
  private findPythonExecutable(): string {
    const candidates = [
      // Windows 虚拟环境
      path.join(path.dirname(this.options.scriptPath), '..', 'venv', 'Scripts', 'python.exe'),
      path.join(path.dirname(this.options.scriptPath), '..', '.venv', 'Scripts', 'python.exe'),
      // 系统 Python
      'python',
      'python3',
    ];

    for (const candidate of candidates) {
      if (candidate.includes(path.sep) && existsSync(candidate)) {
        return candidate;
      }
    }

    return 'python'; // fallback
  }
}
