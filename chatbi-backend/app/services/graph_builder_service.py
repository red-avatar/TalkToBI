"""
功能：图谱构建服务 (Graph Builder Service)
说明:
    封装知识图谱构建的核心操作，包括：
    1. Schema 提取：从 MySQL 提取元数据
    2. 关系 JSON 读写：读取/保存本地 relationships.json
    3. Neo4j 同步：将本地 JSON 同步到 Neo4j 图谱
    
    该服务是 scripts/knowledge/ 下脚本功能的 API 化封装。

使用方式:
    service = get_graph_builder_service()
    
    # 提取Schema
    schema = service.extract_schema()
    
    # 读取本地关系
    relations = service.get_local_relationships()
    
    # 保存关系
    service.save_local_relationships(relations)
    
    # 同步到Neo4j
    service.sync_to_neo4j()

Author: CYJ
Time: 2025-12-03
"""

import json
import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from app.modules.schema.loader import SchemaLoader
from app.modules.graph.service import GraphService
from app.schemas.db_schema import SchemaMetadata

logger = logging.getLogger(__name__)

# 数据文件路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "scripts", "knowledge", "data"
)
SCHEMA_FILE = os.path.join(DATA_DIR, "full_schema.json")
RELATIONSHIPS_FILE = os.path.join(DATA_DIR, "relationships_enhanced.json")

@dataclass
class SyncResult:
    """Neo4j同步结果"""
    success: bool
    tables_count: int
    columns_count: int
    relations_count: int
    message: str

