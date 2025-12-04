import axios from 'axios';

// 创建Axios实例
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    const { data } = response;
    // 统一响应格式: { code, message, data }
    if (data.code !== 0) {
      console.error(data.message || '请求失败');
      return Promise.reject(new Error(data.message));
    }
    return data;
  },
  (error) => {
    const msg = error.response?.data?.message || error.message || '网络错误';
    console.error(msg);
    return Promise.reject(error);
  }
);

export default api;

// 导出API类型
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
