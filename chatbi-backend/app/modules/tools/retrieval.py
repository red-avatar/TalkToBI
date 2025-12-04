"""
功能：检索工具集 (Retrieval Tools) - 引导式设计版本
说明：
    封装 VectorStore 和 GraphService 为 LangChain 标准 Tools。
    采用引导式设计：给 LLM 候选集合，让它选择，而非硬编码映射。
    
    核心改进：
    1. 槽位分解：将复合语义查询分解为独立槽位分别召回
    2. Schema-Aware Expansion：基于候选集引导 LLM 选择
    3. 外键自动补全：通过图谱自动补全关联的维度表
作者：CYJ
时间：2025-11-25 (重构)
"""
from typing import List, Dict, Optional, Set, Tuple
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from app.modules.vector.store import VectorStore
from app.modules.graph.service import GraphService
from app.modules.schema.catalog import get_schema_catalog
from app.core.config import get_settings
import json
import os
import logging

logger = logging.getLogger(__name__)
_settings = get_settings()

# =============================================================================
# Tool 1: Vector Retrieval Tool
# =============================================================================

class VectorSearchInput(BaseModel):
    query: str = Field(description="Natural language query to search for tables/columns. e.g. 'users in Hangzhou'")
    top_k: int = Field(default=5, description="Number of results to return")

