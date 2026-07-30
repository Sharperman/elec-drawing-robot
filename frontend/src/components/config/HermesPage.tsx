/**
 * Hermes Skill 管理页面 v2
 * - Skill 列表（分类筛选 + 搜索）
 * - Skill 详情面板
 * - 自动创建预览
 * - 命令测试
 */
import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '@/services/apiClient';

// ─── 类型定义 ────────────────────────────────

interface SkillItem {
  skill_id: string;
  metadata: { name: string; description: string; author: string; version: string };
  category: string;
  status: string;
  use_count: number;
  success_count: number;
  triggers?: { patterns: string[]; confidence_threshold: number };
  execution?: { steps: Array<{ tool: string; params: Record<string, unknown> }> };
}

interface CategoryCounts {
  internal: number; external: number; autogen: number; total: number;
}

interface HermesStatus {
  enabled: boolean; running: boolean; current_action: string;
  action_count: number; action_log: string[]; skills: CategoryCounts;
}

// ─── 分类 Tab ─────────────────────────────────

const CATEGORIES = [
  { key: 'all', label: '全部', icon: '📋' },
  { key: 'internal', label: '内置', icon: '⚙️' },
  { key: 'external', label: '外部', icon: '📦' },
  { key: 'autogen', label: '自动生成', icon: '🤖' },
];

// ─── 主组件 ───────────────────────────────────

