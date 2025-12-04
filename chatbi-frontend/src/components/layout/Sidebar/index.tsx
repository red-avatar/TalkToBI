import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { LayoutDashboard, MessageSquare, Database, Network, BookOpen, History, Cloud, Wrench, ChevronLeft, ChevronRight, Settings, GitBranch } from 'lucide-react';
import { cn } from '../../../lib/utils';
import { useAuth } from '../../../contexts/AuthContext';
import * as styles from './styles.css';

interface MenuItem { key: string; icon: React.ReactNode; label: string; children?: MenuItem[]; rootOnly?: boolean; }

const menuItems: MenuItem[] = [
  { key: '/dashboard', icon: <LayoutDashboard size={20} />, label: '工作台' },
  { key: '/chat', icon: <MessageSquare size={20} />, label: '智能对话' },
  { key: 'knowledge', icon: <Database size={20} />, label: '知识库管理', children: [
    { key: '/knowledge/vectors', icon: <Network size={18} />, label: '向量数据' },
    { key: '/knowledge/terms', icon: <BookOpen size={18} />, label: '业务名词' },
    { key: '/knowledge/cache', icon: <Cloud size={18} />, label: '查询缓存' },
    { key: '/knowledge/logs', icon: <History size={18} />, label: '执行日志' },
    { key: '/knowledge/graph', icon: <GitBranch size={18} />, label: '知识图谱' },
  ]},
  { key: 'build', icon: <Wrench size={20} />, label: '知识库构建', children: [
    { key: '/build/pipeline', icon: <Cloud size={18} />, label: '构建流程' },
  ]},
  { key: '/system', icon: <Settings size={20} />, label: '系统管理', rootOnly: true },
];

interface SidebarProps { collapsed: boolean; onCollapse: (collapsed: boolean) => void; }

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onCollapse }) => {
  const { isRoot } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expandedKeys, setExpandedKeys] = React.useState<string[]>(['knowledge', 'build']);

  const isActive = (key: string) => location.pathname === key;
  const isParentActive = (item: MenuItem) => item.children?.some((child) => location.pathname === child.key);
  const toggleExpand = (key: string) => setExpandedKeys((prev) => prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]);
  const handleClick = (item: MenuItem) => { if (item.children) toggleExpand(item.key); else navigate(item.key); };

  // 过滤菜单项（非 root 用户不显示 rootOnly 项）
  const filteredMenuItems = menuItems.filter(item => !item.rootOnly || isRoot);

  return (
    <aside className={cn(styles.sidebar, collapsed && styles.collapsed)}>
      <nav className={styles.nav}>
        {filteredMenuItems.map((item) => (
          <div key={item.key}>
            <motion.button className={cn(styles.menuItem, (isActive(item.key) || isParentActive(item)) && styles.active)} onClick={() => handleClick(item)} whileHover={{ x: 4 }} whileTap={{ scale: 0.98 }}>
              <span className={styles.icon}>{item.icon}</span>
              <AnimatePresence>
                {!collapsed && <motion.span className={styles.label} initial={{ opacity: 0, width: 0 }} animate={{ opacity: 1, width: 'auto' }} exit={{ opacity: 0, width: 0 }}>{item.label}</motion.span>}
              </AnimatePresence>
              {item.children && !collapsed && <ChevronRight size={16} className={cn(styles.expandIcon, expandedKeys.includes(item.key) && styles.expanded)} />}
            </motion.button>
            <AnimatePresence>
              {item.children && expandedKeys.includes(item.key) && !collapsed && (
                <motion.div className={styles.subMenu} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
                  {item.children.map((child) => (
                    <motion.button key={child.key} className={cn(styles.subMenuItem, isActive(child.key) && styles.active)} onClick={() => navigate(child.key)} whileHover={{ x: 4 }} whileTap={{ scale: 0.98 }}>
                      <span className={styles.icon}>{child.icon}</span>
                      <span className={styles.label}>{child.label}</span>
                    </motion.button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </nav>
      <button className={styles.collapseBtn} onClick={() => onCollapse(!collapsed)}>{collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}</button>
    </aside>
  );
};

export default Sidebar;
