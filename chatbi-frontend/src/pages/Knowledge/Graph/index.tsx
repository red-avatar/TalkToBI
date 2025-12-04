/**
 * 知识图谱编辑器
 * Author: 陈怡坚
 * Time: 2025-12-03
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network,
  Table2,
  Link,
  Sparkles,
  Upload,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  Key,
  List,
  GitBranch,
  X,
  Maximize2,
  Minimize2,
  ArrowRight,
} from 'lucide-react';
import { Card, Button, Spinner } from '../../../components/ui';
import { useToast } from '../../../components/ui/Toast';
import { graphApi } from '../../../api/graph';
import type { TableSchema, GraphRelationship, ColumnSchema } from '../../../api/types';
import { cn } from '../../../lib/utils';
import * as styles from './styles.css';
import RelationshipGraph from './RelationshipGraph';
import CustomSelect from './CustomSelect';
import type { SelectOption } from './CustomSelect';

/** 关系类型选项 - 与后端schemas.py一致 */
const JOIN_TYPES = [
  { value: 'FOREIGN_KEY', label: '外键关系', desc: 'DDL中定义了FK约束' },
  { value: 'LOGICAL', label: '逻辑关联', desc: '无FK约束，但字段逻辑上可关联' },
  { value: 'SEMANTIC', label: '语义关联', desc: '基于业务含义的关联' },
];

/** 视图类型 */
type ViewMode = 'list' | 'graph';

