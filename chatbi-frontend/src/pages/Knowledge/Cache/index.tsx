import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Cloud, RefreshCw, Search, ChevronLeft, ChevronRight, Trash2, Database, Zap, Activity, Target } from 'lucide-react';
import { Card, Button, Spinner } from '../../../components/ui';
import { cacheApi } from '../../../api/cache';
import type { CacheEntry, CacheStats } from '../../../api/types';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

const PAGE_SIZE = 15;
const formatTime = (iso: string) => new Date(iso).toLocaleString('zh-CN');

const Cache: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [caches, setCaches] = useState<CacheEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<'all' | 'active' | 'invalid' | 'deprecated'>('all');
  const [keyword, setKeyword] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, listRes] = await Promise.allSettled([
        cacheApi.getStats(),
        cacheApi.getList({ page, page_size: PAGE_SIZE, status: filter === 'all' ? undefined : filter, keyword: keyword || undefined }),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      if (listRes.status === 'fulfilled') { setCaches(listRes.value.data.items || []); setTotal(listRes.value.data.total || 0); }
    } finally { setLoading(false); }
  }, [page, filter, keyword]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除该缓存？')) return;
    try { await cacheApi.delete(id); loadData(); } catch (e) { console.error(e); }
  };

  const handleStatusChange = async (id: number, status: 'active' | 'invalid' | 'deprecated') => {
    try { await cacheApi.updateStatus(id, status); loadData(); } catch (e) { console.error(e); }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const statusMap = { active: { label: '有效', style: styles.statusActive }, invalid: { label: '无效', style: styles.statusInvalid }, deprecated: { label: '废弃', style: styles.statusDeprecated } };

  return (
    <motion.div className={styles.container} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Cloud size={28} color="#00FF88" />
          <h1 className={styles.title}>查询缓存</h1>
        </div>
        <Button variant="ghost" size="sm" leftIcon={loading ? <Spinner size="sm" /> : <RefreshCw size={16} />} onClick={loadData} disabled={loading}>刷新</Button>
      </div>

      <div className={styles.statsGrid}>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 255, 136, 0.1)' }}><Database size={24} color="#00FF88" /></div>
          <div className={styles.statContent}><span className={styles.statLabel}>总缓存</span><span className={styles.statValue}>{stats?.total ?? '-'}</span></div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 245, 255, 0.1)' }}><Activity size={24} color="#00F5FF" /></div>
          <div className={styles.statContent}><span className={styles.statLabel}>有效缓存</span><span className={styles.statValue}>{stats?.active ?? '-'}</span></div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(255, 184, 0, 0.1)' }}><Zap size={24} color="#FFB800" /></div>
          <div className={styles.statContent}><span className={styles.statLabel}>总命中次数</span><span className={styles.statValue}>{stats?.total_hits ?? '-'}</span></div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(189, 0, 255, 0.1)' }}><Target size={24} color="#BD00FF" /></div>
          <div className={styles.statContent}><span className={styles.statLabel}>平均评分</span><span className={styles.statValue}>{stats?.avg_score?.toFixed(1) ?? '-'}</span></div>
        </Card>
      </div>

      <Card variant="glass" padding="md">
        <div className={styles.toolbar}>
          <div className={styles.filters}>
            {(['all', 'active', 'invalid', 'deprecated'] as const).map((f) => (
              <button key={f} className={cn(styles.filterButton, filter === f && styles.filterButtonActive)} onClick={() => { setFilter(f); setPage(1); }}>
                {f === 'all' ? '全部' : statusMap[f].label}
              </button>
            ))}
          </div>
          <div className={styles.filters}>
            <Search size={16} color="rgba(255,255,255,0.4)" />
            <input className={styles.searchInput} placeholder="搜索查询..." value={keyword} onChange={(e) => setKeyword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && loadData()} />
          </div>
        </div>
      </Card>

      <Card variant="glass" padding="md">
        {loading ? (<div className={styles.emptyState}><Spinner size="lg" /></div>) : caches.length === 0 ? (
          <div className={styles.emptyState}><Cloud size={48} color="rgba(255,255,255,0.2)" /><p>暂无缓存数据</p></div>
        ) : (
          <>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead><tr><th>ID</th><th>原始查询</th><th>SQL</th><th>评分</th><th>命中</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
                <tbody>
                  {caches.map((c) => (
                    <tr key={c.id}>
                      <td>{c.id}</td>
                      <td className={styles.queryCell} title={c.original_query}>{c.original_query}</td>
                      <td className={styles.sqlCell} title={c.sql}>{c.sql}</td>
                      <td className={styles.scoreCell}>{c.cache_score}</td>
                      <td>{c.hit_count}</td>
                      <td>
                        <select value={c.status} onChange={(e) => handleStatusChange(c.id, e.target.value as any)} style={{ background: 'transparent', border: 'none', cursor: 'pointer' }} className={cn(styles.statusBadge, statusMap[c.status].style)}>
                          <option value="active">有效</option>
                          <option value="invalid">无效</option>
                          <option value="deprecated">废弃</option>
                        </select>
                      </td>
                      <td>{formatTime(c.created_at)}</td>
                      <td><Button variant="ghost" size="sm" leftIcon={<Trash2 size={14} />} onClick={() => handleDelete(c.id)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className={styles.pagination}>
              <span className={styles.pageInfo}>共 {total} 条，第 {page}/{totalPages} 页</span>
              <Button variant="ghost" size="sm" leftIcon={<ChevronLeft size={16} />} onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>上一页</Button>
              <Button variant="ghost" size="sm" rightIcon={<ChevronRight size={16} />} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>下一页</Button>
            </div>
          </>
        )}
      </Card>
    </motion.div>
  );
};

export default Cache;