class GraphBuilderService:
    """
    图谱构建服务
    
    封装知识图谱构建的核心操作：
    1. extract_schema: 从 MySQL 提取元数据
    2. get_local_relationships: 读取本地关系 JSON
    3. save_local_relationships: 保存关系到本地 JSON
    4. sync_to_neo4j: 将本地 JSON 同步到 Neo4j
    
    Author: CYJ
    Time: 2025-12-03
    """
    
    def __init__(self):
        """
        初始化服务
        
        Author: CYJ
        Time: 2025-12-03
        """
        self._ensure_data_dir()
    
    def _ensure_data_dir(self) -> None:
        """确保数据目录存在"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            logger.info(f"[GraphBuilderService] Created data directory: {DATA_DIR}")
    
    def extract_schema(self) -> Dict[str, Any]:
        """
        从MySQL提取元数据并保存到full_schema.json
        
        Returns:
            提取的Schema数据字典
            
        Author: CYJ
        Time: 2025-12-03
        """
        try:
            logger.info("[GraphBuilderService] Starting schema extraction from MySQL...")
            
            loader = SchemaLoader()
            table_schemas = loader.extract_full_schema()
            
            # 构建数据结构
            data = {
                "database_name": str(loader.engine.url.database),
                "tables": [t.model_dump() for t in table_schemas]
            }
            
            # 保存到文件
            with open(SCHEMA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[GraphBuilderService] Schema extracted: {len(table_schemas)} tables saved to {SCHEMA_FILE}")
            return data
            
        except Exception as e:
            logger.error(f"[GraphBuilderService] Schema extraction failed: {e}")
            raise
    
    def get_schema(self) -> Optional[Dict[str, Any]]:
        """
        获取已提取的Schema数据
        
        Returns:
            Schema数据字典，如果文件不存在返回None
            
        Author: CYJ
        Time: 2025-12-03
        """
        if not os.path.exists(SCHEMA_FILE):
            logger.warning(f"[GraphBuilderService] Schema file not found: {SCHEMA_FILE}")
            return None
        
        try:
            with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[GraphBuilderService] Failed to read schema file: {e}")
            return None
    
    def get_local_relationships(self) -> List[Dict[str, Any]]:
        """
        读取本地关系JSON文件
        
        Returns:
            关系列表，如果文件不存在返回空列表
            
        Author: CYJ
        Time: 2025-12-03
        """
        if not os.path.exists(RELATIONSHIPS_FILE):
            logger.warning(f"[GraphBuilderService] Relationships file not found: {RELATIONSHIPS_FILE}")
            return []
        
        try:
            with open(RELATIONSHIPS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 确保返回列表
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "relationships" in data:
                    return data["relationships"]
                else:
                    logger.warning("[GraphBuilderService] Unexpected relationships format")
                    return []
        except Exception as e:
            logger.error(f"[GraphBuilderService] Failed to read relationships file: {e}")
            return []
    
    def save_local_relationships(self, relationships: List[Dict[str, Any]]) -> bool:
        """
        保存关系到本地JSON文件
        
        Args:
            relationships: 关系列表
            
        Returns:
            是否保存成功
            
        Author: CYJ
        Time: 2025-12-03
        """
        try:
            self._ensure_data_dir()
            
            with open(RELATIONSHIPS_FILE, 'w', encoding='utf-8') as f:
                json.dump(relationships, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[GraphBuilderService] Saved {len(relationships)} relationships to {RELATIONSHIPS_FILE}")
            return True
            
        except Exception as e:
            logger.error(f"[GraphBuilderService] Failed to save relationships: {e}")
            return False
    
    def sync_to_neo4j(self) -> SyncResult:
        """
        将本地JSON同步到Neo4j图谱
        
        这是 scripts/knowledge/build_graph.py 的 API 化封装。
        
        Returns:
            SyncResult 包含同步结果信息
            
        Author: CYJ
        Time: 2025-12-03
        """
        # 检查必要文件
        if not os.path.exists(SCHEMA_FILE):
            return SyncResult(
                success=False,
                tables_count=0,
                columns_count=0,
                relations_count=0,
                message=f"Schema file not found: {SCHEMA_FILE}. Please extract schema first."
            )
        
        try:
            logger.info("[GraphBuilderService] Starting Neo4j sync...")
            
            # 加载Schema
            with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                schema_data = json.load(f)
            schema = SchemaMetadata(**schema_data)
            
            # 加载关系（可选）
            rel_data = self.get_local_relationships()
            
            # 连接Neo4j
            graph_service = GraphService()
            graph_service.connect()
            
            try:
                # 清空现有图谱
                logger.info("[GraphBuilderService] Clearing existing graph...")
                graph_service.clear_graph()
                
                # Step 1: 创建表和列节点
                tables_count = len(schema.tables)
                columns_count = 0
                
                logger.info(f"[GraphBuilderService] Creating {tables_count} tables...")
                for table in schema.tables:
                    graph_service.create_table_node(table.name, table.comment or "")
                    
                    for col in table.columns:
                        graph_service.create_column_node(
                            table.name,
                            col.name,
                            col.data_type,
                            col.comment or ""
                        )
                        columns_count += 1
                
                # Step 2: 创建关系
                relations_count = 0
                
                if rel_data:
                    logger.info(f"[GraphBuilderService] Creating {len(rel_data)} relationships...")
                    for rel in rel_data:
                        try:
                            props = rel.get("properties", {})
                            condition = props.get("condition", "")
                            
                            # 解析condition获取列名
                            source_col = ""
                            target_col = ""
                            if condition and "=" in condition:
                                parts = condition.split("=")
                                left_part = parts[0].strip()
                                right_part = parts[1].strip()
                                
                                if "." in left_part:
                                    source_col = left_part.split(".")[1]
                                if "." in right_part:
                                    target_col = right_part.split(".")[1]
                            
                            graph_service.create_join_relationship(
                                rel["source"],
                                source_col,
                                rel["target"],
                                target_col,
                                relationship_type=rel.get("type", "JOIN_ON"),
                                properties=props
                            )
                            relations_count += 1
                            
                        except Exception as e:
                            logger.warning(f"[GraphBuilderService] Failed to create relationship: {rel} - {e}")
                
                # Step 3: 从关系推断列级引用
                if rel_data:
                    logger.info("[GraphBuilderService] Creating column references...")
                    for rel in rel_data:
                        props = rel.get("properties", {})
                        condition = props.get("condition", "")
                        
                        if condition and "=" in condition:
                            try:
                                parts = condition.split("=")
                                left_part = parts[0].strip()
                                right_part = parts[1].strip()
                                
                                if "." in left_part and "." in right_part:
                                    source_table, source_col = left_part.split(".")
                                    target_table, target_col = right_part.split(".")
                                    
                                    graph_service.create_column_reference(
                                        source_table,
                                        source_col,
                                        target_table,
                                        target_col,
                                        reference_type=props.get("join_type", "FOREIGN_KEY"),
                                        description=props.get("description", "")
                                    )
                            except Exception as e:
                                logger.warning(f"[GraphBuilderService] Failed to create column reference: {e}")
                
                logger.info(f"[GraphBuilderService] Neo4j sync completed successfully")
                
                return SyncResult(
                    success=True,
                    tables_count=tables_count,
                    columns_count=columns_count,
                    relations_count=relations_count,
                    message="Sync completed successfully"
                )
                
            finally:
                graph_service.close()
                
        except Exception as e:
            logger.error(f"[GraphBuilderService] Neo4j sync failed: {e}")
            return SyncResult(
                success=False,
                tables_count=0,
                columns_count=0,
                relations_count=0,
                message=f"Sync failed: {str(e)}"
            )

# 单例模式
_graph_builder_service: Optional[GraphBuilderService] = None

def get_graph_builder_service() -> GraphBuilderService:
    """
    获取 GraphBuilderService 单例
    
    Returns:
        GraphBuilderService 实例
        
    Author: CYJ
    Time: 2025-12-03
    """
    global _graph_builder_service
    if _graph_builder_service is None:
        _graph_builder_service = GraphBuilderService()
    return _graph_builder_service
