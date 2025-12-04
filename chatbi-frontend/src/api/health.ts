import axios from 'axios';
import type { HealthStatus } from './types';

// 健康检查不走统一拦截器
export const healthApi = {
  check: () =>
    axios.get<HealthStatus>('/health').then(res => res.data),
};
