import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  MessageSquare,
  Database,
  Clock,
  Rocket,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  CheckCircle,
} from 'lucide-react';
import { Card, Button, Spinner, StatusIndicator } from '../../components/ui';
import { logsApi } from '../../api/logs';
import { cacheApi } from '../../api/cache';
import { vectorsApi } from '../../api/vectors';
import type { LogStats, CacheStats, VectorStats, LogEntry } from '../../api/types';
import * as styles from './styles.css';

// 工具函数：将毫秒转换为秒
const msToSeconds = (ms: number) => (ms / 1000).toFixed(2);

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logStats, setLogStats] = useState<LogStats | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [vectorStats, setVectorStats] = useState<VectorStats | null>(null);
  const [recentLogs, setRecentLogs] = useState<LogEntry[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [logRes, cacheRes, vectorRes, logsListRes] = await Promise.allSettled([
        logsApi.getStats(),
        cacheApi.getStats(),
        vectorsApi.getStats(),
        logsApi.getList({ page: 1, page_size: 100 }),
      ]);

      if (logRes.status === 'fulfilled') setLogStats(logRes.value.data);
      if (cacheRes.status === 'fulfilled') setCacheStats(cacheRes.value.data);
      if (vectorRes.status === 'fulfilled') setVectorStats(vectorRes.value.data);
      if (logsListRes.status === 'fulfilled') setRecentLogs(logsListRes.value.data.items || []);

      const allFailed = [logRes, cacheRes, vectorRes].every((r) => r.status === 'rejected');
      if (allFailed) {
        setError('无法连接后端服务，请确保后端已启动');
      }
    } catch {
      setError('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  // 基于真实日志数据生成按日提问次数统计图
  const getDailyQueryChartOption = () => {
    // 按日期分组统计提问次数
    const dailyCounts: Record<string, number> = {};
    
    recentLogs.forEach(log => {
      const date = new Date(log.created_at);
      const dateKey = date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
      dailyCounts[dateKey] = (dailyCounts[dateKey] || 0) + 1;
    });
    
    // 按日期排序
    const sortedDates = Object.keys(dailyCounts).sort((a, b) => {
      const [aMonth, aDay] = a.split('/').map(Number);
      const [bMonth, bDay] = b.split('/').map(Number);
      return aMonth !== bMonth ? aMonth - bMonth : aDay - bDay;
    });
    
    const dateLabels = sortedDates;
    const counts = sortedDates.map(date => dailyCounts[date]);
    
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(18, 18, 26, 0.9)',
        borderColor: 'rgba(0, 245, 255, 0.3)',
        textStyle: { color: '#fff' },
        formatter: (params: any) => {
          const p = params[0];
          return `${p.name}<br/>${p.seriesName}: ${p.value} 次`;
        },
      },
      grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dateLabels.length > 0 ? dateLabels : ['暂无数据'],
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)', rotate: 0, fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        name: '提问次数',
        nameTextStyle: { color: 'rgba(255,255,255,0.5)' },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: 'rgba(255,255,255,0.5)' },
        minInterval: 1,
      },
      series: [{
        name: '提问次数',
        type: 'line',
        smooth: true,
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0, 245, 255, 0.3)' },
              { offset: 1, color: 'rgba(0, 245, 255, 0)' },
            ],
          },
        },
        lineStyle: { color: '#00F5FF', width: 2 },
        itemStyle: { color: '#00F5FF' },
        data: counts.length > 0 ? counts : [0],
      }],
    };
  };

  const getSuccessRateOption = () => {
    const success = logStats?.success_count ?? 0;
    const errorCount = logStats?.error_count ?? 0;
    const timeout = logStats?.timeout_count ?? 0;
    const total = success + errorCount + timeout;
    const successRate = logStats?.success_rate ?? (total > 0 ? (success / total) * 100 : 0);

    const data = [];
    if (success > 0) data.push({ value: success, name: `成功 (${success})`, itemStyle: { color: '#00FF88' } });
    if (errorCount > 0) data.push({ value: errorCount, name: `失败 (${errorCount})`, itemStyle: { color: '#FF3366' } });
    if (timeout > 0) data.push({ value: timeout, name: `超时 (${timeout})`, itemStyle: { color: '#FFB800' } });
    if (total === 0) data.push({ value: 1, name: '', itemStyle: { color: 'rgba(255,255,255,0.05)' } });

    return {
      backgroundColor: 'transparent',
      tooltip: total > 0 ? {
        trigger: 'item',
        backgroundColor: 'rgba(18, 18, 26, 0.9)',
        borderColor: 'rgba(0, 245, 255, 0.3)',
        textStyle: { color: '#fff' },
        formatter: '{b}: {c} ({d}%)',
      } : undefined,
      legend: total > 0 ? {
        bottom: '5%',
        left: 'center',
        textStyle: { color: 'rgba(255,255,255,0.6)' },
      } : undefined,
      title: {
        text: total > 0 ? `${successRate.toFixed(1)}%` : '暂无数据',
        subtext: total > 0 ? '成功率' : '',
        left: 'center',
        top: 'center',
        textStyle: {
          fontSize: total > 0 ? 28 : 14,
          fontWeight: 'bold',
          color: total > 0 ? '#00FF88' : 'rgba(255,255,255,0.3)',
        },
        subtextStyle: {
          fontSize: 12,
          color: 'rgba(255,255,255,0.5)',
        },
      },
      series: [{
        type: 'pie',
        radius: ['55%', '75%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#0a0a0f', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: false } },
        silent: total === 0,
        data,
      }],
    };
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 },
  };

  return (
    <motion.div className={styles.container} variants={containerVariants} initial="hidden" animate="show">
      {/* Welcome banner */}
      <motion.div variants={itemVariants}>
        <Card variant="glow" padding="lg" className={styles.welcomeCard}>
          <div className={styles.welcomeContent}>
            <div>
              <h1 className={styles.welcomeTitle}>欢迎使用 TalktoBI</h1>
              <p className={styles.welcomeDesc}>智能对话式商业智能分析平台，让数据分析变得简单自然</p>
            </div>
            <Button size="lg" leftIcon={<Rocket size={20} />} onClick={() => navigate('/chat')}>
              开始对话
            </Button>
          </div>
        </Card>
      </motion.div>

      {/* Error alert */}
      {error && (
        <motion.div variants={itemVariants}>
          <Card variant="bordered" padding="md" className={styles.errorCard}>
            <div className={styles.errorContent}>
              <AlertCircle size={20} />
              <span>{error}</span>
              <Button variant="ghost" size="sm" leftIcon={<RefreshCw size={16} />} onClick={loadData}>
                重试
              </Button>
            </div>
          </Card>
        </motion.div>
      )}

      {/* System status */}
      <motion.div variants={itemVariants}>
        <Card variant="glass" padding="md">
          <div className={styles.sectionHeader}>
            <h3 className={styles.sectionTitle}>系统状态</h3>
            <Button variant="ghost" size="sm" leftIcon={loading ? <Spinner size="sm" /> : <RefreshCw size={16} />} onClick={loadData} disabled={loading}>
              刷新
            </Button>
          </div>
          <div className={styles.statusGrid}>
            <StatusIndicator status={logStats ? 'online' : 'offline'} label="执行日志" />
            <StatusIndicator status={vectorStats ? 'online' : 'offline'} label="向量存储" />
            <StatusIndicator status={cacheStats ? 'online' : 'offline'} label="查询缓存" />
          </div>
        </Card>
      </motion.div>

      {/* Stats cards */}
      <motion.div className={styles.statsGrid} variants={itemVariants}>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 245, 255, 0.1)' }}>
            <MessageSquare size={24} color="#00F5FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>总查询数</span>
            <span className={styles.statValue}>{loading ? '-' : logStats?.total ?? 0}</span>
          </div>
        </Card>

        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 255, 136, 0.1)' }}>
            <CheckCircle size={24} color="#00FF88" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>查询成功率</span>
            <span className={styles.statValue}>
              {loading ? '-' : logStats?.success_rate != null ? `${logStats.success_rate.toFixed(1)}%` : '-'}
            </span>
          </div>
        </Card>

        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(189, 0, 255, 0.1)' }}>
            <Database size={24} color="#BD00FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>向量数量</span>
            <span className={styles.statValue}>{loading ? '-' : vectorStats?.total ?? 0}</span>
          </div>
        </Card>

        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(255, 184, 0, 0.1)' }}>
            <Clock size={24} color="#FFB800" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>平均响应</span>
            <span className={styles.statValue}>
              {loading ? '-' : logStats?.avg_execution_time_ms != null ? `${msToSeconds(logStats.avg_execution_time_ms)}s` : '-'}
            </span>
          </div>
        </Card>
      </motion.div>

      {/* Charts */}
      <motion.div className={styles.chartsGrid} variants={itemVariants}>
        <Card variant="glass" padding="md" className={styles.chartCard}>
          <h3 className={styles.chartTitle}>
            <TrendingUp size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />
            每日提问次数统计
          </h3>
          <ReactECharts option={getDailyQueryChartOption()} style={{ height: 280 }} />
        </Card>

        <Card variant="glass" padding="md" className={styles.chartCard}>
          <h3 className={styles.chartTitle}>查询成功率</h3>
          <ReactECharts option={getSuccessRateOption()} style={{ height: 280 }} />
        </Card>
      </motion.div>
    </motion.div>
  );
};

export default Dashboard;
