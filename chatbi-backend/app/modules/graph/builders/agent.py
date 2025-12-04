"""
功能：关系推断Agent (Relationship Inference Agent)
说明:
    使用LLM分析数据库表结构，从零生成表关系数据。
    
    核心能力:
    1. 读取 full_schema.json 元数据
    2. 分析表名/列名的语义含义
    3. 推断表间关联关系
    4. 使用 structured output 确保输出格式正确
    5. 支持分批处理大表场景
    
    使用方式:
        agent = get_relationship_inference_agent()
        result = agent.generate_relationships()
        # result.relationships 是推断出的关系列表

Author: CYJ
Time: 2025-12-03
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from langchain_core.messages import SystemMessage, HumanMessage

from app.core.llm import get_llm
from app.core.config import get_settings
from app.services.graph_builder_service import get_graph_builder_service
from .schemas import (
    RelationshipList, 
    Relationship, 
    RelationshipProperties,
    TableInfo, 
    ColumnInfo,
    InferenceResult
)
from .prompts import SYSTEM_PROMPT, build_inference_prompt, build_simplified_prompt

logger = logging.getLogger(__name__)
_settings = get_settings()

class RelationshipInferenceAgent:
    """
    关系推断Agent - 从元数据生成关系JSON
    
    核心功能:
    1. 加载Schema数据
    2. 过滤/简化列信息（减少Token）
    3. 分批处理大表
    4. 调用LLM推断关系
    5. 合并去重结果
    
    Author: CYJ
    Time: 2025-12-03
    """
    
    # 需要过滤的通用列（不参与关系推断）
    SKIP_COLUMNS = {
        "created_at", "updated_at", "deleted_at", "create_time", "update_time",
        "created_by", "updated_by", "is_deleted", "version", "remark", "remarks"
    }
    
    # 外键列后缀
    FK_SUFFIXES = ("_id", "_code")
    
    def __init__(self):
        """
        初始化Agent
        
        Author: CYJ
        Time: 2025-12-03
        """
        self.llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
        self.graph_service = get_graph_builder_service()
        
        # 使用 structured output 确保输出格式
        self.structured_llm = self.llm.with_structured_output(RelationshipList)
    
    def generate_relationships(
        self,
        tables: Optional[List[str]] = None,
        batch_size: int = 10
    ) -> InferenceResult:
        """
        生成表关系
        
        这是主入口方法，从Sche ma生成完整的关系列表。
        
        Args:
            tables: 要分析的表名列表，为None则分析所有表
            batch_size: 分批大小，默认10个表一批
            
        Returns:
            InferenceResult 包含推断结果
            
        Author: CYJ
        Time: 2025-12-03
        """
        try:
            # Step 1: 加载Schema
            schema_data = self.graph_service.get_schema()
            if not schema_data:
                return InferenceResult(
                    relationships=[],
                    tables_analyzed=0,
                    total_batches=0,
                    success=False,
                    message="Schema not found. Please extract schema first."
                )
            
            # Step 2: 提取表信息
            all_tables = self._extract_table_info(schema_data)
            logger.info(f"[RelationshipInferenceAgent] Loaded {len(all_tables)} tables from schema")
            
            # 过滤指定表
            if tables:
                all_tables = [t for t in all_tables if t.name in tables]
                logger.info(f"[RelationshipInferenceAgent] Filtered to {len(all_tables)} specified tables")
            
            if not all_tables:
                return InferenceResult(
                    relationships=[],
                    tables_analyzed=0,
                    total_batches=0,
                    success=True,
                    message="No tables to analyze"
                )
            
            # Step 3: 分批处理
            table_names = {t.name for t in all_tables}
            batches = self._group_tables_by_domain(all_tables, batch_size)
            logger.info(f"[RelationshipInferenceAgent] Split into {len(batches)} batches")
            
            # Step 4: 推断关系
            all_relationships: List[Relationship] = []
            
            for i, batch in enumerate(batches):
                logger.info(f"[RelationshipInferenceAgent] Processing batch {i+1}/{len(batches)}: {[t.name for t in batch]}")
                
                try:
                    batch_relations = self._infer_batch(batch, table_names)
                    all_relationships.extend(batch_relations)
                    logger.info(f"[RelationshipInferenceAgent] Batch {i+1} found {len(batch_relations)} relationships")
                except Exception as e:
                    logger.error(f"[RelationshipInferenceAgent] Batch {i+1} failed: {e}")
                    continue
            
            # Step 5: 去重
            unique_relations = self._deduplicate_relationships(all_relationships)
            logger.info(f"[RelationshipInferenceAgent] Total unique relationships: {len(unique_relations)}")
            
            return InferenceResult(
                relationships=unique_relations,
                tables_analyzed=len(all_tables),
                total_batches=len(batches),
                success=True,
                message=f"Successfully inferred {len(unique_relations)} relationships from {len(all_tables)} tables"
            )
            
        except Exception as e:
            logger.error(f"[RelationshipInferenceAgent] Generation failed: {e}")
            return InferenceResult(
                relationships=[],
                tables_analyzed=0,
                total_batches=0,
                success=False,
                message=f"Generation failed: {str(e)}"
            )
    
    def _extract_table_info(self, schema_data: Dict[str, Any]) -> List[TableInfo]:
        """
        从Sche ma数据提取表信息
        
        只保留推断关系所需的字段，减少Token消耗。
        
        Author: CYJ
        Time: 2025-12-03
        """
        tables = []
        
        for table_data in schema_data.get("tables", []):
            columns = []
            
            for col_data in table_data.get("columns", []):
                col_name = col_data.get("name", "")
                
                # 过滤通用列
                if col_name.lower() in self.SKIP_COLUMNS:
                    continue
                
                # 只保留可能参与关系的列：主键、外键、_id、_code
                is_pk = col_data.get("is_primary_key", False)
                is_fk = col_data.get("is_foreign_key", False)
                is_potential_fk = any(col_name.lower().endswith(suffix) for suffix in self.FK_SUFFIXES)
                
                if is_pk or is_fk or is_potential_fk or col_name.lower() == "id":
                    columns.append(ColumnInfo(
                        name=col_name,
                        data_type=col_data.get("data_type", ""),
                        comment=col_data.get("comment"),
                        is_primary_key=is_pk,
                        is_foreign_key=is_fk
                    ))
            
            tables.append(TableInfo(
                name=table_data.get("name", ""),
                comment=table_data.get("comment"),
                columns=columns
            ))
        
        return tables
    
    def _group_tables_by_domain(
        self, 
        tables: List[TableInfo], 
        batch_size: int
    ) -> List[List[TableInfo]]:
        """
        按业务域分组表
        
        策略:
        1. 按表名前缀分组（order_*, user_*, dim_*）
        2. 相关表放在同一批次
        3. 每批不超过batch_size
        
        Author: CYJ
        Time: 2025-12-03
        """
        # 按前缀分组
        prefix_groups: Dict[str, List[TableInfo]] = defaultdict(list)
        
        for table in tables:
            # 提取前缀（第一个下划线前的部分）
            name = table.name.lower()
            if "_" in name:
                prefix = name.split("_")[0]
            else:
                prefix = name
            
            prefix_groups[prefix].append(table)
        
        # 构建批次
        batches: List[List[TableInfo]] = []
        current_batch: List[TableInfo] = []
        
        for prefix, group_tables in sorted(prefix_groups.items()):
            for table in group_tables:
                current_batch.append(table)
                
                if len(current_batch) >= batch_size:
                    batches.append(current_batch)
                    current_batch = []
        
        # 添加剩余的表
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _infer_batch(
        self, 
        tables: List[TableInfo],
        all_table_names: Set[str]
    ) -> List[Relationship]:
        """
        对一批表进行关系推断
        
        Args:
        tables: 要分析的表列表
            all_table_names: 所有表名集合（用于验证目标表存在）
            
        Returns:
            推断出的关系列表
            
        Author: CYJ
        Time: 2025-12-03
        """
        # 构建表信息JSON
        tables_json = self._build_tables_json(tables)
        
        # 构建Prompt
        user_prompt = build_inference_prompt(tables_json)
        
        # 调用LLM
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            result: RelationshipList = self.structured_llm.invoke(messages)
            
            # 过滤无效关系
            valid_relations = []
            for rel in result.relationships:
            # 验证源表和目标表都存在
                if rel.source in all_table_names and rel.target in all_table_names:
                    valid_relations.append(rel)
                else:
                    logger.warning(
                        f"[RelationshipInferenceAgent] Skipping invalid relation: "
                        f"{rel.source} -> {rel.target} (table not found)"
                    )
            
            return valid_relations
            
        except Exception as e:
            logger.error(f"[RelationshipInferenceAgent] LLM inference failed: {e}")
            return []
    
    def _build_tables_json(self, tables: List[TableInfo]) -> str:
        """
        构建表信息JSON字符串（用于Prompt）
        
        Author: CYJ
        Time: 2025-12-03
        """
        tables_data = []
        
        for table in tables:
            table_dict = {
                "name": table.name,
                "comment": table.comment or "",
                "columns": [
                    {
                        "name": col.name,
                        "type": col.data_type,
                        "comment": col.comment or "",
                        "is_pk": col.is_primary_key,
                        "is_fk": col.is_foreign_key
                    }
                    for col in table.columns
                ]
            }
            tables_data.append(table_dict)
        
        return json.dumps(tables_data, ensure_ascii=False, indent=2)
    
    def _deduplicate_relationships(
        self, 
        relationships: List[Relationship]
    ) -> List[Relationship]:
        """
        去重关系
        
        去重规则: 相同的 source + target + condition
        
        Author: CYJ
        Time: 2025-12-03
        """
        seen: Set[str] = set()
        unique: List[Relationship] = []
        
        for rel in relationships:
            # 生成唯一键
            key = f"{rel.source}|{rel.target}|{rel.properties.condition}"
            
            if key not in seen:
                seen.add(key)
                unique.append(rel)
        
        return unique
    
    def to_dict_list(self, relationships: List[Relationship]) -> List[Dict[str, Any]]:
        """
        将关系列表转换为字典列表（用于保存JSON）
        
        Author: CYJ
        Time: 2025-12-03
        """
        return [rel.model_dump() for rel in relationships]

# ============================================================================
# 单例模式
# ============================================================================

_relationship_inference_agent: Optional[RelationshipInferenceAgent] = None

def get_relationship_inference_agent() -> RelationshipInferenceAgent:
    """
    获取 RelationshipInferenceAgent 单例
    
    Returns:
        RelationshipInferenceAgent 实例
        
    Author: CYJ
    Time: 2025-12-03
    """
    global _relationship_inference_agent
    if _relationship_inference_agent is None:
        _relationship_inference_agent = RelationshipInferenceAgent()
    return _relationship_inference_agent
