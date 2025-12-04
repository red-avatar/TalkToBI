import api from './index';
import type { PaginatedData } from './index';
import type { BusinessTerm, CreateTermRequest, UpdateTermRequest } from './types';

export const termsApi = {
  // 获取业务名词列表
  getList: (params?: { page?: number; page_size?: number }) =>
    api.get<any, { data: PaginatedData<BusinessTerm> }>('/terms/', { params }),

  // 获取单个业务名词 (使用name作为主键)
  getByName: (name: string) =>
    api.get<any, { data: BusinessTerm }>(`/terms/${encodeURIComponent(name)}`),

  // 创建业务名词
  create: (data: CreateTermRequest) =>
    api.post<any, { data: any }>('/terms/', data),

  // 更新业务名词 (使用name作为主键)
  update: (name: string, data: UpdateTermRequest) =>
    api.put<any, { data: any }>(`/terms/${encodeURIComponent(name)}`, data),

  // 删除业务名词 (使用name作为主键)
  delete: (name: string) =>
    api.delete(`/terms/${encodeURIComponent(name)}`),

  // 重新加载配置
  reload: () =>
    api.post('/terms/reload'),
};
