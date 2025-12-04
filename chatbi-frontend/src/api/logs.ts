import api from './index';
import type { PaginatedData } from './index';
import type { LogEntry, LogStats } from './types';

export const logsApi = {
  // 获取日志列表
  getList: (params?: { 
    page?: number; 
    page_size?: number; 
    status?: string;
    start_date?: string;
    end_date?: string;
  }) =>
    api.get<any, { data: PaginatedData<LogEntry> }>('/logs/', { params }),

  // 获取日志统计
  getStats: () =>
    api.get<any, { data: LogStats }>('/logs/stats'),

  // 获取单条日志详情
  getById: (id: string) =>
    api.get<any, { data: LogEntry }>(`/logs/${id}`),

  // 删除日志
  delete: (id: string) =>
    api.delete(`/logs/${id}`),

  // 清理过期日志
  cleanup: (days: number) =>
    api.delete(`/logs/cleanup`, { params: { days } }),
};
