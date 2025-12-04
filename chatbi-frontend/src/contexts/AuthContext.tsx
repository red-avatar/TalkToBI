import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { UserInfo } from '../api/auth';
import { login as apiLogin, logout as apiLogout } from '../api/auth';

interface AuthContextType {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isRoot: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  updateUser: (user: UserInfo) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = 'talktobi_user';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(() => {
    // 从 localStorage 恢复用户信息
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return null;
      }
    }
    return null;
  });

  const isAuthenticated = !!user;
  const isRoot = user?.is_root ?? false;

  // 登录
  const login = async (username: string, password: string) => {
    try {
      const data = await apiLogin({ username, password });
      setUser(data.user);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data.user));
      return { success: true, message: '登录成功' };
    } catch (error: any) {
      return { success: false, message: error.message || '登录失败' };
    }
  };

  // 登出
  const logout = () => {
    apiLogout().catch(() => {});
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  // 更新用户信息
  const updateUser = (newUser: UserInfo) => {
    setUser(newUser);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newUser));
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, isRoot, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
