/**
 * LearnPage.tsx
 * /learn 学习模式：上传参考图纸 → 多尺度截图 → ezdxf + 视觉LLM → DrawingPattern
 *
 * 功能：
 * 1. 文件上传（DWG / DXF / PDF）
 * 2. 学习进度展示（阶段时间线）
 * 3. 对话式交互（SSE 流式，含截图+问答）
 * 4. 已学习模式列表（查看 / 确认 / 删除 / 应用）
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  DocumentArrowUpIcon, ArrowPathIcon, XCircleIcon,
  CheckCircleIcon, ExclamationTriangleIcon,
  TrashIcon, PlayIcon, ArrowDownTrayIcon, MagnifyingGlassIcon,
  QuestionMarkCircleIcon, PhotoIcon,
  Cog6ToothIcon, BookmarkIcon,
} from '@heroicons/react/24/outline';
import apiClient from '@/services/apiClient';
import type {
  DrawingPattern, LearnStep, LearnSSEEvent,
} from '@/types';

// ─── 步骤图标映射 ──────────────────────────────────────────

const stepIcons: Record<string, React.ReactNode> = {
  upload:    <DocumentArrowUpIcon className="w-4 h-4" />,
  zoom:      <MagnifyingGlassIcon className="w-4 h-4" />,
  capture:   <PhotoIcon className="w-4 h-4" />,
  analyze:   <Cog6ToothIcon className="w-4 h-4" />,
  extract:   <ArrowDownTrayIcon className="w-4 h-4" />,
  pattern:   <BookmarkIcon className="w-4 h-4" />,
  question:  <QuestionMarkCircleIcon className="w-4 h-4" />,
  done:      <CheckCircleIcon className="w-4 h-4" />,
};

const stepLabels: Record<string, string> = {
  upload:   '上传图纸',
  zoom:     '多尺度缩放',
  capture:  '截图分析',
  analyze:  '视觉识别',
  extract:  '结构提取',
  pattern:  '生成模式',
  question: '交互确认',
  done:     '完成学习',
};

// ─── 消息角色 ──────────────────────────────────────────────

interface LearnMessage {
  id: string;
  role: 'system' | 'assistant' | 'user';
  content: string;
  screenshot_b64?: string;
  question_id?: string;
  timestamp: number;
}

// ─── 主组件 ────────────────────────────────────────────────

const LearnPage: React.FC = () => {
  const sessionId = 'learn-session'; // 固定 session ID，用于关联 LearnAgent 实例

  // 状态
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [learning, setLearning] = useState(false);
  const [steps, setSteps] = useState<LearnStep[]>([]);
  const [messages, setMessages] = useState<LearnMessage[]>([]);
  const [patterns, setPatterns] = useState<DrawingPattern[]>([]);
  const [selectedPattern, setSelectedPattern] = useState<DrawingPattern | null>(null);
  const [patternsLoading, setPatternsLoading] = useState(true);
  const [questionText, setQuestionText] = useState('');
  const [showQuestion, setShowQuestion] = useState(false);
  const [error, setError] = useState('');
  const fileIdRef = useRef('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ─── 加载已学模式 ───────────────────────────────────────
  const fetchPatterns = useCallback(async () => {
    setPatternsLoading(true);
    try {
      const res = await apiClient.get('/api/learn/patterns');
      if (res.data?.code === 0) setPatterns(res.data.data ?? []);
    } catch { /* ignore */ }
    finally { setPatternsLoading(false); }
  }, []);

  useEffect(() => { fetchPatterns(); }, [fetchPatterns]);

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ─── 文件上传 ──────────────────────────────────────────

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await apiClient.post('/api/learn/upload', formData);
      if (res.data?.code === 0) {
        // 后端返回 { file_id, file_path, file_name, size }
        const fid = res.data.data?.file_id ?? res.data.data?.file_path ?? '';
        fileIdRef.current = fid;
        setSteps([{ phase: 'upload', status: 'done', message: `已上传: ${file.name}` }]);
        startLearning(fid);
      } else {
        setError(res.data?.message || '上传失败');
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '上传失败');
    } finally {
      setUploading(false);
    }
  };

  // ─── 开始学习（SSE 流式） ──────────────────────────────

  const startLearning = async (fileId: string) => {
    setLearning(true);
    setMessages([]);
    setShowQuestion(false);
    setError('');

    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      const sseUrl = `/api/learn/stream?file_id=${encodeURIComponent(fileId)}&session_id=${sessionId}`;

      const response = await fetch(sseUrl, {
        headers: { Accept: 'text/event-stream' },
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: LearnSSEEvent = JSON.parse(line.slice(6));
              handleSSEEvent(event);
            } catch { /* 忽略解析错误 */ }
          }
        }
      }
    } catch (e: unknown) {
      if (abortController.signal.aborted) return;
      setError(e instanceof Error ? e.message : '学习过程出错');
    } finally {
      setLearning(false);
      fetchPatterns();
    }
  };

  // ─── SSE 事件处理 ──────────────────────────────────────

  const handleSSEEvent = (event: LearnSSEEvent) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    switch (event.type) {
      case 'progress': {
        const phase = event.phase ?? 'unknown';
        const msg = event.message ?? '';
        setSteps((prev) => [...prev.filter((s) => s.phase !== phase || s.status !== 'done'), {
          phase,
          status: 'done',
          message: msg,
        }]);
        // 同时也显示为消息
        if (msg && !msg.startsWith('正在')) {
          setMessages((prev) => [...prev, {
            id, role: 'system',
            content: msg,
            timestamp: Date.now(),
          }]);
        }
        break;
      }

      case 'screenshot':
        setMessages((prev) => [...prev, {
          id, role: 'assistant',
          content: event.analysis ?? event.description ?? '',
          screenshot_b64: event.screenshot_b64,
          timestamp: Date.now(),
        }]);
        break;

      case 'analysis':
        setMessages((prev) => [...prev, {
          id, role: 'assistant',
          content: event.message ?? '',
          timestamp: Date.now(),
        }]);
        break;

      case 'question':
        setMessages((prev) => [...prev, {
          id, role: 'assistant',
          content: event.question_text ?? event.message ?? '',
          screenshot_b64: event.screenshot_b64,
          timestamp: Date.now(),
        }]);
        setShowQuestion(true);
        break;

      case 'pattern':
        if (event.pattern) {
          setSelectedPattern(event.pattern as DrawingPattern);
        }
        setSteps((prev) => [...prev, {
          phase: 'done', status: 'done',
          message: event.message ?? '模式已生成',
        }]);
        break;

      case 'done':
        setSteps((prev) => [...prev, {
          phase: 'done', status: 'done',
          message: event.message ?? '学习完成',
        }]);
        // 如果 done 事件包含 pattern 数据
        if (event.pattern && !selectedPattern) {
          setSelectedPattern(event.pattern as DrawingPattern);
        }
        break;

      case 'error':
        setError(event.error ?? '未知错误');
        break;
    }
  };

  // ─── 回答问题 ──────────────────────────────────────────

  const handleAnswer = async () => {
    if (!questionText.trim()) return;
    setShowQuestion(false);
    setMessages((prev) => [...prev, {
      id: `${Date.now()}`,
      role: 'user',
      content: questionText,
      timestamp: Date.now(),
    }]);
    setQuestionText('');
  };

  // ─── 确认模式 ──────────────────────────────────────────

  const handleConfirmPattern = async (id?: number) => {
    try {
      const pid = id ?? 0; // SSE 生成的模式暂无 ID，传 0 由后端创建新记录
      const res = await apiClient.post(`/api/learn/patterns/${pid}/confirm`, {
        confirmed: true,
        session_id: sessionId,  // 让后端能找到 LearnAgent 的临时 pattern 数据
      });
      // 用后端返回的实际 ID 更新 selectedPattern
      if (res.data?.pattern_id) {
        setSelectedPattern((prev) => prev ? { ...prev, id: res.data.pattern_id, is_confirmed: true } : prev);
      }
      fetchPatterns();
    } catch { /* ignore */ }
  };

  // ─── 删除模式 ──────────────────────────────────────────

  const handleDeletePattern = async (id: number) => {
    if (!confirm('确定删除该学习模式？')) return;
    try {
      await apiClient.delete(`/api/learn/patterns/${id}`);
      setSelectedPattern(null);
      fetchPatterns();
    } catch { /* ignore */ }
  };

  // ─── 应用模式 ──────────────────────────────────────────

  const handleApplyPattern = async (id: number) => {
    try {
      await apiClient.post(`/api/learn/patterns/${id}/apply?session_id=learn-session`);
    } catch { /* ignore */ }
  };

  // ─── 取消学习 ──────────────────────────────────────────

  const handleCancel = () => {
    abortRef.current?.abort();
    setLearning(false);
  };

  // ─── 渲染 ──────────────────────────────────────────────

  return (
    <div className="flex h-full bg-gray-950">
      {/* ── 左侧：主操作区 ──────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* 标题栏 */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-800/50 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600
                          flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <BookmarkIcon className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-100">图纸学习模式</h1>
            <p className="text-[11px] text-gray-600">上传参考图纸，AI 多尺度分析并提取可复用的绘制模式</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {learning && (
              <button onClick={handleCancel}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10
                           border border-red-500/20 text-red-400 text-xs
                           hover:bg-red-500/20 transition-all">
                <XCircleIcon className="w-3.5 h-3.5" />
                取消
              </button>
            )}
          </div>
        </div>

        {/* 内容区 */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

          {/* ── 文件上传区 ───────────────────────────── */}
          {!learning && !selectedPattern && (
            <div className="max-w-2xl mx-auto pt-8">
              <div
                className="relative border-2 border-dashed border-gray-700 rounded-2xl p-12
                           hover:border-emerald-500/50 transition-all text-center
                           bg-gray-900/50"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files[0];
                  if (f) setFile(f);
                }}
              >
                <input
                  type="file"
                  accept=".dwg,.dxf,.pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20
                                  flex items-center justify-center">
                    <DocumentArrowUpIcon className="w-8 h-8 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-base font-medium text-gray-200">
                      {file ? file.name : '拖放或点击上传参考图纸'}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      支持 DWG / DXF / PDF 格式
                      {file && ` — ${(file.size / 1024 / 1024).toFixed(2)} MB`}
                    </p>
                  </div>
                  {file && !uploading && (
                    <button onClick={handleUpload}
                      disabled={uploading}
                      className="relative z-10 flex items-center gap-2 px-6 py-2.5 rounded-xl
                                 bg-gradient-to-r from-emerald-600 to-teal-600
                                 hover:from-emerald-500 hover:to-teal-500
                                 text-white text-sm font-medium
                                 transition-all shadow-lg shadow-emerald-500/25
                                 active:scale-[0.98] disabled:opacity-50">
                      开始学习
                    </button>
                  )}
                  {uploading && (
                    <div className="flex items-center gap-2 text-sm text-emerald-400">
                      <ArrowPathIcon className="w-4 h-4 animate-spin" />
                      上传中...
                    </div>
                  )}
                </div>
              </div>

              {error && (
                <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}
            </div>
          )}

          {/* ── 学习进度时间线 ────────────────────────── */}
          {learning && steps.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center gap-1 flex-wrap">
                {steps.map((step, i) => (
                  <React.Fragment key={step.phase}>
                    {i > 0 && (
                      <div className={`w-6 h-px ${step.status === 'done' ? 'bg-emerald-500/40' : 'bg-gray-700'}`} />
                    )}
                    <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all
                                     ${step.status === 'done'
                        ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'
                        : 'bg-gray-800/60 border border-gray-700/50 text-gray-500'
                      }`}>
                      {stepIcons[step.phase] ?? <div className="w-3 h-3 rounded-full bg-gray-600" />}
                      {stepLabels[step.phase] ?? step.phase}
                    </div>
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* ── 对话消息区 ────────────────────────────── */}
          {messages.length > 0 && (
            <div className="space-y-3">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm
                                   ${msg.role === 'user'
                      ? 'bg-blue-600/20 border border-blue-500/30 text-blue-200'
                      : 'bg-gray-900/70 border border-gray-800 text-gray-300'
                    }`}>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.screenshot_b64 && (
                      <div className="mt-3 rounded-xl overflow-hidden border border-gray-700">
                        <img
                          src={`data:image/png;base64,${msg.screenshot_b64}`}
                          alt="AutoCAD 截图"
                          className="max-w-full h-auto cursor-zoom-in hover:scale-105 transition-transform"
                          onClick={(e) => {
                            const img = e.currentTarget;
                            img.classList.toggle('scale-150');
                          }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />

              {/* 问题输入 */}
              {showQuestion && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                  <QuestionMarkCircleIcon className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 flex gap-2">
                    <input
                      type="text"
                      value={questionText}
                      onChange={(e) => setQuestionText(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleAnswer(); }}
                      placeholder="回答 LLM 的问题..."
                      className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2
                                 text-sm text-gray-200 placeholder-gray-600
                                 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                      autoFocus
                    />
                    <button onClick={handleAnswer}
                      disabled={!questionText.trim()}
                      className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500
                                 text-white text-sm font-medium transition-all
                                 disabled:opacity-50 active:scale-95">
                      回答
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 加载中 */}
          {learning && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20">
              <ArrowPathIcon className="w-8 h-8 text-emerald-400 animate-spin" />
              <p className="text-sm text-gray-500 mt-4">正在多尺度分析图纸...</p>
              <p className="text-xs text-gray-600 mt-1">缩放 → 截图 → 识别 → 提取</p>
            </div>
          )}

          {/* ── Pattern 详情 ────────────────────────────── */}
          {selectedPattern && !learning && (
            <div className="max-w-3xl space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-base font-semibold text-gray-100">
                  {selectedPattern.name}
                  {!selectedPattern.is_confirmed && (
                    <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30">
                      待确认
                    </span>
                  )}
                </h2>
                <button onClick={() => setSelectedPattern(null)}
                  className="text-gray-600 hover:text-gray-400 transition-colors">
                  <XCircleIcon className="w-5 h-5" />
                </button>
              </div>

              {/* 概览 */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-3">
                  <div className="text-[10px] text-gray-600 uppercase mb-1">源文件</div>
                  <div className="text-sm text-gray-300">{selectedPattern.source_file}</div>
                </div>
                <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-3">
                  <div className="text-[10px] text-gray-600 uppercase mb-1">设备数</div>
                  <div className="text-sm text-gray-300">{selectedPattern.devices?.length ?? 0} 种设备</div>
                </div>
              </div>

              {/* 拓扑结构 */}
              <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-4">
                <h3 className="text-xs font-semibold text-gray-400 mb-2">拓扑结构</h3>
                <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap">
                  {JSON.stringify(selectedPattern.topology, null, 2)}
                </pre>
              </div>

              {/* 设备清单 */}
              {selectedPattern.devices?.length > 0 && (
                <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-3">设备清单</h3>
                  <div className="space-y-2">
                    {selectedPattern.devices.map((d, i) => (
                      <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-gray-950/50">
                        <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20
                                        flex items-center justify-center text-xs text-blue-400 font-mono">
                          {d.type?.slice(0, 4) ?? '?'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-gray-300">{d.type}</div>
                          <div className="text-[11px] text-gray-600">
                            标注模式: {d.label_pattern ?? '—'}
                            {d.typical_position && (
                              <> · 典型位置: ({d.typical_position.x}, {d.typical_position.y})</>
                            )}
                            </div>
                        </div>
                        <span className="text-xs text-gray-500">×{d.quantity ?? 1}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 布局规则 */}
              {selectedPattern.layout_rules?.length > 0 && (
                <div className="bg-gray-900/70 border border-gray-800 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-gray-400 mb-2">布局规则</h3>
                  <ul className="space-y-1">
                    {selectedPattern.layout_rules.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                        <span className="text-emerald-400 mt-0.5">•</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 未解决问题 */}
              {selectedPattern.unresolved_questions && selectedPattern.unresolved_questions.length > 0 && (
                <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4">
                  <h3 className="text-xs font-semibold text-amber-400 mb-2">待确认问题</h3>
                  <ul className="space-y-1">
                    {selectedPattern.unresolved_questions.map((q, i) => (
                      <li key={i} className="text-xs text-amber-300/70">• {q}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex items-center gap-2 pt-2">
                {!selectedPattern.is_confirmed && (
                  <button onClick={() => handleConfirmPattern(selectedPattern.id)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600
                               hover:bg-emerald-500 text-white text-sm font-medium
                               transition-all shadow-sm shadow-emerald-500/25 active:scale-95">
                    <CheckCircleIcon className="w-4 h-4" />
                    确认模式
                  </button>
                )}
                <button onClick={() => handleApplyPattern(selectedPattern.id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600
                             hover:bg-blue-500 text-white text-sm font-medium
                             transition-all shadow-sm shadow-blue-500/25 active:scale-95">
                  <PlayIcon className="w-4 h-4" />
                  应用到当前绘图
                </button>
                <button onClick={() => handleDeletePattern(selectedPattern.id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-800
                             hover:bg-red-500/20 hover:text-red-400 text-gray-400
                             text-sm transition-all">
                  <TrashIcon className="w-4 h-4" />
                  删除
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 右侧：已学模式列表 ────────────────────────── */}
      <div className="w-80 border-l border-gray-800/50 flex flex-col flex-shrink-0">
        <div className="px-4 py-3 border-b border-gray-800/50 flex-shrink-0">
          <h3 className="text-xs font-semibold text-gray-400">已学模式 ({patterns.length})</h3>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {patternsLoading ? (
            <div className="flex justify-center py-8">
              <ArrowPathIcon className="w-5 h-5 text-gray-600 animate-spin" />
            </div>
          ) : patterns.length === 0 ? (
            <div className="text-center py-8 text-gray-600">
              <BookmarkIcon className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p className="text-xs">暂无学习模式</p>
              <p className="text-[10px] mt-1">上传图纸开始学习</p>
            </div>
          ) : (
            patterns.map((p) => (
              <button key={p.id}
                onClick={() => { setSelectedPattern(p); setLearning(false); }}
                className={`w-full text-left p-3 rounded-xl border transition-all
                            ${selectedPattern?.id === p.id
                    ? 'bg-emerald-500/10 border-emerald-500/30'
                    : 'bg-gray-900/50 border-gray-800 hover:border-gray-700'
                  }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-200 truncate flex-1">
                    {p.name}
                  </span>
                  {p.is_confirmed
                    ? <CheckCircleIcon className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0 ml-1" />
                    : <ExclamationTriangleIcon className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 ml-1" />
                  }
                </div>
                <div className="text-[10px] text-gray-600">
                  {p.source_file} · {p.devices?.length ?? 0} 设备
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default LearnPage;
