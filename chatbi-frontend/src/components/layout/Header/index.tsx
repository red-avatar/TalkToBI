import React from 'react';
import { useNavigate } from 'react-router-dom';
import { User, LogOut, Sparkles } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { cn } from '../../../lib/utils';
import { useAuth } from '../../../contexts/AuthContext';
import * as styles from './styles.css';

export const Header: React.FC<{ className?: string }> = ({ className }) => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className={cn(styles.header, className)}>
      <div className={styles.logoSection} onClick={() => navigate('/dashboard')}>
        <div className={styles.logoIcon}><Sparkles size={20} /></div>
        <div className={styles.logoText}>
          <span className={styles.logoTitle}>TalktoBI</span>
          <span className={styles.logoSubtitle}>AI Assistant</span>
        </div>
      </div>
      <div className={styles.center}><span className={styles.tagline}>智能对话式 BI 平台</span></div>
      <div className={styles.rightSection}>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button className={styles.userButton}>
              <div className={styles.avatar}><User size={18} /></div>
              <span className={styles.userName}>{user?.nickname || user?.username || '用户'}</span>
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content className={styles.dropdownContent} sideOffset={4} align="end" alignOffset={0}>
              <DropdownMenu.Item className={styles.dropdownItem} onClick={() => navigate('/profile')}>
                <User size={16} /><span>个人中心</span>
              </DropdownMenu.Item>
              <DropdownMenu.Separator className={styles.dropdownSeparator} />
              <DropdownMenu.Item className={styles.dropdownItem} onClick={handleLogout}>
                <LogOut size={16} /><span>退出登录</span>
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  );
};

export default Header;
