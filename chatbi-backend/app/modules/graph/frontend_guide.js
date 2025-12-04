/*
功能：知识图谱构建器前端交互逻辑说明
说明：基于 React Flow 的前端组件逻辑，用于指导前端工程师对接后端 API。
作者：CYJ
时间：2025-11-20
*/

/**
 * 核心组件结构 (GraphBuilder)
 * 
 * 1. 状态管理 (State)
 * - `nodes`: React Flow 节点列表 (从 /api/graph/visualization 初始化)
 * - `edges`: React Flow 边列表 (从 /api/graph/visualization 初始化)
 * - `metadata`: MySQL 表结构列表 (从 /api/graph/metadata 获取)
 * 
 * 2. 关键交互流程
 * 
 * A. 初始化加载
 *    useEffect(() => {
 *      // 1. 并行请求元数据和图谱数据
 *      Promise.all([
 *        fetch('/api/v1/graph/metadata'),
 *        fetch('/api/v1/graph/visualization')
 *      ]).then(([meta, graph]) => {
 *        setMetadata(meta);
 *        setNodes(mapNeo4jNodesToReactFlow(graph.nodes));
 *        setEdges(mapNeo4jEdgesToReactFlow(graph.edges));
 *      });
 *    }, []);
 * 
 * B. 拖拽添加节点 (DnD)
 *    onDrop = (event) => {
 *      const tableName = event.dataTransfer.getData('tableName');
 *      // 1. 乐观更新 UI
 *      addNodeToCanvas(tableName);
 *      // 2. 调用后端创建节点 (防止 ID 冲突，最好由后端生成或前端生成 UUID)
 *      fetch('/api/v1/graph/node', {
 *        method: 'POST',
 *        body: { label: 'Table', properties: { name: tableName } }
 *      });
 *    };
 * 
 * C. 连线创建关系 (Connection)
 *    onConnect = (params) => {
 *      // params: { source, target, sourceHandle, targetHandle }
 *      // sourceHandle / targetHandle 通常对应字段名
 *      
 *      // 1. 弹出模态框让用户输入关系类型 (JOIN_ON / FOREIGN_KEY)
 *      const relConfig = await openRelationshipModal();
 *      
 *      // 2. 调用后端
 *      fetch('/api/v1/graph/relationship', {
 *        method: 'POST',
 *        body: {
 *          source_node_id: params.source,
 *          target_node_id: params.target,
 *          relationship_type: relConfig.type,
 *          properties: relConfig.properties 
 *        }
 *      }).then(() => {
 *         // 3. 更新 UI 连线
 *         setEdges((eds) => addEdge(params, eds));
 *      });
 *    };
 * 
 * D. 删除操作
 *    onEdgesDelete = (edgesToDelete) => {
 *       edgesToDelete.forEach(edge => {
 *          fetch(`/api/v1/graph/relationship/${edge.id}`, { method: 'DELETE' });
 *       });
 *    };
 * 
 * 3. 数据结构映射
 * - Neo4j Node (Table) -> React Flow Node (type: 'customTableNode')
 * - Neo4j Edge (JOIN_ON) -> React Flow Edge (type: 'smoothstep', label: 'JOIN_ON')
 */
