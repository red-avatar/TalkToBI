import api from './index';

// 用户信息类型
export interface UserInfo {
  id: number;
  username: string;
  nickname: string;
  is_root: boolean;
  status: number;
  created_at: string;
  updated_at: string;
}

// 登录请求
export interface LoginRequest {
  username: string;
  password: string;
}

// 登录响应
export interface LoginResponse {
  user: UserInfo;
  token: string;
}

// 修改密码请求
export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

// 创建用户请求
export interface CreateUserRequest {
  username: string;
  password?: string;
  nickname?: string;
}

// 登录日志
export interface LoginLog {
  id: number;
  user_id: number | null;
  username: string;
  ip_address: string;
  location: string;
  user_agent: string;
  login_time: string;
  status: number;
  message: string;
}

// 用户登录
export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await api.post('/auth/login', data);
  return res.data;
}

// 用户登出
export async function logout(): Promise<void> {
  await api.post('/auth/logout');
}

// 修改密码
export async function changePassword(userId: number, data: ChangePasswordRequest): Promise<void> {
  await api.put(`/auth/password?user_id=${userId}`, data);
}

// 获取用户列表（root）
export async function getUsers(page = 1, pageSize = 20, isRoot = false) {
  const res = await api.get('/auth/users', {
    params: { page, page_size: pageSize, is_root: isRoot }
  });
  return res.data;
}

// 创建用户（root）
export async function createUser(data: CreateUserRequest, isRoot = false) {
  const res = await api.post('/auth/users', data, {
    params: { is_root: isRoot }
  });
  return res.data;
}

// 重置用户密码（root）
export async function resetPassword(userId: number, isRoot = false): Promise<void> {
  await api.put(`/auth/users/${userId}/reset-password`, null, {
    params: { is_root: isRoot }
  });
}

// 获取登录日志（root）
export async function getLoginLogs(page = 1, pageSize = 20, isRoot = false) {
  const res = await api.get('/auth/logs', {
    params: { page, page_size: pageSize, is_root: isRoot }
  });
  return res.data;
}

// 获取当前用户信息
export async function getCurrentUser(userId: number): Promise<UserInfo> {
  const res = await api.get('/auth/me', {
    params: { user_id: userId }
  });
  return res.data;
}