const HermesPage: React.FC = () => {
  const [status, setStatus] = useState<HermesStatus | null>(null);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [selected, setSelected] = useState<SkillItem | null>(null);
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [autoGenResult, setAutoGenResult] = useState<string | null>(null);

  // ── 数据加载 ──
  const fetchData = useCallback(async () => {
    try {
      const [sr, sk] = await Promise.all([
        apiClient.get('/api/hermes/status'),
        apiClient.get(`/api/hermes/skills${category !== 'all' ? `?category=${category}` : ''}`),
      ]);
      if (sr.data?.code === 0) setStatus(sr.data.data);
      if (sk.data?.code === 0) setSkills(sk.data.data.skills ?? []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [category]);

  useEffect(() => { fetchData(); const t = setInterval(fetchData, 5000); return () => clearInterval(t); }, [fetchData]);

  // ── 筛选 ──
  const filtered = skills.filter(s => {
    if (search) {
      const q = search.toLowerCase();
      const name = s.metadata?.name?.toLowerCase() || '';
      const desc = s.metadata?.description?.toLowerCase() || '';
      return name.includes(q) || desc.includes(q) || s.skill_id.includes(q);
    }
    return true;
  });

  // ── 切换 CU ──
  const handleToggle = async () => {
    try {
      await apiClient.post('/api/hermes/toggle', { enabled: !status?.enabled });
      fetchData();
    } catch { /* ignore */ }
  };

  // ── 删除 Skill ──
  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/api/hermes/skills/${id}`);
      if (selected?.skill_id === id) setSelected(null);
      fetchData();
    } catch { /* ignore */ }
  };

  // ── 测试自动创建 ──
  const handleAutoCreateTest = async () => {
    const fakeTrace = [
      { tool: 'insert_element', params: { symbol: 'breaker_3p', x: 100, y: 200 }, success: true },
      { tool: 'annotate', params: { text: 'QF01', x: 110, y: 195 }, success: true },
    ];
    try {
      const res = await apiClient.post('/api/hermes/skills/autocreate', {
        task_description: '画三极断路器并标注 QF01',
        execution_trace: fakeTrace,
        auto_confirm: false,
      });
      if (res.data?.code === 0) {
        const d = res.data.data;
        setAutoGenResult(JSON.stringify(d, null, 2));
        fetchData();
      }
    } catch { setAutoGenResult('自动创建失败'); }
  };

  return (
    <div className="flex h-full bg-gray-950 overflow-hidden">
      {/* ── 左侧主区域 ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800/50">
          <div className="flex items-center gap-3">
            <h1 className="text-base font-semibold text-gray-100">Hermes Skills</h1>
            <div className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
              status?.enabled ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-gray-800 text-gray-500 border border-gray-700'
            }`}>
              {status?.enabled ? (status.running ? '运行中' : '已就绪') : '已关闭'}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{status?.skills?.total ?? 0} 个 Skill</span>
            <button onClick={handleToggle} className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-all ${
              status?.enabled
                ? 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}>
              {status?.enabled ? '关闭 CU' : '开启 CU'}
            </button>
          </div>
        </div>

        {/* 分类 Tab + 搜索 */}
        <div className="flex items-center gap-2 px-6 py-3 border-b border-gray-800/30">
          {CATEGORIES.map(c => (
            <button key={c.key} onClick={() => setCategory(c.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                category === c.key ? 'bg-blue-600/20 text-blue-400 border border-blue-500/20' : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >{c.icon} {c.label} {status?.skills?.[c.key as keyof CategoryCounts] !== undefined && `(${status.skills[c.key as keyof CategoryCounts]})`}</button>
          ))}
          <div className="flex-1" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="🔍 搜索 Skill..."
            className="w-48 px-3 py-1.5 rounded-lg bg-gray-800/50 border border-gray-700 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/40"
          />
        </div>

        {/* Skill 卡片网格 */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-40"><p className="text-sm text-gray-600">加载中...</p></div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-gray-600">
              <p className="text-sm mb-1">暂无 Skill</p>
              <p className="text-[11px]">{search ? '尝试不同关键词' : '开启 CU 后将自动加载内置 Skills'}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {filtered.map(s => (
                <div key={s.skill_id} onClick={() => setSelected(s)}
                  className={`group cursor-pointer rounded-xl border transition-all p-4 ${
                    selected?.skill_id === s.skill_id
                      ? 'bg-blue-600/10 border-blue-500/30 shadow-lg shadow-blue-500/5'
                      : 'bg-gray-900/50 border-gray-800 hover:border-gray-700 hover:bg-gray-900/80'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-200 group-hover:text-gray-100 transition-colors">
                        {s.metadata?.name || s.skill_id}
                      </h3>
                      <span className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[9px] font-medium uppercase ${
                        s.category === 'internal' ? 'bg-blue-500/10 text-blue-400' :
                        s.category === 'autogen' ? 'bg-purple-500/10 text-purple-400' :
                        'bg-gray-700/50 text-gray-400'
                      }`}>{s.category}</span>
                    </div>
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${s.status === 'active' ? 'bg-green-400' : 'bg-gray-600'}`} />
                  </div>
                  <p className="text-[11px] text-gray-500 leading-relaxed line-clamp-2 mb-2">
                    {s.metadata?.description || '无描述'}
                  </p>
                  <div className="flex items-center gap-3 text-[10px] text-gray-600">
                    <span>使用 {s.use_count || 0} 次</span>
                    <span className={`${s.success_count && s.use_count ? ((s.success_count / s.use_count) >= 0.8 ? 'text-green-500' : 'text-yellow-500') : 'text-gray-600'}`}>
                      {s.use_count ? `${Math.round(s.success_count / s.use_count * 100)}%` : '-'}
                    </span>
                    {s.execution?.steps && <span>{s.execution.steps.length} 步</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── 右侧详情面板 ── */}
      <div className="w-96 border-l border-gray-800/50 flex flex-col overflow-hidden">
        {selected ? (
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800/30">
              <h3 className="text-sm font-semibold text-gray-200">{selected.metadata?.name || selected.skill_id}</h3>
              <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-gray-300 text-lg leading-none">&times;</button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* 状态 */}
              <SkillField label="ID" value={selected.skill_id} mono />
              <SkillField label="描述" value={selected.metadata?.description} />
              <SkillField label="分类" value={selected.category} badge />
              <SkillField label="状态" value={selected.status} badge />
              <SkillField label="作者" value={selected.metadata?.author} />
              <SkillField label="版本" value={selected.metadata?.version} />

              {/* 触发词 */}
              {selected.triggers?.patterns && selected.triggers.patterns.length > 0 && (
                <div>
                  <p className="text-[10px] font-medium text-gray-500 uppercase mb-1.5">触发词</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.triggers.patterns.map((p, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md bg-gray-800 text-[10px] text-gray-300 border border-gray-700">{p}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 执行步骤 */}
              {selected.execution?.steps && selected.execution.steps.length > 0 && (
                <div>
                  <p className="text-[10px] font-medium text-gray-500 uppercase mb-1.5">执行步骤 ({selected.execution.steps.length})</p>
                  <div className="space-y-1">
                    {selected.execution.steps.map((s, i) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-800/30 text-xs">
                        <span className="text-gray-600 w-4 flex-shrink-0">{i + 1}.</span>
                        <span className="text-blue-400 font-mono text-[11px]">{s.tool}</span>
                        <span className="text-gray-600 text-[10px] truncate">{JSON.stringify(s.params)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 统计 */}
              <div className="grid grid-cols-3 gap-2">
                <StatBox label="使用" value={String(selected.use_count || 0)} />
                <StatBox label="成功" value={String(selected.success_count || 0)} />
                <StatBox label="成功率" value={selected.use_count ? `${Math.round(selected.success_count / selected.use_count * 100)}%` : '-'} />
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-2 pt-2 border-t border-gray-800/30">
                {selected.category !== 'internal' && (
                  <button onClick={() => handleDelete(selected.skill_id)}
                    className="flex-1 px-3 py-2 rounded-lg bg-red-500/5 hover:bg-red-500/10 border border-red-500/20 text-red-400 text-xs transition-all"
                  >删除</button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col h-full">
            <div className="px-5 py-3 border-b border-gray-800/30">
              <h3 className="text-sm font-semibold text-gray-200">工具</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {/* CU 状态 */}
              <div className="p-4 rounded-xl bg-gray-900/50 border border-gray-800">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-2 h-2 rounded-full ${status?.running ? 'bg-green-400 animate-pulse' : status?.enabled ? 'bg-blue-400' : 'bg-gray-600'}`} />
                  <span className="text-sm font-medium text-gray-200">Computer Use</span>
                </div>
                <p className="text-[11px] text-gray-500 leading-relaxed mb-2">
                  {status?.running ? status.current_action : status?.enabled ? '就绪' : '未开启'}
                </p>
                {status?.action_log && status.action_log.length > 0 && (
                  <div className="space-y-0.5 max-h-20 overflow-y-auto">
                    {status.action_log.slice(-5).reverse().map((log, i) => (
                      <p key={i} className="text-[10px] font-mono text-gray-600">{log}</p>
                    ))}
                  </div>
                )}
              </div>

              {/* 自动创建测试 */}
              <div className="p-4 rounded-xl bg-gray-900/50 border border-gray-800">
                <h4 className="text-xs font-medium text-gray-300 mb-2">🤖 Skill 自动创建</h4>
                <p className="text-[10px] text-gray-600 mb-2">从成功任务自动提取可复用的 Skill</p>
                <button onClick={handleAutoCreateTest}
                  className="w-full px-3 py-2 rounded-lg bg-purple-600/10 hover:bg-purple-600/20 border border-purple-500/20 text-purple-400 text-xs transition-all"
                >测试自动创建</button>
                {autoGenResult && (
                  <pre className="mt-2 p-2 rounded-lg bg-gray-800 text-[10px] text-gray-400 overflow-x-auto max-h-40">{autoGenResult}</pre>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ─── 小组件 ────────────────────────────────────────

const SkillField: React.FC<{ label: string; value?: string; mono?: boolean; badge?: boolean }> = ({ label, value, mono, badge }) => (
  <div className="flex items-start gap-2">
    <span className="text-[10px] font-medium text-gray-500 uppercase w-16 flex-shrink-0">{label}</span>
    {badge ? (
      <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
        value === 'active' ? 'bg-green-500/10 text-green-400' :
        value === 'internal' ? 'bg-blue-500/10 text-blue-400' :
        value === 'autogen' ? 'bg-purple-500/10 text-purple-400' :
        'bg-gray-700/50 text-gray-400'
      }`}>{value}</span>
    ) : (
      <span className={`text-xs text-gray-400 ${mono ? 'font-mono' : ''}`}>{value || '-'}</span>
    )}
  </div>
);

const StatBox: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="text-center p-3 rounded-lg bg-gray-800/30 border border-gray-800/50">
    <p className="text-sm font-semibold text-gray-200">{value}</p>
    <p className="text-[9px] text-gray-600 mt-0.5">{label}</p>
  </div>
);

export default HermesPage;
