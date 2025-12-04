import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/ui/Toast';
import { changePassword } from '../../api/auth';
import * as styles from './styles.css';

export default function Profile() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { toast } = useToast();
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!oldPassword || !newPassword || !confirmPassword) {
      setMessage({ type: 'error', text: '请填写所有字段' });
      return;
    }
    
    if (newPassword.length < 6) {
      setMessage({ type: 'error', text: '新密码长度不能少于6位' });
      return;
    }
    
    if (newPassword !== confirmPassword) {
      setMessage({ type: 'error', text: '两次输入的新密码不一致' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      await changePassword(user!.id, { old_password: oldPassword, new_password: newPassword });
      toast.success('密码修改成功，请重新登录');
      // 密码修改成功后退出登录
      setTimeout(() => {
        logout();
        navigate('/login');
      }, 1500);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.message || '密码修改失败' });
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>个人中心</h1>
        <p className={styles.subtitle}>管理您的账号信息</p>
      </div>

      {/* 用户信息 */}
      <div className={styles.card}>
        <h2 className={styles.cardTitle}>基本信息</h2>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>用户名</span>
          <span className={styles.infoValue}>{user.username}</span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>昵称</span>
          <span className={styles.infoValue}>{user.nickname || '-'}</span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>角色</span>
          <span className={styles.infoValue}>{user.is_root ? '超级管理员' : '普通用户'}</span>
        </div>
        <div className={styles.infoRow}>
          <span className={styles.infoLabel}>创建时间</span>
          <span className={styles.infoValue}>
            {new Date(user.created_at).toLocaleString('zh-CN')}
          </span>
        </div>
      </div>

      {/* 修改密码 */}
      <div className={styles.card}>
        <h2 className={styles.cardTitle}>修改密码</h2>
        <form className={styles.form} onSubmit={handleChangePassword}>
          {message && (
            <div className={`${styles.message} ${message.type === 'success' ? styles.success : styles.error}`}>
              {message.text}
            </div>
          )}

          <div className={styles.inputGroup}>
            <label className={styles.label}>当前密码</label>
            <input
              type="password"
              className={styles.input}
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="请输入当前密码"
            />
          </div>

          <div className={styles.inputGroup}>
            <label className={styles.label}>新密码</label>
            <input
              type="password"
              className={styles.input}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="请输入新密码（至少6位）"
            />
          </div>

          <div className={styles.inputGroup}>
            <label className={styles.label}>确认新密码</label>
            <input
              type="password"
              className={styles.input}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="请再次输入新密码"
            />
          </div>

          <button type="submit" className={styles.button} disabled={loading}>
            {loading ? '提交中...' : '修改密码'}
          </button>
        </form>
      </div>
    </div>
  );
}