class VectorRetrievalTool(BaseTool):
    """
    向量检索工具 - 引导式设计版本
    
    核心改进：
    1. 槽位分解：将复合语义查询分解为独立槽位
    2. Schema-Aware Expansion：基于候选集引导 LLM 选择
    3. 外键自动补全：通过图谱自动补全关联的维度表
    
    Author: CYJ
    Time: 2025-11-25
    """
    name: str = "retrieve_schema_vectors"
    description: str = "Search for relevant tables and columns using vector similarity and graph completion."
    args_schema: type[BaseModel] = VectorSearchInput
    
    # 配置参数（从 Settings 读取）
    # Author: CYJ
    # Time: 2025-11-28 (配置化改造)
    HIGH_THRESHOLD: float = _settings.RETRIEVAL_HIGH_THRESHOLD
    MEDIUM_THRESHOLD: float = _settings.RETRIEVAL_MEDIUM_THRESHOLD
    LOW_THRESHOLD: float = _settings.RETRIEVAL_LOW_THRESHOLD
    VECTOR_WEIGHT: float = _settings.RETRIEVAL_VECTOR_WEIGHT
    
    # --- V3: Embedding 缓存（LRU）---
    _embedding_cache: dict = {}
    _embedding_cache_order: list = []
    _embedding_cache_cap: int = 512  # 最多缓存 512 条，避免内存增长
    _emb_client = None  # 复用 Embeddings 客户端，避免每次创建
    
    def _run(self, query: str, top_k: int = 10) -> str:
        """
        执行引导式分层召回 (V2)
        
        流程（分层检索，避免 Token 爆炸）：
        1. 槽位分解：将复合查询分解为独立语义槽位
        2. 第 1 层：表名粗筛（LLM 从表名列表选择，~200 token）
        3. 第 2 层：获取选中表的列 + 向量搜索
        4. 外键补全：自动补全外键关联的维度表
        5. 图路径补全
        
        Author: CYJ
        Time: 2025-11-25 (V2)
        """
        try:
            store = VectorStore()
            catalog = get_schema_catalog()
            all_results: List[Tuple] = []
            found_tables: Set[str] = set()
            found_fk_columns: Set[str] = set()
            
            # === Step 1: 槽位分解 ===
            logger.info(f"[Retrieval V2] Step 1: Slot Decomposition for '{query}'")
            slots = self._decompose_to_slots(query)
            logger.info(f"[Retrieval V2] Decomposed Slots: {slots}")
            
            # === Step 2: 分层检索第 1 层 - 表名粗筛 ===
            logger.info("[Retrieval V2] Step 2: Layer 1 - Table Selection")
            
            # 使用只包含表名的轻量级 prompt 让 LLM 选择相关表
            selected_tables = self._select_tables_layer1(query)
            logger.info(f"[Retrieval V2] Layer 1 Selected Tables: {selected_tables}")
            
            # 确保至少有一些表被选中
            if not selected_tables:
                # 回退到老方法
                selected_tables = self._expand_query_with_candidates(query)
                logger.info(f"[Retrieval V2] Fallback to old method, tables: {selected_tables}")
            
            # 将选中的表加入 found_tables
            found_tables.update(selected_tables)
            
            # === Step 3: 分层检索第 2 层 - 获取选中表的列 + 向量搜索 ===
            logger.info("[Retrieval V2] Step 3: Layer 2 - Column Retrieval + Vector Search")
            
            # 3.1 获取选中表的列信息
            columns_info = catalog.format_columns_for_tables(list(selected_tables))
            logger.info(f"[Retrieval V2] Columns info length: {len(columns_info)} chars")
            
            # 3.1.1 V3: 预批量计算并缓存 Embedding，减少多次 HTTP 往返
            batch_texts = set()
            batch_texts.add(query)
            for sv in slots.values():
                if sv:
                    batch_texts.add(sv)
            for t in selected_tables:
                batch_texts.add(f"table {t}")
            self._precache_embeddings(list(batch_texts))
            
            # 3.2 将 Layer 1 选中的表直接加入结果（高置信度）
            # 重要：不依赖向量搜索的相似度，LLM 选择的表应该被信任
            forced_table_results = []
            for table_name in selected_tables:
                table_rec = self._fetch_table_by_name(store, table_name)
                if table_rec:
                    forced_table_results.append((table_rec, 0.98))  # 高置信度
                    logger.info(f"[Retrieval V2] Layer 1 forced table: {table_name}")
            
            # 3.3 向量搜索（使用槽位分解的结果）
            embedding = self._get_embedding(query)
            primary_results = store.hybrid_search(
                query_embedding=embedding, 
                query_text=query, 
                limit=top_k, 
                vector_weight=self.VECTOR_WEIGHT
            )
            all_results.extend(primary_results)
            
            # 3.4 各槽位独立召回（去重后）
            for slot_type, slot_value in {k:v for k,v in slots.items() if v}.items():
                slot_emb = self._get_embedding(slot_value)
                slot_results = store.hybrid_search(
                    query_embedding=slot_emb,
                    query_text=slot_value,
                    limit=5,
                    vector_weight=self.VECTOR_WEIGHT
                )
                all_results.extend(slot_results)
                logger.info(f"[Retrieval V2] Slot '{slot_type}' retrieved {len(slot_results)} results")
            
            # === Step 4: 结果处理 ===
            unique_results = self._dedupe_results(all_results)
            filtered_results = self._filter_results(unique_results, threshold=self.LOW_THRESHOLD)
            
            # 4.1 合并 Layer 1 强制表和向量搜索结果
            # Layer 1 的表应该始终包含
            for rec, score in forced_table_results:
                # 检查是否已存在
                exists = any(r.object_name == rec.object_name for r, _ in filtered_results)
                if not exists:
                    filtered_results.append((rec, score))
                    logger.info(f"[Retrieval V2] Added forced table to results: {rec.object_name}")
            
            # 提取已召回的表和外键列
            for r, _ in filtered_results:
                if r.object_type == 'table':
                    found_tables.add(r.object_name)
                elif r.object_type == 'column':
                    if '.' in r.object_name:
                        table_name = r.object_name.split('.')[0]
                        col_name = r.object_name.split('.')[1]
                        found_tables.add(table_name)
                        # 检测外键列
                        if col_name.endswith('_id') or col_name.endswith('_code'):
                            found_fk_columns.add(r.object_name)
            
            logger.info(f"[Retrieval V2] Found Tables: {found_tables}")
            logger.info(f"[Retrieval V2] Found FK Columns: {found_fk_columns}")
            
            # === Step 5: 外键自动补全 ===
            logger.info("[Retrieval V2] Step 5: FK Column Expansion")
            fk_target_tables = self._expand_fk_columns(found_fk_columns, catalog)
            
            for target_table in fk_target_tables:
                if target_table not in found_tables:
                    logger.info(f"[Retrieval V2] FK Expansion: Adding dimension table '{target_table}'")
                    # 获取目标表的 schema
                    table_rec = self._fetch_table_by_name(store, target_table)
                    if table_rec:
                        filtered_results.append((table_rec, 0.95))  # 高置信度
                        found_tables.add(target_table)
            
            # === Step 6: 图路径补全 ===
            if len(found_tables) >= 2:
                logger.info("[Retrieval V2] Step 6: Graph Path Completion")
                intermediate_tables = self._complete_schema_with_graph(list(found_tables))
                
                for t_name in intermediate_tables:
                    if t_name not in found_tables:
                        table_rec = self._fetch_table_by_name(store, t_name)
                        if table_rec:
                            filtered_results.append((table_rec, 0.90))
                            found_tables.add(t_name)
                            logger.info(f"[Retrieval V2] Graph Completion: Added '{t_name}'")
            
            # === Final: 格式化输出 ===
            if not filtered_results:
                # 最终回退
                fallback_results = store.search(query_embedding=embedding, limit=top_k)
                filtered_results = [(rec, 1.0 - float(dist)) for rec, dist in fallback_results]
            
            # V2 关键改进：附加选中表的列信息
            # 这样 Planner 才知道每个表有哪些字段
            base_result = self._format_results(filtered_results)
            columns_info = catalog.format_columns_for_tables(list(found_tables))
            
            if columns_info:
                return base_result + "\n\n[Column Details]\n" + columns_info
            return base_result

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            import traceback
            traceback.print_exc()
            return f"Vector search error: {str(e)}"

    def _dedupe_results(self, results: List[Tuple]) -> List[Tuple]:
        """
        去重并按相似度排序
        
        Author: CYJ
        Time: 2025-11-25
        """
        unique = {}
        for rec, dist in results:
            if rec.id not in unique:
                unique[rec.id] = (rec, dist)
            else:
                # 保留距离更小的（相似度更高）
                if dist < unique[rec.id][1]:
                    unique[rec.id] = (rec, dist)
        
        deduped = list(unique.values())
        deduped.sort(key=lambda x: x[1])  # 按距离升序
        return deduped
    
    def _filter_results(self, results: List[Tuple], threshold: float) -> List[Tuple]:
        """
        按相似度阈值过滤结果
        
        Author: CYJ
        Time: 2025-11-25
        """
        filtered = []
        for r, distance in results:
            similarity = 1 - distance
            if similarity >= threshold:
                filtered.append((r, similarity))
        return filtered

    def _format_results(self, results: List[Tuple]) -> str:
        """
        格式化结果为字符串
        
        Author: CYJ
        Time: 2025-11-25
        """
        formatted_res = []
        for r, similarity in results:
            desc = r.enriched_description or r.original_description or getattr(r, 'description', '')
            formatted_res.append(f"[{r.object_type.upper()}] {r.object_name} (Score: {similarity:.2f}): {desc}")
        logger.info(f"[Retrieval] Returning {len(formatted_res)} results.")
        return "\n".join(formatted_res)
    
    def _fetch_table_by_name(self, store: VectorStore, table_name: str):
        """
        根据表名精确获取表记录
        
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            t_emb = self._get_embedding(f"table {table_name}")
            t_res = store.hybrid_search(
                query_embedding=t_emb, 
                query_text=table_name, 
                limit=5, 
                vector_weight=0.1
            )
            for rec, _ in t_res:
                if rec.object_name == table_name and rec.object_type == 'table':
                    return rec
            return None
        except Exception as e:
            logger.error(f"Failed to fetch table {table_name}: {e}")
            return None
    
    def _decompose_to_slots(self, query: str) -> Dict[str, str]:
        """
        将复合语义查询分解为独立槽位
        
        设计原理：
        复合查询如"广州的订单数量"包含多个语义维度（地理+业务）。
        单一向量无法同时捕捉所有维度，导致召回偏向某一侧。
        通过分解为独立槽位，每个槽位单独检索，提高召回全面性。
        
        Author: CYJ
        """
        try:
            from app.core.llm import get_llm
            from langchain_core.messages import HumanMessage
            
            llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
            prompt = f"""分析用户的数据查询问题，提取关键语义槽位。

