import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, Users, FileText } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/ui/Toast';
import type { UserInfo, LoginLog } from '../../api/auth';
import { getUsers, createUser, resetPassword, getLoginLogs } from '../../api/auth';
import * as styles from './styles.css';

type Tab = 'users' | 'logs';

export default function System() {
  const navigate = useNavigate();
  const { isRoot } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('users');

  // 非 root 用户无权访问
  useEffect(() => {
    if (!isRoot) {
      navigate('/dashboard');
    }
  }, [isRoot, navigate]);

  if (!isRoot) return null;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>系统管理</h1>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'users' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={16} style={{ marginRight: 4 }} />
          用户管理
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'logs' ? styles.tabActive : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          <FileText size={16} style={{ marginRight: 4 }} />
          登录日志
        </button>
      </div>

      {activeTab === 'users' && <UserManagement />}
      {activeTab === 'logs' && <LoginLogs />}
    </div>
  );
}

// 用户管理组件
function UserManagement() {
  const { isRoot } = useAuth();
  const { toast, confirm } = useToast();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers(page, 20, isRoot);
      setUsers(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error('获取用户列表失败', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, isRoot]);

  const handleResetPassword = (userId: number, username: string) => {
    confirm({
      title: '重置密码',
      message: `确定要重置用户 "${username}" 的密码为 123456 吗？`,
      confirmText: '确定重置',
      danger: true,
      onConfirm: async () => {
        try {
          await resetPassword(userId, isRoot);
          toast.success('密码已重置为 123456');
        } catch (error: any) {
          toast.error(error.message || '重置失败');
        }
      }
    });
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <>
      <div className={styles.toolbar}>
        <span className={styles.pageInfo}>共 {total} 个用户</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`${styles.button} ${styles.buttonSecondary}`} onClick={fetchUsers}>
            <RefreshCw size={14} /> 刷新
          </button>
          <button className={styles.button} onClick={() => setShowModal(true)}>
            <Plus size={14} /> 新增用户
          </button>
        </div>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>ID</th>
            <th className={styles.th}>用户名</th>
            <th className={styles.th}>昵称</th>
            <th className={styles.th}>角色</th>
            <th className={styles.th}>状态</th>
            <th className={styles.th}>创建时间</th>
            <th className={styles.th}>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.length === 0 ? (
            <tr>
              <td colSpan={7} className={styles.empty}>
                {loading ? '加载中...' : '暂无数据'}
              </td>
            </tr>
          ) : (
            users.map((user) => (
              <tr key={user.id}>
                <td className={styles.td}>{user.id}</td>
                <td className={styles.td}>{user.username}</td>
                <td className={styles.td}>{user.nickname || '-'}</td>
                <td className={styles.td}>
                  <span className={`${styles.badge} ${user.is_root ? styles.badgeInfo : styles.badgeSuccess}`}>
                    {user.is_root ? '超级管理员' : '普通用户'}
                  </span>
                </td>
                <td className={styles.td}>
                  <span className={`${styles.badge} ${user.status === 1 ? styles.badgeSuccess : styles.badgeError}`}>
                    {user.status === 1 ? '正常' : '禁用'}
                  </span>
                </td>
                <td className={styles.td}>{new Date(user.created_at).toLocaleString('zh-CN')}</td>
                <td className={styles.td}>
                  {!user.is_root && (
                    <button
                      className={styles.actionButton}
                      onClick={() => handleResetPassword(user.id, user.username)}
                    >
                      重置密码
                    </button>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageButton}
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            上一页
          </button>
          <span className={styles.pageInfo}>
            第 {page} / {totalPages} 页
          </span>
          <button
            className={styles.pageButton}
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            下一页
          </button>
        </div>
      )}

      {showModal && (
        <CreateUserModal
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            fetchUsers();
          }}
        />
      )}
    </>
  );
}

// 创建用户弹窗
function CreateUserModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const { isRoot } = useAuth();
  const { toast } = useToast();
  const [username, setUsername] = useState('');
  const [nickname, setNickname] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username) {
      toast.warning('请输入用户名');
      return;
    }

    setLoading(true);
    try {
      await createUser({ username, nickname, password: '123456' }, isRoot);
      toast.success('用户创建成功，初始密码为 123456');
      onSuccess();
    } catch (error: any) {
      toast.error(error.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.modalTitle}>新增用户</h2>
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.inputGroup}>
            <label className={styles.label}>用户名 *</label>
            <input
              type="text"
              className={styles.input}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
            />
          </div>
          <div className={styles.inputGroup}>
            <label className={styles.label}>昵称</label>
            <input
              type="text"
              className={styles.input}
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="请输入昵称（可选）"
            />
          </div>
          <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)' }}>
            初始密码为 123456，用户登录后可自行修改
          </p>
          <div className={styles.modalActions}>
            <button
              type="button"
              className={`${styles.button} ${styles.buttonSecondary}`}
              onClick={onClose}
            >
              取消
            </button>
            <button type="submit" className={styles.button} disabled={loading}>
              {loading ? '创建中...' : '创建'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// 登录日志组件
function LoginLogs() {
  const { isRoot } = useAuth();
  const [logs, setLogs] = useState<LoginLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await getLoginLogs(page, 20, isRoot);
      setLogs(data.items || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error('获取登录日志失败', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, isRoot]);

  const totalPages = Math.ceil(total / 20);

  return (
    <>
      <div className={styles.toolbar}>
        <span className={styles.pageInfo}>共 {total} 条记录</span>
        <button className={`${styles.button} ${styles.buttonSecondary}`} onClick={fetchLogs}>
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>ID</th>
            <th className={styles.th}>用户名</th>
            <th className={styles.th}>IP地址</th>
            <th className={styles.th}>登录时间</th>
            <th className={styles.th}>状态</th>
            <th className={styles.th}>备注</th>
          </tr>
        </thead>
        <tbody>
          {logs.length === 0 ? (
            <tr>
              <td colSpan={6} className={styles.empty}>
                {loading ? '加载中...' : '暂无数据'}
              </td>
            </tr>
          ) : (
            logs.map((log) => (
              <tr key={log.id}>
                <td className={styles.td}>{log.id}</td>
                <td className={styles.td}>{log.username}</td>
                <td className={styles.td}>{log.ip_address || '-'}</td>
                <td className={styles.td}>{new Date(log.login_time).toLocaleString('zh-CN')}</td>
                <td className={styles.td}>
                  <span className={`${styles.badge} ${log.status === 1 ? styles.badgeSuccess : styles.badgeError}`}>
                    {log.status === 1 ? '成功' : '失败'}
                  </span>
                </td>
                <td className={styles.td}>{log.message || '-'}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageButton}
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            上一页
          </button>
          <span className={styles.pageInfo}>
            第 {page} / {totalPages} 页
          </span>
          <button
            className={styles.pageButton}
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            下一页
          </button>
        </div>
      )}
    </>
  );
}
