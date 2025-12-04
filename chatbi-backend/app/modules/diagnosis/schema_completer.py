"""
功能：Schema补全器 (Schema Completer)
说明：
    检测已召回Schema的完整性，识别缺失的关联表，触发二次召回补全
    
    核心能力：
    1. 外键列检测：识别 *_id, *_code 等外键列
    2. 目标表推断：根据外键列名推断指向的目标表
    3. 图谱关联检查：通过知识图谱验证表关联关系
    4. Schema补全：补充召回缺失的表信息
    
Author: CYJ
"""
import re
import json
import os
import logging
from typing import List, Dict, Set, Optional, Tuple

from app.modules.diagnosis.models import SchemaCheckResult

logger = logging.getLogger(__name__)


class SchemaCompleter:
    """
    Schema完整性检查与补全器 (V2: 动态FK映射)
    
    职责：
    1. 检测召回的表是否完整
    2. 识别缺失的关联表
    3. 补充召回缺失的表信息
    
    V2更新：移除硬编码的FK_TARGET_MAPPING，改为从图谱关系动态构建
    
    Author: CYJ
    """
    
    # 外键列后缀模式
    FK_SUFFIXES = ['_id', '_code']
    
    def __init__(self):
        """
        初始化Schema补全器
        
        V2: 动态构建FK映射，而非使用硬编码
        
        Author: CYJ
        Time: 2025-11-25 (V2重构)
        """
        self._graph_relations = self._load_graph_relations()
        self._all_tables = self._get_all_tables()
        # V2: 从图谱关系动态构建FK映射
        self._fk_target_mapping = self._build_fk_mapping_from_graph()
    
    def _load_graph_relations(self) -> List[Dict]:
        """
        加载图谱关系数据
        
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            json_path = os.path.join(base_path, "scripts", "phase2_knowledge_base", "data", "relationships_enhanced.json")
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Failed to load graph relations: {e}")
            return []
    
    def _get_all_tables(self) -> Set[str]:
        """
        获取所有已知的表名
        
        Author: CYJ
        Time: 2025-11-25
        """
        tables = set()
        for rel in self._graph_relations:
            tables.add(rel.get('source', ''))
            tables.add(rel.get('target', ''))
        return {t for t in tables if t}
    
    def _build_fk_mapping_from_graph(self) -> Dict[str, str]:
        """
        从图谱关系动态构建FK映射 (V2新增)
        
        分析图谱关系中的condition字段，提取外键前缀到目标表的映射。
        例如：condition = "orders.user_id = users.user_id" → user -> users
        
        Returns:
            Dict[str, str]: {外键前缀: 目标表名}
            
        Author: CYJ
        Time: 2025-11-25 (V2新增)
        """
        fk_mapping = {}
        
        for rel in self._graph_relations:
            target_table = rel.get('target', '')
            condition = rel.get('properties', {}).get('condition', '')
            
            if not target_table or not condition:
                continue
            
            # 从 condition 中提取外键列
            # 模式: xxx.yyy_id = zzz.yyy_id 或 xxx.yyy_code = zzz.yyy_code
            for suffix in self.FK_SUFFIXES:
                # 匹配如: user_id, category_id, logistics_provider_id 等
                pattern = rf'(\w+)\.(\w+{suffix})\s*='
                matches = re.findall(pattern, condition, re.IGNORECASE)
                
                for table, fk_col in matches:
                    # 提取外键前缀
                    fk_prefix = fk_col[:-len(suffix)]
                    
                    # 跳过自关联（如 parent_id）
                    if fk_prefix == 'parent':
                        continue
                    
                    # 建立映射: fk_prefix -> target_table
                    if fk_prefix not in fk_mapping:
                        fk_mapping[fk_prefix] = target_table
                        logger.debug(f"[SchemaCompleter] Built FK mapping: {fk_prefix} -> {target_table}")
        
        # 补充基于表名的推断规则
        # 例如: 如果存在表 'users'/'categories' 等，且无映射，则添加
        for table in self._all_tables:
            # users -> user, categories -> category 等
            if table.endswith('s') and len(table) > 2:
                prefix = table[:-1]  # users -> user
                if prefix not in fk_mapping:
                    fk_mapping[prefix] = table
            elif table.endswith('ies') and len(table) > 4:
                prefix = table[:-3] + 'y'  # categories -> category
                if prefix not in fk_mapping:
                    fk_mapping[prefix] = table
        
        logger.info(f"[SchemaCompleter] Built {len(fk_mapping)} FK mappings from graph")
        return fk_mapping
    
    def check_completeness(self,
                          sql: Optional[str], 
                          selected_tables: List[str],
                          schema_context: str) -> SchemaCheckResult:
        """
        检查Schema完整性
        
        检测方法：
        1. 从已召回表的Schema中提取所有外键列
        2. 推断每个外键指向的目标表
        3. 检查目标表是否在已选表中
        4. 通过图谱验证是否存在需要的关联
        
        Args:
            sql: 生成的SQL（可能为None，表示生成失败）
            selected_tables: 已召回的表名列表
            schema_context: 已召回的Schema上下文
            
        Returns:
            SchemaCheckResult: 检查结果
            
        Author: CYJ
        Time: 2025-11-25
        """
        missing_tables = set()
        evidence = []
        fk_analysis = []
        
        selected_set = set(selected_tables)
        
        # Step 1: 从Schema上下文中提取已召回表的外键列
        fk_columns = self._extract_fk_columns_from_context(schema_context)
        logger.info(f"[SchemaCompleter] Found FK columns: {fk_columns}")
        
        # Step 2: 推断每个外键指向的目标表
        for fk_col in fk_columns:
            target_table = self._infer_fk_target(fk_col)
            if target_table and target_table not in selected_set:
                missing_tables.add(target_table)
                evidence.append(f"外键列 {fk_col} 指向表 {target_table}，但该表未被召回")
                fk_analysis.append({
                    "fk_column": fk_col,
                    "target_table": target_table,
                    "status": "missing"
                })
            elif target_table:
                fk_analysis.append({
                    "fk_column": fk_col,
                    "target_table": target_table,
                    "status": "present"
                })
        
        # Step 3: 检查图谱中的直接关联（终点表检测）
        graph_missing = self._check_endpoint_tables(selected_tables)
        for table, reason in graph_missing.items():
            if table not in selected_set:
                missing_tables.add(table)
                evidence.append(reason)
        
        # Step 4: 如果SQL生成失败（None），检查是否有明显的关联缺失
        if sql is None:
            # 分析schema_context中是否有关于缺少关联的提示
            if "clarification" in schema_context.lower() or "缺少" in schema_context:
                evidence.append("SQL生成失败，可能是Schema信息不完整")
        
        logger.info(f"[SchemaCompleter] Missing tables: {missing_tables}")
        logger.info(f"[SchemaCompleter] Evidence: {evidence}")
        
        return SchemaCheckResult(
            is_complete=len(missing_tables) == 0,
            missing_tables=list(missing_tables),
            evidence=evidence,
            confidence=0.9 if missing_tables else 1.0,
            fk_analysis=fk_analysis
        )
    
    def _extract_fk_columns_from_context(self, schema_context: str) -> List[str]:
        """
        从Schema上下文中提取外键列
        
        识别模式：
        - table.column_id
        - column_id: 描述
        - column_code: 描述
        
        Args:
            schema_context: Schema上下文字符串
            
        Returns:
            外键列列表，格式为 table.column 或 column
            
        Author: CYJ
        Time: 2025-11-25
        """
        fk_columns = []
        
        # 模式1: [table] 后跟列信息
        # 匹配格式如: [orders]\n  - user_id: 用户ID
        table_pattern = r'\[(\w+)\]'
        column_pattern = r'-\s*(\w+(?:_id|_code))\s*:'
        
        current_table = None
        for line in schema_context.split('\n'):
            # 检查是否是表名行
            table_match = re.search(table_pattern, line)
            if table_match:
                current_table = table_match.group(1)
                continue
            
            # 检查是否有外键列
            col_match = re.search(column_pattern, line, re.IGNORECASE)
            if col_match and current_table:
                col_name = col_match.group(1)
                fk_columns.append(f"{current_table}.{col_name}")
        
        # 模式2: 直接匹配 table.column_id 格式
        direct_pattern = r'(\w+)\.(\w+(?:_id|_code))'
        for match in re.finditer(direct_pattern, schema_context, re.IGNORECASE):
            full_name = f"{match.group(1)}.{match.group(2)}"
            if full_name not in fk_columns:
                fk_columns.append(full_name)
        
        return fk_columns
    
    def _infer_fk_target(self, fk_column: str) -> Optional[str]:
        """
        推断外键列指向的目标表 (V2: 使用动态映射)
        
        推断规则：
        1. 使用从图谱动态构建的FK映射
        2. 根据列名模式推断：user_id -> users, category_id -> categories
        3. 通过图谱验证
        
        V2更新：使用_fk_target_mapping替代硬编码的FK_TARGET_MAPPING
        
        Args:
            fk_column: 外键列名，格式为 table.column 或 column
            
        Returns:
            目标表名，如果无法推断则返回None
            
        Author: CYJ
        Time: 2025-11-25 (V2重构)
        """
        # 解析表名和列名
        if '.' in fk_column:
            source_table, col_name = fk_column.split('.', 1)
        else:
            source_table = None
            col_name = fk_column
        
        # 提取外键前缀
        fk_prefix = None
        for suffix in self.FK_SUFFIXES:
            if col_name.endswith(suffix):
                fk_prefix = col_name[:-len(suffix)]
                break
        
        if not fk_prefix:
            return None
        
        # 跳过自关联
        if fk_prefix == 'parent':
            return None
        
        # V2: 使用动态构建的FK映射
        if fk_prefix in self._fk_target_mapping:
            return self._fk_target_mapping[fk_prefix]
        
        # 尝试推断：prefix -> prefix + 's' 或 dim_prefix
        candidates = [
            fk_prefix + 's',           # user -> users
            'dim_' + fk_prefix,        # region -> dim_region
            fk_prefix,                  # 完全匹配
        ]
        
        for candidate in candidates:
            if candidate in self._all_tables:
                return candidate
        
        # 通过图谱验证（如果有source_table）
        if source_table:
            for rel in self._graph_relations:
                if rel['source'] == source_table:
                    condition = rel.get('properties', {}).get('condition', '')
                    if col_name in condition:
                        return rel['target']
        
        return None
    
    def _check_endpoint_tables(self, selected_tables: List[str]) -> Dict[str, str]:
        """
        检查图谱中的终点表（叶子节点）
        
        设计原理：
        图路径补全只能找到两个已选表之间的中间表，
        但无法找到从已选表出发的终点表。
        此方法专门检测这种情况。
        
        Args:
            selected_tables: 已选择的表列表
            
        Returns:
            Dict[str, str]: {缺失的表名: 原因}
            
        Author: CYJ
        Time: 2025-11-25
        """
        missing = {}
        selected_set = set(selected_tables)
        
        for rel in self._graph_relations:
            source = rel['source']
            target = rel['target']
            
            # 如果源表在已选表中，但目标表不在
            # 且目标表是一个"重要"的维度表或基础表
            if source in selected_set and target not in selected_set:
                # 判断目标表是否重要
                if self._is_important_endpoint(target, source):
                    condition = rel.get('properties', {}).get('condition', '')
                    missing[target] = f"表 {source} 通过 {condition} 关联到 {target}，但 {target} 未被召回"
        
        return missing
    
    def _is_important_endpoint(self, table: str, source: str) -> bool:
        """
        判断一个表是否是重要的终点表
        
        重要终点表的特征：
        1. 维度表（dim_*）
        2. 基础实体表（categories, logistics_providers等）
        3. 不是自关联
        
        Args:
            table: 目标表名
            source: 源表名
            
        Returns:
            是否是重要的终点表
            
        Author: CYJ
        Time: 2025-11-25
        """
        # 自关联不算
        if table == source:
            return False
        
        # 维度表始终重要
        if table.startswith('dim_'):
            return True
        
        # 基础实体表
        important_tables = {
            'categories', 'logistics_providers', 'users', 'shops',
            'products', 'coupons'
        }
        
        return table in important_tables
    
    async def complete_schema(self, 
                             user_query: str,
                             current_tables: List[str], 
                             missing_tables: List[str],
                             current_context: str = "") -> 'SchemaCompletionResult':
        """
        补全Schema上下文
        
        Args:
            user_query: 用户原始查询
            current_tables: 当前已召回的表
            missing_tables: 需要补充召回的表
            current_context: 当前的Schema上下文
            
        Returns:
            SchemaCompletionResult: 补全结果
            
        Author: CYJ
        Time: 2025-11-25
        """
        from app.modules.diagnosis.models import SchemaCompletionResult
        
        try:
            additional_context = "\n\n[Supplementary Tables - Auto Completed]\n"
            added_tables = []
            
            for table in missing_tables:
                if table in current_tables:
                    continue
                
                # 获取表信息
                table_info = self._get_table_info(table)
                if table_info:
                    additional_context += f"\n[{table}]\n{table_info}"
                    added_tables.append(table)
                    logger.info(f"[SchemaCompleter] Added supplementary table: {table}")
            
            # 添加关联关系提示
            join_hints = self._get_join_hints(current_tables, missing_tables)
            if join_hints:
                additional_context += "\n\n[Join Hints]\n" + join_hints
            
            complete_ddl = current_context + additional_context if current_context else additional_context
            
            return SchemaCompletionResult(
                success=len(added_tables) > 0,
                added_tables=added_tables,
                complete_ddl=complete_ddl,
                error=""
            )
            
        except Exception as e:
            logger.error(f"[SchemaCompleter] complete_schema failed: {e}")
            return SchemaCompletionResult(
                success=False,
                added_tables=[],
                complete_ddl="",
                error=str(e)
            )
    
    def _get_table_info(self, table_name: str) -> Optional[str]:
        """
        获取表的Schema信息
        
        通过VectorStore或Catalog获取表的列信息
        
        Args:
            table_name: 表名
            
        Returns:
            表的Schema信息字符串
            
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            from app.modules.schema.catalog import get_schema_catalog
            
            catalog = get_schema_catalog()
            columns = catalog.list_columns_by_table(table_name)
            
            if not columns:
                return None
            
            lines = []
            for col in columns:
                desc = col.get('description', '')[:50]
                lines.append(f"  - {col['name']}: {desc}")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return None
    
    def _get_join_hints(self, existing_tables: List[str], new_tables: List[str]) -> str:
        """
        获取表之间的JOIN提示
        
        Args:
            existing_tables: 已有的表
            new_tables: 新增的表
            
        Returns:
            JOIN条件提示字符串
            
        Author: CYJ
        Time: 2025-11-25
        """
        hints = []
        
        for rel in self._graph_relations:
            source = rel['source']
            target = rel['target']
            
            # 检查是否是已有表和新增表之间的关联
            if (source in existing_tables and target in new_tables) or \
               (source in new_tables and target in existing_tables):
                condition = rel.get('properties', {}).get('condition', '')
                if condition:
                    hints.append(f"- {source} <-> {target}: {condition}")
        
        return "\n".join(hints)
