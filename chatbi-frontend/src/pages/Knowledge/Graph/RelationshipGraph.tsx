/**
 * 关系图组件 - 基于 React Flow
 * 支持：缩放、拖动、节点拖拽、点击交互
 * Author: 陈怡坚
 * Time: 2025-12-03
 */
import React, { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
  ConnectionLineType,
} from '@xyflow/react';
import type { Node, Edge, NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { GraphRelationship } from '../../../api/types';
import * as styles from './graphStyles.css';

interface RelationshipGraphProps {
  relationships: GraphRelationship[];
  selectedNode: string | null;
  highlightedIndices: Set<number>;
  onNodeSelect: (tableName: string) => void;
}

/** 表节点数据类型 */
type TableNodeData = {
  label: string;
  relationCount: number;
};

/** 自定义表节点组件 */
const TableNode: React.FC<NodeProps<Node<TableNodeData>>> = ({ data, selected }) => {
  return (
    <div className={`${styles.tableNode} ${selected ? styles.tableNodeSelected : ''}`}>
      {/* 四边连接点 */}
      <Handle type="target" position={Position.Top} id="top" className={styles.handle} />
      <Handle type="target" position={Position.Left} id="left" className={styles.handle} />
      <Handle type="source" position={Position.Bottom} id="bottom" className={styles.handle} />
      <Handle type="source" position={Position.Right} id="right" className={styles.handle} />
      
      <div className={styles.tableNodeIcon}>📊</div>
      <div className={styles.tableNodeLabel}>{data.label}</div>
      {data.relationCount > 0 && (
        <div className={styles.tableNodeBadge}>{data.relationCount}</div>
      )}
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

/** 计算两个节点之间的最佳连接点 */
const getBestHandles = (
  sourcePos: { x: number; y: number },
  targetPos: { x: number; y: number }
): { sourceHandle: string; targetHandle: string } => {
  const dx = targetPos.x - sourcePos.x;
  const dy = targetPos.y - sourcePos.y;
  
  // 根据相对位置选择最佳连接点
  if (Math.abs(dx) > Math.abs(dy)) {
    // 水平方向为主
    if (dx > 0) {
      return { sourceHandle: 'right', targetHandle: 'left' };
    } else {
      return { sourceHandle: 'left', targetHandle: 'right' };
    }
  } else {
    // 垂直方向为主
    if (dy > 0) {
      return { sourceHandle: 'bottom', targetHandle: 'top' };
    } else {
      return { sourceHandle: 'top', targetHandle: 'bottom' };
    }
  }
};

const RelationshipGraph: React.FC<RelationshipGraphProps> = ({
  relationships,
  selectedNode,
  highlightedIndices,
  onNodeSelect,
}) => {
  /** 将关系数据转换为节点和边 */
  const { initialNodes, initialEdges } = useMemo(() => {
    const uniqueTables = Array.from(
      new Set(relationships.flatMap((r) => [r.source, r.target]))
    );

    // 计算每个表的关系数量（入度+出度）
    const relationCountMap: Record<string, number> = {};
    const outDegree: Record<string, number> = {};
    const inDegree: Record<string, number> = {};
    
    relationships.forEach((rel) => {
      relationCountMap[rel.source] = (relationCountMap[rel.source] || 0) + 1;
      relationCountMap[rel.target] = (relationCountMap[rel.target] || 0) + 1;
      outDegree[rel.source] = (outDegree[rel.source] || 0) + 1;
      inDegree[rel.target] = (inDegree[rel.target] || 0) + 1;
    });

    // 改进布局：按入度分层（入度小的在左边/上面）
    const sortedTables = [...uniqueTables].sort((a, b) => {
      const aIn = inDegree[a] || 0;
      const bIn = inDegree[b] || 0;
      const aOut = outDegree[a] || 0;
      const bOut = outDegree[b] || 0;
      // 优先按入度排序，入度小的在前面（源表）
      if (aIn !== bIn) return aIn - bIn;
      // 其次按出度排序，出度大的在前面
      return bOut - aOut;
    });

    // 布局参数
    const nodeWidth = 160;
    const nodeHeight = 50;
    const gapX = 260;  // 增大水平间距
    const gapY = 100;  // 增大垂直间距
    const cols = Math.min(5, Math.ceil(Math.sqrt(sortedTables.length)));  // 最多5列

    const nodePositions: Record<string, { x: number; y: number }> = {};
    
    const nodes: Node[] = sortedTables.map((tableName, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      const position = {
        x: 80 + col * gapX,
        y: 60 + row * gapY,
      };
      nodePositions[tableName] = position;

      return {
        id: tableName,
        type: 'tableNode',
        position,
        data: {
          label: tableName,
          relationCount: relationCountMap[tableName] || 0,
        },
        style: { width: nodeWidth, height: nodeHeight },
      };
    });

    // 创建边 - 选中节点时高亮所有相关边
    const edges: Edge[] = relationships.map((rel, index) => {
      const sourcePos = nodePositions[rel.source];
      const targetPos = nodePositions[rel.target];
      const { sourceHandle, targetHandle } = getBestHandles(sourcePos, targetPos);
      const isHighlighted = highlightedIndices.has(index);

      return {
        id: `edge-${index}`,
        source: rel.source,
        target: rel.target,
        sourceHandle,
        targetHandle,
        type: 'smoothstep',
        animated: isHighlighted,  // 高亮的边有动画
        style: {
          stroke: isHighlighted ? '#00F5FF' : 'rgba(0, 245, 255, 0.25)',
          strokeWidth: isHighlighted ? 3 : 1,
          filter: isHighlighted ? 'drop-shadow(0 0 6px #00F5FF)' : 'none',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isHighlighted ? '#00F5FF' : 'rgba(0, 245, 255, 0.25)',
          width: 16,
          height: 16,
        },
        label: isHighlighted ? rel.properties.join_type : undefined,
        labelStyle: {
          fill: '#fff',
          fontSize: 10,
          fontWeight: 600,
        },
        labelBgStyle: {
          fill: 'rgba(0, 0, 0, 0.8)',
          fillOpacity: 0.9,
        },
        labelBgPadding: [4, 8] as [number, number],
        labelBgBorderRadius: 4,
        data: { index },
      };
    });

    return { initialNodes: nodes, initialEdges: edges };
  }, [relationships, highlightedIndices, selectedNode]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // 当关系数据变化时更新
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  /** 节点点击事件 */
  const onNodeClickHandler = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeSelect(node.id);
    },
    [onNodeSelect]
  );

  /** 点击空白区域取消选中 */
  const onPaneClick = useCallback(() => {
    onNodeSelect('');
  }, [onNodeSelect]);

  return (
    <div className={styles.graphContainer}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClickHandler}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
        defaultEdgeOptions={{
          type: 'smoothstep',
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(0, 245, 255, 0.05)" gap={20} />
        <Controls 
          className={styles.controls}
          showInteractive={false}
        />
        <MiniMap
          className={styles.minimap}
          nodeColor={(node) => 
            node.selected ? '#00F5FF' : 'rgba(0, 245, 255, 0.3)'
          }
          maskColor="rgba(0, 0, 0, 0.8)"
          style={{ background: 'rgba(20, 20, 30, 0.9)' }}
        />
      </ReactFlow>
    </div>
  );
};

export default RelationshipGraph;
