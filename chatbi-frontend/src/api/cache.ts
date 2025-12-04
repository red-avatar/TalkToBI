import api from './index';
import type { PaginatedData } from './index';
import type { CacheEntry, CacheStats } from './types';

export const cacheApi = {
  // 获取缓存列表
  getList: (params?: { page?: number; page_size?: number; status?: string; keyword?: string }) =>
    api.get<any, { data: PaginatedData<CacheEntry> }>('/cache/', { params }),

  // 获取缓存统计
  getStats: () =>
    api.get<any, { data: CacheStats }>('/cache/stats'),

  // 获取缓存详情
  getById: (id: number) =>
    api.get<any, { data: CacheEntry }>(`/cache/${id}`),

  // 删除单个缓存
  delete: (id: number) =>
    api.delete(`/cache/${id}`),

  // 更新缓存状态 (active/invalid/deprecated)
  updateStatus: (id: number, status: 'active' | 'invalid' | 'deprecated') =>
    api.put(`/cache/${id}/status`, null, { params: { status } }),
};
