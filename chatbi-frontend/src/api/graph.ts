/**
 * 知识图谱构建 API
 * Author: 陈怡坚
 * Time: 2025-12-03
 */
import api from './index';
import type {
  GraphRelationship,
  InferResult,
  SyncResult,
  TableSchema,
} from './types';

export const graphApi = {
  // 获取MySQL元数据（返回直接数组）
  getMetadata: () =>
    api.get<any, { data: TableSchema[] }>('/graph/metadata'),

  // 触发LLM推断生成关系
  inferRelationships: () =>
    api.post<any, { data: InferResult }>('/graph/infer'),

  // 读取本地关系JSON（返回直接数组）
  getLocalRelationships: () =>
    api.get<any, { data: GraphRelationship[] }>('/graph/relationships/local'),

  // 保存本地关系JSON
  saveLocalRelationships: (relationships: GraphRelationship[]) =>
    api.post<any, { data: { message: string } }>(
      '/graph/relationships/local',
      { relationships }
    ),

  // 获取已保存的Schema
  getSavedSchema: () =>
    api.get<any, { data: { tables: TableSchema[] } }>('/graph/schema'),

  // 同步到Neo4j
  syncToNeo4j: () =>
    api.post<any, { data: SyncResult }>('/graph/sync-to-neo4j'),
};
