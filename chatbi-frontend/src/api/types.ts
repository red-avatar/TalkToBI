// ============ 业务名词 (匹配后端实际返回) ============
export interface BusinessTerm {
  name: string;           // 名词名称（主键）
  meaning: string;        // 含义解释
  sql_hint: string;       // SQL提示
  examples: string[];     // 示例列表
}

export interface CreateTermRequest {
  name: string;
  meaning: string;
  sql_hint?: string;
  examples?: string[];
}

export interface UpdateTermRequest {
  meaning?: string;
  sql_hint?: string;
  examples?: string[];
}

// ============ 查询缓存 ============
export interface CacheEntry {
  id: number;
  query_hash: string;
  original_query: string;
  rewritten_query: string;
  sql: string;
  tables_used: string[];
  cache_score: number;
  hit_count: number;
  status: 'active' | 'invalid' | 'deprecated';
  created_at: string;
  updated_at: string;
}

export interface CacheStats {
  total: number;
  active: number;
  invalid: number;
  deprecated: number;
  total_hits: number;
  avg_score: number;
}

// ============ 向量数据 ============
export interface VectorEntry {
  id: number;
  object_type: 'table' | 'column';
  object_name: string;
  original_description: string;
  enriched_description: string;
  metadata: Record<string, any>;
  embedding_dim: number;
}

export interface VectorStats {
  total: number;
  table_count: number;
  column_count: number;
}

export interface ExtractResult {
  tables_count: number;
  columns_count: number;
  output_file: string;
}

export interface EnhanceResult {
  enhanced_count: number;
  output_file: string;
}

export interface BuildResult {
  vectors_count: number;
  collection_name: string;
}

// ============ 执行日志 ============
export interface LogEntry {
  id: number;
  query_text: string;
  rewritten_query: string;
  sql_generated: string;
  tables_used: string[];
  status: 'success' | 'error' | 'timeout' | 'pending';
  error_message: string | null;
  result_row_count: number;
  execution_time_ms: number;
  cache_score: number;
  cache_hit: boolean;
  session_id: string;
  message_id: string;
  chart_type: string;
  created_at: string;
}

export interface LogStats {
  total: number;
  success_count: number;
  error_count: number;
  timeout_count: number;
  success_rate: number;
  cache_hit_count: number;
  cache_hit_rate: number;
  avg_execution_time_ms: number;
  avg_cache_score: number;
}

// ============ WebSocket消息类型 (匹配后端协议) ============

// 消息类型枚举
export type WSMessageType = 
  | 'user_message' | 'interrupt' | 'ping' | 'get_history'  // 客户端发送
  | 'status' | 'text_chunk' | 'complete' | 'error' | 'interrupted' | 'history' | 'pong';  // 服务端发送

// 处理阶段
export type ProcessingStage = 'intent' | 'planner' | 'executor' | 'analyzer' | 'responder';

// 通用WebSocket消息
export interface WSMessage {
  type: WSMessageType;
  payload: Record<string, any>;
  timestamp?: string;
  message_id?: string;
}

// ---- 客户端发送的消息 ----

// 用户消息
export interface WSUserMessagePayload {
  content: string;
  message_id?: string;
}

// 中断请求
export interface WSInterruptPayload {
  reason: 'user_cancel' | 'new_message';
  target_message_id?: string;
}

// ---- 服务端发送的消息载荷 ----

// 状态更新
export interface WSStatusPayload {
  stage: ProcessingStage;
  message: string;
  message_id?: string;
  progress?: number;
  details?: Record<string, any>;
}

// 文本块（流式）
export interface WSTextChunkPayload {
  content: string;
  message_id?: string;
  chunk_index: number;
  is_first: boolean;
  is_last: boolean;
}

// 可视化配置
export interface WSVisualizationPayload {
  recommended: boolean;
  chart_type?: string;
  echarts_option?: Record<string, any>;
  raw_data?: Record<string, any>[];
  aggregation?: Record<string, any>;
}

// 数据洞察
export interface WSDataInsightPayload {
  summary?: string;
  highlights?: string[];
  trend?: string;
  statistics?: Record<string, any>;
}

// 调试信息
export interface WSDebugPayload {
  sql_query?: string;
  raw_data?: Record<string, any>[];
  row_count?: number;
  execution_time_ms?: number;
  selected_tables?: string[];
  intent?: Record<string, any>;
}

// 完成消息
export interface WSCompletePayload {
  message_id: string;
  reply_to?: string;
  text_answer: string;
  sql_query?: string;
  data_insight?: WSDataInsightPayload;
  visualization?: WSVisualizationPayload;
  debug?: WSDebugPayload;
}

// 错误消息
export interface WSErrorPayload {
  code: string;
  message: string;
  message_id?: string;
  stage?: ProcessingStage;
  recoverable: boolean;
  details?: Record<string, any>;
}

// 中断确认
export interface WSInterruptedPayload {
  message_id: string;
  stage?: ProcessingStage;
  partial_answer?: string;
}

// ============ 健康检查 ============
// 注意：后端可能没有健康检查API，暂时禁用
export interface HealthStatus {
  status: string;
  database?: boolean;
  vector_store?: boolean;
  llm?: boolean;
  cache?: boolean;
}

// ============ 元数据文件结构 ============
export interface TableSchema {
  name: string;           // 表名
  comment?: string;       // 表注释
  columns: ColumnSchema[];
  relationships?: Relationship[];
}

export interface ColumnSchema {
  name: string;           // 列名
  data_type: string;      // 数据类型
  comment?: string;       // 列注释
  is_primary_key?: boolean;
  is_foreign_key?: boolean;
  sample_values?: string[];
}

export interface Relationship {
  source_column: string;
  target_table: string;
  target_column: string;
  relation_type: string;
}

export interface EnrichedTable {
  table_name: string;
  table_comment: string;
  business_description: string;
  synonyms: string[];
  columns: EnrichedColumn[];
}

export interface EnrichedColumn {
  column_name: string;
  data_type: string;
  column_comment: string;
  business_meaning: string;
  synonyms: string[];
  sample_values?: string[];
}

export interface TableRelationship {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relationship_type: string;
  join_hint: string;
}

// ============ 知识图谱构建 ============

/** 关系属性 */
export interface RelationshipProperties {
  condition: string;
  confidence: number;
  join_type: string;
  description: string;
}

/** 图谱关系 */
export interface GraphRelationship {
  source: string;
  target: string;
  type: string;
  properties: RelationshipProperties;
}

/** 本地JSON关系数据 */
export interface LocalRelationships {
  relationships: GraphRelationship[];
  updated_at?: string;
}

/** LLM推断结果 */
export interface InferResult {
  success: boolean;
  relationships: GraphRelationship[];
  tables_analyzed: number;
  total_batches: number;
  message: string;
}

/** 同步到Neo4j结果 */
export interface SyncResult {
  success: boolean;
  tables_count: number;
  columns_count: number;
  relations_count: number;
  message: string;
}

/** 图谱统计 */
export interface GraphStats {
  tables_count: number;
  relationships_count: number;
  last_synced?: string;
}
