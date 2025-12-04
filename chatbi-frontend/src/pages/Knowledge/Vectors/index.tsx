import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Network, Table2, Columns, RefreshCw, Search, ChevronLeft, ChevronRight, Database } from 'lucide-react';
import { Card, Button, Spinner } from '../../../components/ui';
import { vectorsApi } from '../../../api/vectors';
import type { VectorEntry, VectorStats } from '../../../api/types';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';

const PAGE_SIZE = 15;

const Vectors: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<VectorStats | null>(null);
  const [vectors, setVectors] = useState<VectorEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<'all' | 'table' | 'column'>('all');
  const [keyword, setKeyword] = useState('');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, listRes] = await Promise.allSettled([
        vectorsApi.getStats(),
        vectorsApi.getList({
          page,
          page_size: PAGE_SIZE,
          object_type: filter === 'all' ? undefined : filter,
          keyword: keyword || undefined,
        }),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      if (listRes.status === 'fulfilled') {
        setVectors(listRes.value.data.items || []);
        setTotal(listRes.value.data.total || 0);
      }
    } finally {
      setLoading(false);
    }
  }, [page, filter, keyword]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <motion.div className={styles.container} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Network size={28} color="#00F5FF" />
          <h1 className={styles.title}>向量数据</h1>
        </div>
        <Button variant="ghost" size="sm" leftIcon={loading ? <Spinner size="sm" /> : <RefreshCw size={16} />} onClick={loadData} disabled={loading}>
          刷新
        </Button>
      </div>

      {/* Stats */}
      <div className={styles.statsGrid}>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 245, 255, 0.1)' }}>
            <Database size={24} color="#00F5FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>总向量数</span>
            <span className={styles.statValue}>{loading ? '-' : stats?.total ?? 0}</span>
          </div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 245, 255, 0.1)' }}>
            <Table2 size={24} color="#00F5FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>表向量</span>
            <span className={styles.statValue}>{loading ? '-' : stats?.table_count ?? 0}</span>
          </div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(189, 0, 255, 0.1)' }}>
            <Columns size={24} color="#BD00FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>列向量</span>
            <span className={styles.statValue}>{loading ? '-' : stats?.column_count ?? 0}</span>
          </div>
        </Card>
      </div>

      {/* Toolbar */}
      <Card variant="glass" padding="md">
        <div className={styles.toolbar}>
          <div className={styles.filters}>
            <button className={cn(styles.filterButton, filter === 'all' && styles.filterButtonActive)} onClick={() => { setFilter('all'); setPage(1); }}>全部</button>
            <button className={cn(styles.filterButton, filter === 'table' && styles.filterButtonActive)} onClick={() => { setFilter('table'); setPage(1); }}>表</button>
            <button className={cn(styles.filterButton, filter === 'column' && styles.filterButtonActive)} onClick={() => { setFilter('column'); setPage(1); }}>列</button>
          </div>
          <div className={styles.filters}>
            <Search size={16} color="rgba(255,255,255,0.4)" />
            <input
              className={styles.searchInput}
              placeholder="搜索对象名称..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadData()}
            />
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card variant="glass" padding="md">
        {loading ? (
          <div className={styles.emptyState}><Spinner size="lg" /></div>
        ) : vectors.length === 0 ? (
          <div className={styles.emptyState}>
            <Network size={48} color="rgba(255,255,255,0.2)" />
            <p>暂无向量数据</p>
          </div>
        ) : (
          <>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>类型</th>
                    <th>对象名称</th>
                    <th>原始描述</th>
                    <th>增强描述</th>
                    <th>维度</th>
                  </tr>
                </thead>
                <tbody>
                  {vectors.map((v) => (
                    <tr key={v.id}>
                      <td>{v.id}</td>
                      <td>
                        <span className={cn(styles.typeBadge, v.object_type === 'table' ? styles.typeTable : styles.typeColumn)}>
                          {v.object_type === 'table' ? '表' : '列'}
                        </span>
                      </td>
                      <td>{v.object_name}</td>
                      <td className={styles.descriptionCell} title={v.original_description}>{v.original_description}</td>
                      <td className={styles.descriptionCell} title={v.enriched_description}>{v.enriched_description}</td>
                      <td>{v.embedding_dim}</td>
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

export default Vectors;
