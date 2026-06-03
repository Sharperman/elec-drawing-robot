/**
 * TypeScript 类型定义
 * 与后端 Pydantic Schema 保持一致
 */

// ============================================================
// 通用类型
// ============================================================

export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface PagedData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

// ============================================================
// Chat / Session
// ============================================================

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

export interface Message {
  id: number;
  session_id: string;
  role: MessageRole;
  content: string;
  tool_calls?: string;
  image_data?: string;
  is_streaming: boolean;
  token_count?: number;
  created_at: string;
}

export interface Session {
  id: number;
  session_id: string;
  title: string;
  drawing_file?: string;
  drawing_name?: string;
  standard_id?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateSessionRequest {
  title?: string;
  drawing_file?: string;
  standard_id?: number;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  image_data?: string;
  stream?: boolean;
  /** 运行模式: auto=自动, check=图纸审查, draw=绘图 */
  mode?: RunMode;
}

/** 运行模式类型 */
export type RunMode = 'auto' | 'check' | 'draw';

export interface ChatConfirmRequest {
  session_id: string;
  confirm: boolean;
  modifications?: string;
}

// 流式 SSE 数据
export interface SSEChunk {
  token: string;
  done: boolean;
  full?: string;
  error?: string;
}

/** 新的结构化 SSE 事件类型 */
export type SSEEventType =
  | 'thinking'
  | 'tool_start'
  | 'tool_end'
  | 'text'
  | 'done'
  | 'error'
  | 'report';

/** 单个 Agent 步骤（前端渲染用） */
export interface AgentStep {
  id: string;
  type: 'thinking' | 'tool_call' | 'text';
  status: 'running' | 'done';
  /** 思考阶段 */
  thinkingContent?: string;
  /** 工具调用 */
  toolName?: string;
  toolInput?: string;
  toolOutput?: string;
  /** 文本 token 累积 */
  textContent?: string;
}

/** 结构化 SSE 事件 */
export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  tool_name?: string;
  tool_input?: string;
  tool_output?: string;
  /** 审查报告路径（type=report 时） */
  path?: string;
}

// ============================================================
// AutoCAD
// ============================================================

export interface AutoCADStatus {
  connected: boolean;
  drawing_name?: string;
  drawing_path?: string;
  autocad_version?: string;
  entity_count: number;
  last_check: string;
}

export interface AutoCADConnectRequest {
  version?: string;
}

// ============================================================
// Symbol
// ============================================================

export type SymbolCategory =
  | 'protection'
  | 'switch'
  | 'transformer'
  | 'line'
  | 'measurement'
  | 'grounding'
  | 'source'
  | 'load'
  | 'signal'
  | 'general';

export interface Symbol {
  id: string;          // 前端统一用 string id（后端 int 自动转换）
  symbol_id: string;
  name: string;
  name_en: string;
  category: string;    // 后端可能返回任意分类字符串，放宽类型
  standard: string;
  description: string;
  block_name: string;
  layer: string;
  width: number;
  height: number;
  tags: string;        // JSON 字符串
  is_builtin: boolean;
  is_active: boolean;
  /** 别名数组（用于搜索匹配） */
  aliases?: string[];
  /** SVG 数据字符串（用于图元卡片预览） */
  svg_data?: string;
}

export interface CreateSymbolRequest {
  symbol_id: string;
  name: string;
  name_en?: string;
  category?: SymbolCategory;
  description?: string;
  block_name?: string;
  layer?: string;
  width?: number;
  height?: number;
  tags?: string[];
}

// ============================================================
// Standards
// ============================================================

export interface LayerConfig {
  id: string;
  standard_id: string;
  layer_name: string;
  color_index: number;
  linetype: string;
  /** 线宽，可能是数字或字符串（"DEFAULT" / "0.25"） */
  lineweight: string;
  description?: string;
}

export interface DrawingStandard {
  id: string;
  name: string;
  description: string;
  version: string;
  is_active: boolean;
  text_style: string;
  text_height: number;
  dim_style: string;
  title_block: string; // JSON 字符串
  created_at: string;
  /** 后端返回字段名为 layers 或 layer_configs，前端均支持 */
  layers?: LayerConfig[];
  layer_configs?: LayerConfig[];
}

export interface CreateStandardRequest {
  name: string;
  description?: string;
  version?: string;
  text_style?: string;
  text_height?: number;
  dim_style?: string;
  title_block?: Record<string, unknown>;
}

// ============================================================
// Recognition
// ============================================================

export interface DetectedElement {
  symbol_id: string;
  symbol_name: string;
  confidence: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  center_x: number;
  center_y: number;
  width: number;
  height: number;
}

export interface RecognitionResponse {
  elements: DetectedElement[];
  total: number;
  model_version: string;
  inference_time_ms: number;
}

// ============================================================
// Feedback
// ============================================================

export type FeedbackType = 'positive' | 'negative' | 'correction' | 'suggestion';

export interface FeedbackRequest {
  session_id: string;
  message_id?: number;
  feedback_type: FeedbackType;
  original_input?: string;
  agent_output?: string;
  user_comment?: string;
  correction?: string;
  rating?: number;
}

export interface LearnedRule {
  id: number;
  rule_id: string;
  title: string;
  rule_content: string;
  trigger_pattern: string;
  confidence: number;
  apply_count: number;
  is_active: boolean;
  created_at: string;
}

// ============================================================
// Python 进程状态（Electron IPC）
// ============================================================

export interface PythonStatus {
  running: boolean;
  pid: number | null;
  port: number;
}

// ============================================================
// 应用设置
// ============================================================

export interface AppSettings {
  openaiApiKey: string;
  openaiBaseUrl: string;
  modelName: string;
  autocadVersion: string;
  theme: 'dark' | 'light';
  language: 'zh' | 'en';
  autoConnectAutocad: boolean;
  snapshotInterval: number; // 截图刷新间隔（秒）
}