用户问题：{query}

任务：识别问题中的以下槽位类型（如有）：
- location: 地理位置（城市、地区、省份）
- entity: 业务实体（用户、店铺、商品、品牌）
- metric: 统计指标（数量、金额、销售额、订单数）
- time: 时间范围
- condition: 过滤条件（状态、类型）

输出要求：
- 仅输出 JSON 格式
- 只包含识别到的槽位，未识别到的不要输出
- 槽位值应扩展为适合数据库检索的关键词

示例：
输入："查询广州的订单数量"
输出：{{"location": "广州 城市 地区 dim_region", "metric": "订单 数量 orders count"}}  

输入："没有使用优惠券的订单"
输出：{{"entity": "订单 orders", "condition": "优惠券 coupon order_coupons 未使用"}}  
"""
            resp = llm.invoke([HumanMessage(content=prompt)])
            
            # 解析 JSON
            content = resp.content.strip()
            # 处理 markdown 代码块
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            slots = json.loads(content)
            return slots
            
        except Exception as e:
            logger.error(f"Slot decomposition failed: {e}")
            # 回退：返回原始查询作为单一槽位
            return {"query": query}
    
    def _select_tables_layer1(self, query: str) -> List[str]:
        """
        分层检索第 1 层：轻量级表名选择
        
        设计原理：
        只提供表名和简短描述（~200 token），让 LLM 选择相关表。
        避免一次性注入所有表的列信息，防止 Token 爆炸。
        
        Args:
            query: 用户查询
            
        Returns:
            选中的表名列表
            
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            from app.core.llm import get_llm
            from langchain_core.messages import HumanMessage
            
            catalog = get_schema_catalog()
            # 使用轻量级的表名列表（不含列信息）
            tables_only = catalog.format_tables_only_for_prompt()
            
            llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
            prompt = f"""你是数据库专家。根据用户的数据查询问题，从以下表中选择最相关的表。

用户问题：{query}

数据库中的表：
{tables_only}

任务：
1. 分析用户问题涉及哪些业务概念
2. 从上述表中选择 1-5 个最相关的表
3. 关键业务概念与表的映射关系（必须遵守）：
   - 订单相关：orders, order_items
   - 用户/会员：users
   - 商品相关：products
   - 【类别/品类/分类】：categories（电子产品、手机、服饰鞋包等都属于类别）
   - 店铺：shops
   - 优惠券/券/满减/折扣：coupons, order_coupons, user_coupons
   - 【支付/支付方式/微信/支付宝】：payments
   - 【退款/退货/退款率】：refunds, payments
   - 物流/配送/签收/发货：shipments, logistics_providers
   - 地理位置（城市、地区）：dim_region
   - 渠道（APP、小程序、官网）：dim_channel

Few-Shot示例：

示例1：
问题："二线城市第三方店铺售出的电子产品类商品中，通过支付宝支付且使用满减券，后续退款成功的订单数量与退款金额"
分析：涉及 城市→dim_region, 店铺→shops, 商品类别→categories和products, 支付→payments, 优惠券→coupons和order_coupons, 退款→refunds, 订单→orders和order_items
输出：["orders", "order_items", "products", "categories", "shops", "dim_region", "payments", "refunds", "order_coupons", "coupons", "users"]

示例2：
问题："最近90天一线和二线城市手机类商品在自营与第三方店铺的订单量、GMV以及退款率对比"
分析：涉及 城市→dim_region, 商品类别→categories, 店铺→shops, 订单→orders和order_items, 退款率→refunds和payments
输出：["orders", "order_items", "products", "categories", "shops", "dim_region", "payments", "refunds", "users"]

示例3：
问题："使用折扣券购买服饰鞋包类商品的各城市订单数"
分析：涉及 优惠券→coupons和order_coupons, 商品类别→categories, 城市→dim_region, 订单→orders
输出：["orders", "order_coupons", "coupons", "order_items", "products", "categories", "users", "dim_region"]

输出要求：
- 仅输出 JSON 数组格式
- 只能从上述表名中选择，不要创造新表名
- 必须包含问题涉及的所有相关表，不能遗漏
- 格式示例：["orders", "dim_region", "categories"]
"""
            resp = llm.invoke([HumanMessage(content=prompt)])
            
            content = resp.content.strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            tables = json.loads(content)
            return tables if isinstance(tables, list) else []
            
        except Exception as e:
            logger.error(f"Layer 1 table selection failed: {e}")
            return []
    
    def _expand_query_with_candidates(self, query: str) -> List[str]:
        """
        Schema-Aware Query Expansion（引导式扩展）- 回退方法
        
        设计原理：
        给 LLM 提供数据库的表名候选集，让它从已知范围内选择。
        避免幻觉出不存在的表名，提高扩展的准确性。
        
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            from app.core.llm import get_llm
            from langchain_core.messages import HumanMessage
            
            catalog = get_schema_catalog()
            tables_info = catalog.format_tables_for_prompt(max_tables=20)
            
            llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
            prompt = f"""根据用户问题，从下面的数据库表中选择最相关的表。

