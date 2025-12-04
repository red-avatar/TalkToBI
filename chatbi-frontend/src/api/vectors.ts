import api from './index';
import type { PaginatedData } from './index';
import type { VectorEntry, VectorStats, ExtractResult, EnhanceResult, BuildResult } from './types';

// 构建状态类型
export interface BuildStatus {
  files: {
    [阶段: string]: {
      exists: boolean;
      size_kb: number;
      modified_at: string | null;
    };
  };
  database: VectorStats;
}

export const vectorsApi = {
  // 获取向量列表
  getList: (params?: { page?: number; page_size?: number; object_type?: string; keyword?: string }) =>
    api.get<any, { data: PaginatedData<VectorEntry> }>('/vectors/', { params }),

  // 获取向量统计
  getStats: () =>
    api.get<any, { data: VectorStats }>('/vectors/stats'),

  // 获取构建状态 (文件状态)
  getStatus: () =>
    api.get<any, { data: BuildStatus }>('/vectors/status'),

  // 获取向量详情
  getById: (id: number) =>
    api.get<any, { data: VectorEntry }>(`/vectors/${id}`),

  // 提取元数据
  extract: () =>
    api.post<any, { data: ExtractResult }>('/vectors/extract'),

  // LLM增强
  enhance: () =>
    api.post<any, { data: EnhanceResult }>('/vectors/enhance'),

  // 构建向量
  build: () =>
    api.post<any, { data: BuildResult }>('/vectors/build'),
};
