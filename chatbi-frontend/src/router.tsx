import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { useAuth } from './contexts/AuthContext';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Vectors from './pages/Knowledge/Vectors';
import Terms from './pages/Knowledge/Terms';
import Cache from './pages/Knowledge/Cache';
import Logs from './pages/Knowledge/Logs';
import Graph from './pages/Knowledge/Graph';
import Pipeline from './pages/Build/Pipeline';
import Login from './pages/Login';
import Profile from './pages/Profile';
import System from './pages/System';

// 路由守卫：未登录跳转登录页
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function AppRouter() {
  return (
    <Routes>
      {/* 登录页（不需要 AppShell） */}
      <Route path="/login" element={<Login />} />
      
      {/* 需要登录的页面 */}
      <Route path="/" element={<RequireAuth><AppShell /></RequireAuth>}>
        {/* 默认重定向到工作台 */}
        <Route index element={<Navigate to="/dashboard" replace />} />
        
        {/* 工作台 */}
        <Route path="dashboard" element={<Dashboard />} />
        
        {/* 智能对话 */}
        <Route path="chat" element={<Chat />} />
        
        {/* 个人中心 */}
        <Route path="profile" element={<Profile />} />
        
        {/* 系统管理（root） */}
        <Route path="system" element={<System />} />
        
        {/* 知识库管理 */}
        <Route path="knowledge">
          <Route path="vectors" element={<Vectors />} />
          <Route path="terms" element={<Terms />} />
          <Route path="cache" element={<Cache />} />
          <Route path="logs" element={<Logs />} />
          <Route path="graph" element={<Graph />} />
        </Route>
        
        {/* 知识库构建 */}
        <Route path="build">
          <Route path="pipeline" element={<Pipeline />} />
        </Route>
      </Route>
    </Routes>
  );
}