用户问题：{query}

数据库中的表：
{tables_info}

任务：
1. 分析用户问题涉及哪些业务概念
2. 从上述表中选择 1-5 个最相关的表
3. 注意：地理相关查询通常需要 dim_region 表；优惠券相关需要 order_coupons 表

输出要求：
- 仅输出 JSON 数组格式
- 只能从上述表名中选择，不要创造新表名
- 示例：["orders", "dim_region"]
"""
            resp = llm.invoke([HumanMessage(content=prompt)])
            
            content = resp.content.strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            tables = json.loads(content)
            return tables if isinstance(tables, list) else []
            
        except Exception as e:
            logger.error(f"Schema-aware expansion failed: {e}")
            return []
    
    def _expand_fk_columns(self, fk_columns: Set[str], catalog) -> Set[str]:
        """
        外键列自动补全：根据外键列找到关联的维度表
        
        设计原理：
        当召回了 orders.shipping_region_id 但没有召回 dim_region 时，
        通过图谱或命名规则推断外键指向的表，自动补全。
        
        Author: CYJ
        Time: 2025-11-25
        """
        target_tables = set()
        
        for fk_col in fk_columns:
            target = catalog.get_fk_target_table(fk_col)
            if target:
                target_tables.add(target)
                logger.info(f"[FK Expansion] {fk_col} -> {target}")
        
        return target_tables

    def _complete_schema_with_graph(self, found_tables: List[str]) -> List[str]:
        """
        Find shortest paths between all pairs of found tables using local graph data.
        Return list of intermediate tables that were not in found_tables.
        """
        try:
            # Load relationship data
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            json_path = os.path.join(base_path, "scripts", "phase2_knowledge_base", "data", "relationships_enhanced.json")
            
            if not os.path.exists(json_path):
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                rels = json.load(f)
                
            # Build Adjacency List
            adj = {}
            for r in rels:
                s, t = r['source'], r['target']
                if s not in adj: adj[s] = []
                if t not in adj: adj[t] = []
                adj[s].append(t)
                adj[t].append(s) # Undirected for traversal
                
            intermediate_tables = set()
            
            # Find path between every pair
            import itertools
            for t1, t2 in itertools.combinations(found_tables, 2):
                if t1 not in adj or t2 not in adj:
                    continue
                    
                # BFS
                queue = [[t1]]
                visited = {t1}
                path_found = None
                
                while queue:
                    path = queue.pop(0)
                    node = path[-1]
                    
                    if node == t2:
                        path_found = path
                        break
                        
                    # Optimization: Limit depth to 3 hops to avoid weird long paths
                    if len(path) > 4: 
                        continue
                    
                    # Check adjacency to continue BFS
                    if node in adj:
                        for neighbor in adj[node]:
                            if neighbor not in visited:
                                visited.add(neighbor)
                                new_path = list(path)
                                new_path.append(neighbor)
                                queue.append(new_path)
                
                if path_found:
                    # Add intermediate nodes
                    # Path: [t1, inter1, inter2, t2]
                    for tbl in path_found:
                        if tbl not in found_tables:
                            intermediate_tables.add(tbl)
                            
            return list(intermediate_tables)
            
        except Exception as e:
            logger.error(f"Graph completion failed: {e}")
            return []

    def _expand_query(self, query: str) -> List[str]:
        """Call LLM to expand query into synonyms."""
        try:
            # Simple inline prompt to avoid circular deps
            from app.core.llm import get_llm
            from langchain_core.messages import HumanMessage
            
            llm = get_llm(temperature=_settings.LLM_TEMPERATURE_BALANCED)
            prompt = f"""
            Analyze the user query and generate a list of potential database keywords (tables, columns, technical terms) to improve search recall.
            User Query: '{query}'
            
            Guidelines:
            1. Infer potential table names (e.g. 'sales' -> 'orders', 'order_items'; 'user' -> 'users'; 'shop' -> 'shops').
            2. Infer potential concepts (e.g. 'refund' -> 'refunds'; 'region' -> 'dim_region').
            3. Break down complex concepts (e.g. 'Huawei sales in Guangzhou' -> 'products', 'brand', 'orders', 'dim_region', 'city').
            4. Return ONLY a list of 3-5 keywords/phrases separated by newlines.
            """
            msg = HumanMessage(content=prompt)
            resp = llm.invoke([msg])
            
            queries = [line.strip() for line in resp.content.split('\n') if line.strip()]
            return queries[:3]
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return []

    def _get_embeddings_client(self):
        """
        获取或初始化可复用的 Embeddings 客户端
        
        支持独立配置 EMBEDDING_PROVIDER，与 LLM_PROVIDER 解耦。
        这样可以 chat 用 kimi，embedding 用阿里云。
        
        Author: CYJ
        """
        if self._emb_client is not None:
            return self._emb_client
        from app.core.config import get_settings
        settings = get_settings()
        
        # 使用独立的 EMBEDDING_PROVIDER 配置
        embedding_provider = getattr(settings, 'EMBEDDING_PROVIDER', 'dashscope')
        
        if embedding_provider == "dashscope":
            from langchain_openai import OpenAIEmbeddings
            import httpx
            http_client = httpx.Client(verify=False)
            self._emb_client = OpenAIEmbeddings(
                model=settings.DASHSCOPE_EMBEDDING_MODEL,
                openai_api_key=settings.DASHSCOPE_API_KEY,
                openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                http_client=http_client,
                check_embedding_ctx_length=False
            )
            logger.info(f"[Embedding] Initialized DashScope client with model: {settings.DASHSCOPE_EMBEDDING_MODEL}")
        elif embedding_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            self._emb_client = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
            )
            logger.info("[Embedding] Initialized OpenAI client")
        else:
            logger.warning(f"[Embedding] Unknown provider '{embedding_provider}', falling back to None")
            self._emb_client = None
        return self._emb_client

    def _cache_put(self, text: str, vec: List[float]):
        # Simple LRU maintenance
        if text in self._embedding_cache:
            # move to end
            self._embedding_cache_order.remove(text)
        self._embedding_cache[text] = vec
        self._embedding_cache_order.append(text)
        if len(self._embedding_cache_order) > self._embedding_cache_cap:
            old_key = self._embedding_cache_order.pop(0)
            self._embedding_cache.pop(old_key, None)

    def _precache_embeddings(self, texts: List[str]):
        """
        Batch-embed a list of texts and cache results. Skips cached ones.
        
        V2: 限制 batch size 为 10，避免阿里云 API 报错
        Author: CYJ
        Time: 2025-11-28
        """
        to_embed = [t for t in texts if t not in self._embedding_cache]
        if not to_embed:
            return
        
        # 阿里云 DashScope embedding API batch size 限制为 10
        BATCH_SIZE = 10
        
        try:
            client = self._get_embeddings_client()
            if client is None:
                # Fallback: store mock to avoid repeated attempts
                for t in to_embed:
                    self._cache_put(t, [0.0] * 1024)
                return
            
            # 分批处理，每批最多 BATCH_SIZE 条
            for i in range(0, len(to_embed), BATCH_SIZE):
                batch = to_embed[i:i + BATCH_SIZE]
                try:
                    vecs = client.embed_documents(batch)
                    for t, v in zip(batch, vecs):
                        self._cache_put(t, v)
                except Exception as batch_err:
                    logger.warning(f"Batch {i//BATCH_SIZE + 1} embedding failed: {batch_err}, trying individual...")
                    # 单个批次失败时，逐个处理
                    for t in batch:
                        try:
                            v = client.embed_query(t)
                            self._cache_put(t, v)
                        except Exception:
                            self._cache_put(t, [0.0] * 1024)
                            
        except Exception as e:
            logger.error(f"Batch embedding initialization failed: {e}")
            # Fallback: try individual
            for t in to_embed:
                try:
                    v = self._get_embedding(t)
                    self._cache_put(t, v)
                except Exception:
                    self._cache_put(t, [0.0] * 1024)

    def _get_embedding(self, text: str) -> List[float]:
        # Cached single embedding
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        try:
            client = self._get_embeddings_client()
            if client is not None:
                vec = client.embed_query(text)
                self._cache_put(text, vec)
                return vec
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
        # fallback
        logger.warning("Using MOCK embedding (all zeros) - Search results will be poor!")
        vec = [0.0] * 1024
        self._cache_put(text, vec)
        return vec

# =============================================================================
# Tool 2: Graph Traversal Tool
# =============================================================================

class GraphPathInput(BaseModel):
    start_table: str = Field(description="Name of the starting table (e.g. 'users')")
    end_table: str = Field(description="Name of the target table (e.g. 'products')")

class GraphTraversalTool(BaseTool):
    name: str = "find_graph_path"
    description: str = "Find the shortest JOIN path between two tables. Essential for generating correct SQL JOINs."
    args_schema: type[BaseModel] = GraphPathInput
    
    def _run(self, start_table: str, end_table: str) -> str:
        """Execute graph path finding."""
        try:
            # Strategy 1: Try Neo4j (GraphService)
            graph_service = GraphService()
            # TODO: Implement shortestPath query in GraphService
            # For now, we fallback to local JSON because Neo4j might be empty/down
            return self._find_path_local(start_table, end_table)
        except Exception as e:
            logger.error(f"Graph traversal failed: {e}")
            return f"Graph traversal error: {str(e)}"

    def _find_path_local(self, start: str, end: str) -> str:
        """Fallback: BFS on local JSON file."""
        # Load relationship data
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        json_path = os.path.join(base_path, "scripts", "phase2_knowledge_base", "data", "relationships_enhanced.json")
        
        if not os.path.exists(json_path):
            return "Graph data file not found."
            
        with open(json_path, 'r', encoding='utf-8') as f:
            rels = json.load(f)
            
        # Build adjacency list
        adj = {}
        for r in rels:
            s, t = r['source'], r['target']
            if s not in adj: adj[s] = []
            if t not in adj: adj[t] = []
            adj[s].append((t, r['properties']))
            # Assuming undirected for joinability, but JSON is directed.
            # For SQL generation, JOINs are bidirectional usually.
            adj[t].append((s, r['properties'])) 

        # BFS
        queue = [[start]]
        visited = {start}
        
        if start == end:
            return f"Same table: {start}"
            
        while queue:
            path = queue.pop(0)
            node = path[-1]
            
            if node == end:
                return self._format_path(path, adj, rels)
            
            if node in adj:
                for neighbor, props in adj[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_path = list(path)
                        new_path.append(neighbor)
                        queue.append(new_path)
                        
        return f"No path found between {start} and {end}"

    def _format_path(self, path: List[str], adj, rels) -> str:
        """Format path into readable string like 'users JOIN orders ON users.id = orders.user_id'"""
        result = []
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            # Find specific relation props
            # In a real implementation, we'd pass the exact edge used in BFS
            # Here we simplisticly lookup
            condition = "UNKNOWN"
            for r in rels:
                if (r['source'] == u and r['target'] == v) or (r['source'] == v and r['target'] == u):
                    condition = r['properties'].get('condition', 'UNKNOWN')
                    break
            result.append(f"{u} -> {v} (ON {condition})")
        return " Path: " + " JOIN ".join(result)
