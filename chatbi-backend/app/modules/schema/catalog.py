"""
功能：Schema Catalog 服务 (Schema Metadata Service)
说明：
    提供运行时获取数据库表/列元数据的能力。
    用于引导式召回：给 LLM 提供候选集合，而非硬编码映射。
作者：CYJ
时间：2025-11-25
"""
import logging
from typing import List, Dict, Optional, Tuple
from sqlalchemy import text
from app.modules.vector.store import VectorStore
from app.modules.graph.service import GraphService

logger = logging.getLogger(__name__)


class SchemaCatalog:
    """
    Schema 元数据目录服务
    
    职责：
    1. 从 pgvector 获取表/列的名称和描述
    2. 从 Neo4j 获取外键关系
    3. 提供候选集合给 LLM 进行引导式选择
    
    Author: CYJ
    """
    
    _instance = None
    _cache: Dict[str, any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchemaCatalog, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._store = VectorStore()
        self._graph = GraphService()
        self._initialized = True
    
    def list_tables(self, with_description: bool = True) -> List[Dict[str, str]]:
        """
        获取所有表名及简短描述
        
        Args:
            with_description: 是否包含描述信息
            
        Returns:
            List[Dict]: [{"name": "orders", "description": "订单表"}, ...]
            
        Author: CYJ
        Time: 2025-11-25
        """
        cache_key = f"tables_{with_description}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            session = self._store.Session()
            if with_description:
                query = text("""
                    SELECT object_name, 
                           COALESCE(LEFT(original_description, 100), '') as description
                    FROM schema_embeddings 
                    WHERE object_type = 'table'
                    ORDER BY object_name
                """)
                results = session.execute(query).fetchall()
                tables = [{"name": row[0], "description": row[1]} for row in results]
            else:
                query = text("""
                    SELECT object_name 
                    FROM schema_embeddings 
                    WHERE object_type = 'table'
                    ORDER BY object_name
                """)
                results = session.execute(query).fetchall()
                tables = [{"name": row[0]} for row in results]
            
            session.close()
            self._cache[cache_key] = tables
            return tables
            
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []
    
    def list_table_names(self) -> List[str]:
        """
        获取所有表名（纯列表）
        
        Returns:
            List[str]: ["orders", "users", "dim_region", ...]
            
        Author: CYJ
        Time: 2025-11-25
        """
        tables = self.list_tables(with_description=False)
        return [t["name"] for t in tables]
    
    def list_columns_by_table(self, table_name: str) -> List[Dict[str, str]]:
        """
        获取指定表的所有列
        
        Args:
            table_name: 表名
            
        Returns:
            List[Dict]: [{"name": "id", "description": "主键ID"}, ...]
            
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            session = self._store.Session()
            query = text("""
                SELECT object_name, 
                       COALESCE(LEFT(original_description, 100), '') as description
                FROM schema_embeddings 
                WHERE object_type = 'column' 
                  AND object_name LIKE :pattern
                ORDER BY object_name
            """)
            results = session.execute(query, {"pattern": f"{table_name}.%"}).fetchall()
            columns = [
                {"name": row[0].split('.')[-1], "full_name": row[0], "description": row[1]} 
                for row in results
            ]
            session.close()
            return columns
            
        except Exception as e:
            logger.error(f"Failed to list columns for {table_name}: {e}")
            return []
    
    def list_all_columns(self) -> List[Dict[str, str]]:
        """
        获取所有列（带表归属）
        
        Returns:
            List[Dict]: [{"table": "orders", "column": "id", "full_name": "orders.id"}, ...]
            
        Author: CYJ
        Time: 2025-11-25
        """
        cache_key = "all_columns"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            session = self._store.Session()
            query = text("""
                SELECT object_name, 
                       COALESCE(LEFT(original_description, 80), '') as description
                FROM schema_embeddings 
                WHERE object_type = 'column'
                ORDER BY object_name
            """)
            results = session.execute(query).fetchall()
            columns = []
            for row in results:
                full_name = row[0]
                parts = full_name.split('.')
                if len(parts) == 2:
                    columns.append({
                        "table": parts[0],
                        "column": parts[1],
                        "full_name": full_name,
                        "description": row[1]
                    })
            session.close()
            self._cache[cache_key] = columns
            return columns
            
        except Exception as e:
            logger.error(f"Failed to list all columns: {e}")
            return []
    
    def get_fk_columns(self) -> List[Dict[str, str]]:
        """
        获取所有外键列（以 _id 或 _code 结尾的列）
        
        Returns:
            List[Dict]: [{"column": "orders.user_id", "pattern": "_id"}, ...]
            
        Author: CYJ
        Time: 2025-11-25
        """
        cache_key = "fk_columns"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            session = self._store.Session()
            query = text("""
                SELECT object_name
                FROM schema_embeddings 
                WHERE object_type = 'column'
                  AND (object_name LIKE '%_id' OR object_name LIKE '%_code')
                ORDER BY object_name
            """)
            results = session.execute(query).fetchall()
            fk_cols = []
            for row in results:
                col_name = row[0]
                pattern = "_id" if col_name.endswith("_id") else "_code"
                fk_cols.append({"column": col_name, "pattern": pattern})
            session.close()
            self._cache[cache_key] = fk_cols
            return fk_cols
            
        except Exception as e:
            logger.error(f"Failed to get FK columns: {e}")
            return []
    
    def get_fk_target_table(self, fk_column: str) -> Optional[str]:
        """
        通过 Neo4j 图谱查询外键列指向的目标表
        
        Args:
            fk_column: 外键列全名，如 "orders.shipping_region_id"
            
        Returns:
            目标表名，如 "dim_region"；未找到则返回 None
            
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            # 解析表名和列名
            parts = fk_column.split('.')
            if len(parts) != 2:
                return None
            table_name, col_name = parts
            
            # 方案1：通过 Neo4j 查询 JOIN_ON 关系
            self._graph.connect()
            query = """
            MATCH (t1:Table {name: $table_name})-[r:JOIN_ON]->(t2:Table)
            WHERE r.left_key = $col_name OR r.condition CONTAINS $col_name
            RETURN t2.name as target_table
            LIMIT 1
            """
            with self._graph._driver.session() as session:
                result = session.run(query, {"table_name": table_name, "col_name": col_name})
                record = result.single()
                if record:
                    return record["target_table"]
            
            # 方案2：通过列名模式推断（回退）
            # shipping_region_id -> dim_region (去掉前缀+_id)
            # user_id -> users
            # shop_id -> shops
            col_base = col_name.replace("_id", "").replace("_code", "")
            
            # 尝试匹配表名
            all_tables = self.list_table_names()
            
            # 精确匹配
            for t in all_tables:
                if t == col_base or t == f"dim_{col_base}" or t == f"{col_base}s":
                    return t
            
            # 模糊匹配（包含关系）
            for t in all_tables:
                if col_base in t or t in col_base:
                    return t
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get FK target for {fk_column}: {e}")
            return None
    
    def get_join_path(self, source_table: str, target_table: str) -> Optional[Dict]:
        """
        获取两个表之间的 JOIN 路径
        
        Args:
            source_table: 源表名
            target_table: 目标表名
            
        Returns:
            Dict: {"path": ["orders", "dim_region"], "condition": "orders.shipping_region_id = dim_region.id"}
            
        Author: CYJ
        Time: 2025-11-25
        """
        try:
            self._graph.connect()
            query = """
            MATCH (t1:Table {name: $source})-[r:JOIN_ON]-(t2:Table {name: $target})
            RETURN r.condition as condition, r.left_key as left_key, r.right_key as right_key
            LIMIT 1
            """
            with self._graph._driver.session() as session:
                result = session.run(query, {"source": source_table, "target": target_table})
                record = result.single()
                if record:
                    return {
                        "path": [source_table, target_table],
                        "condition": record["condition"],
                        "left_key": record["left_key"],
                        "right_key": record["right_key"]
                    }
            return None
            
        except Exception as e:
            logger.error(f"Failed to get join path: {e}")
            return None
    
    def get_columns_for_tables(self, table_names: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """
        按需获取指定表的列信息（分层检索第 2 层）
        
        设计原理：
        避免一次性加载所有表的列信息，只获取 LLM 选定的表的列。
        这样可以大幅减少 Token 消耗。
        
        Args:
            table_names: 表名列表，如 ["orders", "dim_region"]
            
        Returns:
            Dict: {
                "orders": [{"name": "id", "description": "主键"}, ...],
                "dim_region": [{"name": "city", "description": "城市"}, ...]
            }
            
        Author: CYJ
        Time: 2025-11-25
        """
        result = {}
        for table_name in table_names:
            cols = self.list_columns_by_table(table_name)
            result[table_name] = cols
        return result
    
    def format_tables_for_prompt(self, max_tables: int = 20) -> str:
        """
        格式化表信息用于 LLM Prompt
        
        Args:
            max_tables: 最大表数量
            
        Returns:
            格式化的字符串，如：
            - orders: 订单表
            - users: 用户表
            ...
            
        Author: CYJ
        Time: 2025-11-25
        """
        tables = self.list_tables(with_description=True)[:max_tables]
        lines = [f"- {t['name']}: {t['description']}" for t in tables]
        return "\n".join(lines)
    
    def format_tables_only_for_prompt(self) -> str:
        """
        格式化表名列表用于分层检索第 1 层（只有表名，不含列）
        
        设计原理：
        第一层只提供表名和简短描述（~200 token），让 LLM 选择相关表。
        之后再获取选中表的列信息。
        
        Returns:
            格式化字符串，如：
            1. orders - 订单主表，存储所有订单信息
            2. users - 用户表
            ...
            
        Author: CYJ
        Time: 2025-11-25
        """
        tables = self.list_tables(with_description=True)
        lines = []
        for i, t in enumerate(tables, 1):
            # 截断描述，避免太长
            desc = t.get('description', '')[:50]
            lines.append(f"{i}. {t['name']} - {desc}")
        return "\n".join(lines)
    
    def format_columns_for_tables(self, table_names: List[str]) -> str:
        """
        格式化指定表的列信息用于分层检索第 2 层
        
        Args:
            table_names: 表名列表
            
        Returns:
            格式化字符串，如：
            [orders]
            - id: 订单ID
            - user_id: 用户ID
            ...
            
        Author: CYJ
        Time: 2025-11-25
        """
        cols_data = self.get_columns_for_tables(table_names)
        lines = []
        for table_name, columns in cols_data.items():
            lines.append(f"[{table_name}]")
            for col in columns:
                desc = col.get('description', '')[:40]
                lines.append(f"  - {col['name']}: {desc}")
        return "\n".join(lines)
    
    def clear_cache(self):
        """
        清除缓存
        
        Author: CYJ
        Time: 2025-11-25
        """
        self._cache.clear()
        logger.info("Schema catalog cache cleared")


# 全局单例
_catalog_instance: Optional[SchemaCatalog] = None


def get_schema_catalog() -> SchemaCatalog:
    """
    获取 Schema Catalog 单例
    
    Author: CYJ
    Time: 2025-11-25
    """
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = SchemaCatalog()
    return _catalog_instance
