/**
 * ComputerUseSettings — Computer Use 开关 + 录制控制 + 录制历史
 * 嵌入在 SettingsPage 中
 */
import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '@/services/apiClient';

interface RecordingSession {
  id: number;
  session_name: string;
  cad_file: string;
  started_at: string;
  duration_seconds: number;
  total_frames: number;
  step_count: number;
  status: string;
  fps: number;
}

const ComputerUseSettings: React.FC = () => {
  const [cuEnabled, setCuEnabled] = useState(false);
  const [recording, setRecording] = useState(false);
  const [sessionName, setSessionName] = useState('');
  const [fps, setFps] = useState(5);
  const [sessions, setSessions] = useState<RecordingSession[]>([]);
  const [message, setMessage] = useState('');

  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/recording/sessions');
      setSessions(res.data?.data?.items ?? []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  // 轮询录制中的会话
  useEffect(() => {
    const hasRecording = sessions.some(s => s.status === 'recording');
    if (hasRecording) {
      const interval = setInterval(fetchSessions, 5000);
      return () => clearInterval(interval);
    }
  }, [sessions, fetchSessions]);

  const startRecording = async () => {
    try {
      const params = new URLSearchParams();
      params.set('session_name', sessionName || `录制_${new Date().toLocaleTimeString()}`);
      params.set('fps', String(fps));
      const res = await apiClient.post(`/api/recording/start?${params.toString()}`);
      setRecording(true);
      setMessage('录制已开始');
      fetchSessions();
    } catch {
      setMessage('开始录制失败');
    }
  };

  const stopRecording = async () => {
    try {
      await apiClient.post('/api/recording/stop');
      setRecording(false);
      setMessage('录制已停止');
      fetchSessions();
    } catch {
      setMessage('停止录制失败');
    }
  };

  const handleAnalyze = async (id: number) => {
    try {
      await apiClient.post(`/api/recording/sessions/${id}/analyze`);
      setMessage('分析已启动');
      fetchSessions();
    } catch {
      setMessage('分析失败');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此录制？视频文件也将被删除。')) return;
    try {
      await apiClient.delete(`/api/recording/sessions/${id}`);
      fetchSessions();
    } catch { /* ignore */ }
  };

  const formatDuration = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6">
      {/* Computer Use Switch */}
      <div className="rounded-xl border border-slate-700/50 p-4 bg-slate-800/30">
        <h3 className="text-sm font-medium text-white mb-3">Computer Use 模式</h3>
        <div className="p-3 mb-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
          <p className="text-xs text-amber-400 leading-relaxed">
            启用后 AI 将获得桌面控制权限（截图/虚拟点击/键盘/浏览器）。
            所有操作使用虚拟输入，不影响您的鼠标键盘。
            白名单应用自动执行，其他应用需手动授权。ESC 键可随时中断。
          </p>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Computer Use</span>
          <button
            onClick={() => setCuEnabled(!cuEnabled)}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              cuEnabled ? 'bg-blue-600' : 'bg-slate-600'
            }`}
          >
            <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
              cuEnabled ? 'translate-x-7' : 'translate-x-1'
            }`} />
          </button>
        </div>
        {cuEnabled && (
          <div className="mt-3 text-xs text-slate-400">
            白名单: AutoCAD · Chrome · Edge · 文件管理器
          </div>
        )}
      </div>

      {/* Recording Controls */}
      <div className="rounded-xl border border-slate-700/50 p-4 bg-slate-800/30">
        <h3 className="text-sm font-medium text-white mb-3">后台操作录制</h3>

        <div className="flex flex-wrap items-center gap-3 mb-3">
          <input
            type="text"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            placeholder="录制名称（可选）"
            className="px-3 py-1.5 rounded-lg bg-slate-700 border border-slate-600 text-xs text-slate-300 w-40"
          />
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400">FPS:</label>
            <select
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
              className="px-2 py-1.5 rounded-lg bg-slate-700 border border-slate-600 text-xs text-slate-300"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={30}>30</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {!recording ? (
            <button
              onClick={startRecording}
              className="px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm transition-colors flex items-center gap-2"
            >
              <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
              开始录制
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="px-4 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-sm transition-colors"
            >
              停止录制
            </button>
          )}
          {recording && (
            <span className="text-xs text-red-400 animate-pulse">
              录���中...
            </span>
          )}
        </div>
      </div>

      {message && <p className="text-xs text-slate-400">{message}</p>}

      {/* Recording History */}
      <div>
        <h3 className="text-sm font-medium text-white mb-3">录制历史</h3>
        {sessions.length === 0 ? (
          <p className="text-xs text-slate-500">暂无录制</p>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <div key={s.id}
                className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/30"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-sm">{s.status === 'recording' ? '⏺' : s.status === 'done' ? '✓' : '📹'}</span>
                  <div>
                    <p className="text-sm text-slate-300 truncate">{s.session_name}</p>
                    <p className="text-[11px] text-slate-500">
                      {formatDuration(s.duration_seconds || 0)} · {s.step_count}步 · {s.fps}fps
                      {s.status === 'analyzing' && ' · 分析中...'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {s.status === 'stopped' && (
                    <button onClick={() => handleAnalyze(s.id)}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300 transition-colors">
                      分析
                    </button>
                  )}
                  <button onClick={() => handleDelete(s.id)}
                    className="text-[11px] text-slate-500 hover:text-red-400 transition-colors">
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ComputerUseSettings;