const Graph: React.FC = () => {
  const { toast, confirm } = useToast();
  
  // 加载状态
  const [loading, setLoading] = useState(true);
  const [inferring, setInferring] = useState(false);
  const [syncing, setSyncing] = useState(false);

  // 数据
  const [tables, setTables] = useState<TableSchema[]>([]);
  const [relationships, setRelationships] = useState<GraphRelationship[]>([]);
  const [hasChanges, setHasChanges] = useState(false);

  // 选中状态
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [selectedRelIndex, setSelectedRelIndex] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);  // 选中的节点
  const [tableSearch, setTableSearch] = useState('');

  // 视图模式
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [isFullscreen, setIsFullscreen] = useState(false);  // 全屏模式

  // 防抖保存定时器
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 添加关系弹窗
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRel, setNewRel] = useState<{
    sourceTable: string;
    sourceColumn: string;
    targetTable: string;
    targetColumn: string;
    joinType: string;
    description: string;
    confidence: number;
  }>({
    sourceTable: '',
    sourceColumn: '',
    targetTable: '',
    targetColumn: '',
    joinType: 'FOREIGN_KEY',
    description: '',
    confidence: 0.9,
  });

  /** 加载元数据和关系 */
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // 并行加载：优先读取缓存的Schema + 本地关系
      const [schemaRes, relRes] = await Promise.allSettled([
        graphApi.getSavedSchema(),
        graphApi.getLocalRelationships(),
      ]);

      // 处理Schema：优先使用缓存，fallback到实时提取
      let tablesLoaded = false;
      if (schemaRes.status === 'fulfilled' && schemaRes.value.data?.tables) {
        // 使用已保存的 full_schema.json（秒级响应）
        setTables(schemaRes.value.data.tables);
        tablesLoaded = true;
      }
      
      if (!tablesLoaded) {
        // fallback: 实时从MySQL提取（较慢）
        try {
          const metaRes = await graphApi.getMetadata();
          setTables(metaRes.data || []);
        } catch (err) {
          console.error('Failed to fetch metadata:', err);
          setTables([]);
        }
      }

      // 处理关系
      if (relRes.status === 'fulfilled') {
        setRelationships(relRes.value.data || []);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /** LLM推断生成关系 */
  const handleInfer = async () => {
    confirm({
      title: 'LLM 推断关系',
      message: '将使用 LLM 推断表关系，可能覆盖现有数据，是否继续？',
      confirmText: '开始推断',
      danger: false,
      onConfirm: async () => {
        setInferring(true);
        try {
          const res = await graphApi.inferRelationships();
          if (res.data.success) {
            await graphApi.saveLocalRelationships(res.data.relationships);
            toast.success(`推断完成！生成了 ${res.data.relationships.length} 条关系`);
            await loadData();
          } else {
            toast.error('推断失败');
          }
        } catch (err: any) {
          toast.error(err.message || '推断失败');
        } finally {
          setInferring(false);
        }
      },
    });
  };

  /** 同步到Neo4j */
  const handleSync = async () => {
    confirm({
      title: '同步到 Neo4j',
      message: '将同步当前数据到 Neo4j 图数据库，这会清空并重建图谱，是否继续？',
      confirmText: '开始同步',
      danger: false,
      onConfirm: async () => {
        setSyncing(true);
        try {
          const res = await graphApi.syncToNeo4j();
          if (res.data.success) {
            toast.success(`同步成功！创建了 ${res.data.tables_count} 个表节点，${res.data.relations_count} 条关系`);
          } else {
            toast.error('同步失败');
          }
        } catch (err: any) {
          toast.error(err.message || '同步失败');
        } finally {
          setSyncing(false);
        }
      },
    });
  };

  /** 切换表展开 */
  const toggleTable = (tableName: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) next.delete(tableName);
      else next.add(tableName);
      return next;
    });
  };

  /** 打开添加关系弹窗 */
  const handleOpenAddModal = () => {
    setNewRel({
      sourceTable: tables[0]?.name || '',
      sourceColumn: '',
      targetTable: tables[1]?.name || '',
      targetColumn: '',
      joinType: 'FOREIGN_KEY',
      description: '',
      confidence: 0.9,
    });
    setShowAddModal(true);
  };

  /** 确认添加关系（添加后自动保存） */
  const handleConfirmAdd = async () => {
    if (!newRel.sourceTable || !newRel.targetTable) {
      toast.warning('请选择源表和目标表');
      return;
    }
    if (!newRel.sourceColumn || !newRel.targetColumn) {
      toast.warning('请选择源字段和目标字段');
      return;
    }
    const rel: GraphRelationship = {
      source: newRel.sourceTable,
      target: newRel.targetTable,
      type: 'JOIN_ON',
      properties: {
        condition: `${newRel.sourceTable}.${newRel.sourceColumn} = ${newRel.targetTable}.${newRel.targetColumn}`,
        confidence: newRel.confidence,
        join_type: newRel.joinType,
        description: newRel.description,
      },
    };
    const newRelationships = [...relationships, rel];
    setRelationships(newRelationships);
    setSelectedRelIndex(relationships.length);
    setShowAddModal(false);
    
    // 自动保存到本地
    try {
      await graphApi.saveLocalRelationships(newRelationships);
      toast.success(`已添加并保存: ${newRel.sourceTable} → ${newRel.targetTable}`);
      setHasChanges(false);
    } catch (err: any) {
      toast.error(err.message || '保存失败');
      setHasChanges(true);
    }
  };

  /** 获取表的列 */
  const getTableColumns = (tableName: string): ColumnSchema[] => {
    const table = tables.find(t => t.name === tableName);
    return table?.columns || [];
  };

  /** 生成表选项 */
  const tableOptions: SelectOption[] = tables.map((t) => ({
    value: t.name,
    label: t.name + (t.comment ? ` (${t.comment})` : ''),
  }));

  /** 生成字段选项 */
  const getColumnOptions = (tableName: string): SelectOption[] => {
    return getTableColumns(tableName).map((col) => ({
      value: col.name,
      label: `${col.name} (${col.data_type})${col.comment ? ` - ${col.comment}` : ''}`,
    }));
  };

  /** 关系类型选项 */
  const joinTypeOptions: SelectOption[] = JOIN_TYPES.map((type) => ({
    value: type.value,
    label: `${type.label} - ${type.desc}`,
  }));

  /** 删除关系（删除后自动保存） */
  const handleDeleteRelationship = (index: number) => {
    const rel = relationships[index];
    confirm({
      title: '删除关系',
      message: `确定删除关系 "${rel.source} → ${rel.target}" 吗？`,
      confirmText: '删除',
      danger: true,
      onConfirm: async () => {
        const newRelationships = relationships.filter((_, i) => i !== index);
        setRelationships(newRelationships);
        if (selectedRelIndex === index) setSelectedRelIndex(null);
        else if (selectedRelIndex !== null && selectedRelIndex > index) {
          setSelectedRelIndex(selectedRelIndex - 1);
        }
        // 自动保存
        try {
          await graphApi.saveLocalRelationships(newRelationships);
          toast.success('关系已删除并保存');
          setHasChanges(false);
        } catch (err: any) {
          toast.error(err.message || '保存失败');
          setHasChanges(true);
        }
      },
    });
  };

  /** 更新关系属性的properties（带防抖自动保存） */
  const updateRelationshipProps = (index: number, propUpdates: Partial<GraphRelationship['properties']>) => {
    setRelationships((prev) => {
      const newRelationships = prev.map((rel, i) =>
        i === index
          ? { ...rel, properties: { ...rel.properties, ...propUpdates } }
          : rel
      );
      
      // 防抖保存（1秒后自动保存）
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = setTimeout(async () => {
        try {
          await graphApi.saveLocalRelationships(newRelationships);
          setHasChanges(false);
          toast.success('自动保存成功');
        } catch (err: any) {
          toast.error(err.message || '自动保存失败');
          setHasChanges(true);
        }
      }, 1000);
      
      return newRelationships;
    });
    setHasChanges(true);
  };

  // 过滤表
  const filteredTables = tables.filter(
    (t) =>
      t.name.toLowerCase().includes(tableSearch.toLowerCase()) ||
      t.comment?.toLowerCase().includes(tableSearch.toLowerCase())
  );

  const selectedRel = selectedRelIndex !== null ? relationships[selectedRelIndex] : null;

  // 计算选中节点的所有相关关系
  const nodeRelationships = selectedNode
    ? relationships
        .map((rel, index) => ({ rel, index }))
        .filter(({ rel }) => rel.source === selectedNode || rel.target === selectedNode)
    : [];

  // 选中节点时高亮的关系索引集合
  const highlightedRelIndices = new Set(nodeRelationships.map(({ index }) => index));

  /** 处理节点点击 */
  const handleNodeSelect = (tableName: string) => {
    setSelectedNode(tableName === selectedNode ? null : tableName);
    setSelectedRelIndex(null);
  };

  return (
    <motion.div className={styles.container} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Network size={28} color="#00F5FF" />
          <h1 className={styles.title}>知识图谱</h1>
        </div>
        <div className={styles.headerActions}>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={inferring ? <Spinner size="sm" /> : <Sparkles size={16} />}
            onClick={handleInfer}
            disabled={inferring || loading}
          >
            LLM推断
          </Button>
          <Button
            variant="primary"
            size="sm"
            leftIcon={syncing ? <Spinner size="sm" /> : <Upload size={16} />}
            onClick={handleSync}
            disabled={syncing || loading}
          >
            同步到Neo4j
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className={styles.statsGrid}>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 245, 255, 0.1)' }}>
            <Table2 size={24} color="#00F5FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>数据表</span>
            <span className={styles.statValue}>{loading ? '-' : tables.length}</span>
          </div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(189, 0, 255, 0.1)' }}>
            <Link size={24} color="#BD00FF" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>关系数</span>
            <span className={styles.statValue}>{loading ? '-' : relationships.length}</span>
          </div>
        </Card>
        <Card variant="glass" hoverable className={styles.statCard}>
          <div className={styles.statIcon} style={{ background: 'rgba(0, 255, 136, 0.1)' }}>
            <Network size={24} color="#00FF88" />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>状态</span>
            <span className={styles.statValue}>{hasChanges ? '已修改' : '已保存'}</span>
          </div>
        </Card>
      </div>

      {/* 三栏编辑区 */}
      <div className={styles.editorWrapper}>
        {/* 左侧：DDL面板 */}
        <Card variant="glass" padding="md" className={styles.ddlPanel}>
          <div className={styles.panelTitle}>数据表结构</div>
          <input
            className={styles.searchInput}
            placeholder="搜索表名..."
            value={tableSearch}
            onChange={(e) => setTableSearch(e.target.value)}
          />
          {loading ? (
            <div className={styles.emptyState}>
              <Spinner size="lg" />
            </div>
          ) : (
            <div className={styles.tableList}>
              {filteredTables.map((table) => (
                <div
                  key={table.name}
                  className={cn(
                    styles.tableItem,
                    expandedTables.has(table.name) && styles.tableItemActive
                  )}
                  onClick={() => toggleTable(table.name)}
                >
                  <div className={styles.tableName}>
                    {expandedTables.has(table.name) ? (
                      <ChevronDown size={14} />
                    ) : (
                      <ChevronRight size={14} />
                    )}
                    <Table2 size={14} />
                    {table.name}
                  </div>
                  {table.comment && (
                    <div className={styles.tableComment}>{table.comment}</div>
                  )}
                  {expandedTables.has(table.name) && (
                    <div className={styles.columnList}>
                      {table.columns.map((col) => (
                        <div key={col.name} className={styles.columnItem}>
                          {col.is_primary_key && <Key size={10} color="#00F5FF" />}
                          <span>{col.name}</span>
                          <span className={styles.columnType}>{col.data_type}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* 中间：关系视图 */}
        <Card variant="glass" padding="md" className={styles.canvasPanel}>
          <div className={styles.canvasToolbar}>
            <div className={styles.canvasTools}>
              <span className={styles.panelTitle}>表关系 ({relationships.length})</span>
              {/* 视图切换 */}
              <button
                className={cn(styles.toolButton, viewMode === 'list' && styles.toolButtonActive)}
                onClick={() => setViewMode('list')}
                title="列表视图"
              >
                <List size={16} />
              </button>
              <button
                className={cn(styles.toolButton, viewMode === 'graph' && styles.toolButtonActive)}
                onClick={() => setViewMode('graph')}
                title="图形视图"
              >
                <GitBranch size={16} />
              </button>
            </div>
            <Button variant="ghost" size="sm" leftIcon={<Plus size={14} />} onClick={handleOpenAddModal}>
              添加关系
            </Button>
          </div>
          {loading ? (
            <div className={styles.emptyState}>
              <Spinner size="lg" />
            </div>
          ) : relationships.length === 0 ? (
            <div className={styles.emptyState}>
              <Network size={48} color="rgba(255,255,255,0.2)" />
              <p>暂无关系数据</p>
              <p style={{ fontSize: '12px' }}>点击"LLM推断"自动生成，或手动添加</p>
            </div>
          ) : viewMode === 'list' ? (
            /* 列表视图 */
            <div className={styles.relationshipList}>
              {relationships.map((rel, index) => (
                <div
                  key={index}
                  className={cn(
                    styles.relationshipItem,
                    selectedRelIndex === index && styles.relationshipItemActive
                  )}
                  onClick={() => setSelectedRelIndex(index)}
                >
                  <Link size={14} color="#00F5FF" />
                  <span className={styles.relationshipPath}>
                    {rel.source} → {rel.target}
                  </span>
                  <span className={styles.relationshipType}>{rel.properties.join_type}</span>
                  <button
                    className={styles.deleteButton}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteRelationship(index);
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            /* 图形视图 - React Flow */
            <>
              <RelationshipGraph
                relationships={relationships}
                selectedNode={selectedNode}
                highlightedIndices={highlightedRelIndices}
                onNodeSelect={handleNodeSelect}
              />
              {/* 全屏按钮 */}
              <button
                className={styles.fullscreenButton}
                onClick={() => setIsFullscreen(true)}
                title="全屏查看"
              >
                <Maximize2 size={18} />
              </button>
            </>
          )}
        </Card>

        {/* 右侧：关系面板 */}
        <Card variant="glass" padding="md" className={styles.propertyPanel}>
          <div className={styles.panelTitle}>
            {selectedNode ? `${selectedNode} 的关系 (${nodeRelationships.length})` : '关系详情'}
          </div>
          {!selectedNode && selectedRel === null ? (
            <div className={styles.propertyEmpty}>
              <Link size={32} color="rgba(255,255,255,0.2)" />
              <p>点击图中节点查看关系</p>
            </div>
          ) : selectedNode ? (
            /* 显示选中节点的所有关系 */
            <div className={styles.nodeRelationsList}>
              {nodeRelationships.length === 0 ? (
                <div className={styles.propertyEmpty}>
                  <p>该表没有关联关系</p>
                </div>
              ) : (
                nodeRelationships.map(({ rel, index }) => (
                  <div
                    key={index}
                    className={cn(
                      styles.nodeRelationItem,
                      selectedRelIndex === index && styles.nodeRelationItemActive
                    )}
                    onClick={() => setSelectedRelIndex(selectedRelIndex === index ? null : index)}
                  >
                    <div className={styles.nodeRelationHeader}>
                      <span className={styles.nodeRelationDirection}>
                        {rel.source === selectedNode ? '出' : '入'}
                      </span>
                      <ArrowRight size={14} />
                      <span className={styles.nodeRelationTarget}>
                        {rel.source === selectedNode ? rel.target : rel.source}
                      </span>
                    </div>
                    <div className={styles.nodeRelationInfo}>
                      <span className={styles.nodeRelationType}>{rel.properties.join_type}</span>
                      {rel.properties.description && (
                        <span className={styles.nodeRelationDesc}>{rel.properties.description}</span>
                      )}
                    </div>
                    <div className={styles.nodeRelationCondition}>
                      {rel.properties.condition}
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            /* 单条关系编辑 */
            <div className={styles.propertyForm}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>JOIN条件</label>
                <input
                  className={styles.formInput}
                  value={selectedRel!.properties.condition}
                  onChange={(e) =>
                    updateRelationshipProps(selectedRelIndex!, { condition: e.target.value })
                  }
                  placeholder="例: orders.user_id = users.id"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>关系类型</label>
                <CustomSelect
                  value={selectedRel!.properties.join_type}
                  onChange={(v) => updateRelationshipProps(selectedRelIndex!, { join_type: v })}
                  options={JOIN_TYPES.map((type) => ({ value: type.value, label: type.label }))}
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>描述</label>
                <textarea
                  className={styles.formTextarea}
                  value={selectedRel!.properties.description}
                  onChange={(e) =>
                    updateRelationshipProps(selectedRelIndex!, { description: e.target.value })
                  }
                  placeholder="关系描述..."
                />
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* 全屏模式 */}
      <AnimatePresence>
        {isFullscreen && (
          <motion.div
            className={styles.fullscreenOverlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className={styles.fullscreenContainer}>
              <div className={styles.fullscreenHeader}>
                <h2 className={styles.fullscreenTitle}>
                  <Network size={24} color="#00F5FF" />
                  知识图谱 - 全屏视图
                  <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.5)', fontWeight: 400 }}>
                    {tables.length} 张表 · {relationships.length} 个关系
                  </span>
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<Minimize2 size={18} />}
                  onClick={() => setIsFullscreen(false)}
                >
                  退出全屏
                </Button>
              </div>
              <div className={styles.fullscreenContent}>
                <div className={styles.fullscreenGraph}>
                  <RelationshipGraph
                    relationships={relationships}
                    selectedNode={selectedNode}
                    highlightedIndices={highlightedRelIndices}
                    onNodeSelect={handleNodeSelect}
                  />
                </div>
                <div className={styles.fullscreenSidebar}>
                  {/* 选中节点的关系 */}
                  {selectedNode && (
                    <Card variant="glass" padding="md" className={styles.fullscreenPanel}>
                      <div className={styles.panelTitle}>
                        {selectedNode} 的关系 ({nodeRelationships.length})
                      </div>
                      {nodeRelationships.length > 0 ? (
                        <div className={styles.nodeRelationsList}>
                          {nodeRelationships.map(({ rel, index }) => (
                            <div key={index} className={styles.nodeRelationItem}>
                              <div className={styles.nodeRelationHeader}>
                                <span className={styles.nodeRelationDirection}>
                                  {rel.source === selectedNode ? '出' : '入'}
                                </span>
                                <ArrowRight size={14} />
                                <span className={styles.nodeRelationTarget}>
                                  {rel.source === selectedNode ? rel.target : rel.source}
                                </span>
                              </div>
                              <div className={styles.nodeRelationInfo}>
                                <span className={styles.nodeRelationType}>{rel.properties.join_type}</span>
                                {rel.properties.description && (
                                  <span className={styles.nodeRelationDesc}>{rel.properties.description}</span>
                                )}
                              </div>
                              <div className={styles.nodeRelationCondition}>
                                {rel.properties.condition}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className={styles.propertyEmpty}>
                          <p>该表没有关联关系</p>
                        </div>
                      )}
                    </Card>
                  )}
                  
                  {/* 全部关系列表 */}
                  <Card variant="glass" padding="md" className={styles.fullscreenPanel} style={{ flex: selectedNode ? 1 : 2 }}>
                    <div className={styles.panelTitle}>
                      全部关系 ({relationships.length})
                    </div>
                    <div className={styles.relationshipList}>
                      {relationships.map((rel, index) => (
                        <div
                          key={index}
                          className={cn(
                            styles.relationshipItem,
                            highlightedRelIndices.has(index) && styles.relationshipItemActive
                          )}
                          onClick={() => {
                            // 点击关系时选中源表
                            handleNodeSelect(rel.source);
                          }}
                        >
                          <Link size={14} color="#00F5FF" />
                          <span className={styles.relationshipPath}>
                            {rel.source} → {rel.target}
                          </span>
                          <span className={styles.relationshipType}>{rel.properties.join_type}</span>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      {/* 添加关系弹窗 - 参考Terms页面风格 */}
      <AnimatePresence>
        {showAddModal && (
          <motion.div
            className={styles.modalOverlay}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowAddModal(false)}
          >
            <motion.div
              className={styles.modalContent}
              onClick={(e) => e.stopPropagation()}
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
            >
              <Card variant="glass" padding="lg">
                <div className={styles.modalHeader}>
                  <h3 className={styles.modalTitle}>添加表关系</h3>
                  <Button variant="ghost" size="sm" leftIcon={<X size={18} />} onClick={() => setShowAddModal(false)} />
                </div>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>源表 *</label>
                    <CustomSelect
                      value={newRel.sourceTable}
                      onChange={(v) => setNewRel({ ...newRel, sourceTable: v, sourceColumn: '' })}
                      options={tableOptions}
                      placeholder="请选择表"
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>源字段 (FK) *</label>
                    <CustomSelect
                      value={newRel.sourceColumn}
                      onChange={(v) => setNewRel({ ...newRel, sourceColumn: v })}
                      options={getColumnOptions(newRel.sourceTable)}
                      placeholder="请选择字段"
                      disabled={!newRel.sourceTable}
                    />
                  </div>
                </div>
                <div className={styles.formRow}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>目标表 *</label>
                    <CustomSelect
                      value={newRel.targetTable}
                      onChange={(v) => setNewRel({ ...newRel, targetTable: v, targetColumn: '' })}
                      options={tableOptions}
                      placeholder="请选择表"
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>目标字段 (PK) *</label>
                    <CustomSelect
                      value={newRel.targetColumn}
                      onChange={(v) => setNewRel({ ...newRel, targetColumn: v })}
                      options={getColumnOptions(newRel.targetTable)}
                      placeholder="请选择字段"
                      disabled={!newRel.targetTable}
                    />
                  </div>
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>关系类型</label>
                  <CustomSelect
                    value={newRel.joinType}
                    onChange={(v) => setNewRel({ ...newRel, joinType: v })}
                    options={joinTypeOptions}
                  />
                </div>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>关系描述</label>
                  <input
                    className={styles.formInput}
                    value={newRel.description}
                    onChange={(e) => setNewRel({ ...newRel, description: e.target.value })}
                    placeholder="例如：用户所属地区、订单商品"
                  />
                </div>
                <div className={styles.modalFooter}>
                  <Button variant="ghost" onClick={() => setShowAddModal(false)}>取消</Button>
                  <Button 
                    onClick={handleConfirmAdd} 
                    disabled={!newRel.sourceTable || !newRel.sourceColumn || !newRel.targetTable || !newRel.targetColumn}
                  >
                    添加关系
                  </Button>
                </div>
              </Card>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default Graph;
