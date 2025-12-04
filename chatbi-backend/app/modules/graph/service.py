"""
功能：图谱服务 (GraphService)
说明：封装 Neo4j 驱动，提供节点（Table, Column）与关系（HAS_COLUMN, JOIN_ON）的增删改查原子操作。
作者：CYJ
时间：2025-11-20
"""
import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class GraphService:
    """
    Service for interacting with Neo4j database.
    Manages knowledge graph nodes (Table, Column) and relationships (HAS_COLUMN, JOIN_ON).
    """
    
    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self._driver: Optional[Driver] = None

    def connect(self):
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                logger.info("Connected to Neo4j")
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
                raise

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def clear_graph(self):
        """Danger: Deletes all nodes and relationships in the database."""
        query = "MATCH (n) DETACH DELETE n"
        self._execute_query(query)
        logger.warning("Graph database cleared.")

    def create_table_node(self, table_name: str, comment: str = ""):
        """Create a Table node."""
        query = """
        MERGE (t:Table {name: $name})
        SET t.comment = $comment
        """
        self._execute_query(query, {"name": table_name, "comment": comment})

    def create_column_node(self, table_name: str, column_name: str, data_type: str, comment: str = ""):
        """Create a Column node and link it to its Table."""
        query = """
        MATCH (t:Table {name: $table_name})
        MERGE (c:Column {name: $column_name, table: $table_name})
        SET c.data_type = $data_type, c.comment = $comment
        MERGE (t)-[:HAS_COLUMN]->(c)
        """
        self._execute_query(query, {
            "table_name": table_name,
            "column_name": column_name,
            "data_type": data_type,
            "comment": comment
        })

    def create_join_relationship(self, source_table: str, source_col: str, target_table: str, target_col: str, relationship_type: str = "JOIN_ON", properties: Dict[str, Any] = None):
        """
        Create a relationship between two Tables representing a JOIN condition.
        Typically used for Foreign Keys.
        Relationship: (Table A)-[:JOIN_ON {left_key: '...', right_key: '...'}]->(Table B)
        """
        props = properties or {}
        set_clause_parts = ["r.left_key = $source_col", "r.right_key = $target_col"]
        
        # Add extra properties from the dict
        for k in props.keys():
            if k not in ["left_key", "right_key"]: # Prevent overwriting core keys if passed in props
                set_clause_parts.append(f"r.{k} = ${k}")
        
        set_clause = "SET " + ", ".join(set_clause_parts)

        query = f"""
        MATCH (t1:Table {{name: $source_table}})
        MATCH (t2:Table {{name: $target_table}})
        MERGE (t1)-[r:{relationship_type}]->(t2)
        {set_clause}
        """
        
        params = {
            "source_table": source_table,
            "target_table": target_table,
            "source_col": source_col,
            "target_col": target_col,
            **props
        }
        
        self._execute_query(query, params)
    
    def create_column_reference(
        self, 
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        reference_type: str = "FOREIGN_KEY",
        cardinality: str = "N:1",
        confidence: float = 1.0,
        description: str = ""
    ):
        """
        创建字段级引用关系（核心方法）
        关系: (source_col:Column)-[:REFERENCES {type, cardinality, confidence, description}]->(target_col:Column)
        
        Author: CYJ
        Time: 2025-11-20
        """
        query = """
        MATCH (c1:Column {name: $source_column, table: $source_table})
        MATCH (c2:Column {name: $target_column, table: $target_table})
        MERGE (c1)-[r:REFERENCES]->(c2)
        SET r.type = $reference_type,
            r.cardinality = $cardinality,
            r.confidence = $confidence,
            r.description = $description
        """
        self._execute_query(query, {
            "source_table": source_table,
            "source_column": source_column,
            "target_table": target_table,
            "target_column": target_column,
            "reference_type": reference_type,
            "cardinality": cardinality,
            "confidence": confidence,
            "description": description
        })
    
    def mark_primary_key(self, table_name: str, column_name: str):
        """
        标记主键列
        关系: (col:Column)-[:IS_PRIMARY_KEY_OF]->(table:Table)
        
        Author: CYJ
        Time: 2025-11-20
        """
        query = """
        MATCH (t:Table {name: $table_name})
        MATCH (c:Column {name: $column_name, table: $table_name})
        MERGE (c)-[:IS_PRIMARY_KEY_OF]->(t)
        SET c.is_primary_key = true
        """
        self._execute_query(query, {
            "table_name": table_name,
            "column_name": column_name
        })
    
    def mark_indexed_column(self, table_name: str, column_name: str, index_name: str = "", index_type: str = "INDEX", is_unique: bool = False):
        """
        标记索引列（设置列属性）
        
        Author: CYJ
        Time: 2025-11-20
        """
        query = """
        MATCH (c:Column {name: $column_name, table: $table_name})
        SET c.is_indexed = true, 
            c.index_type = $index_type,
            c.is_unique = $is_unique
        """
        self._execute_query(query, {
            "table_name": table_name,
            "column_name": column_name,
            "index_type": index_type,
            "is_unique": is_unique
        })

    def _execute_query(self, query: str, parameters: Dict[str, Any] = None):
        self.connect()
        with self._driver.session() as session:
            return session.run(query, parameters)

    def get_graph_visualization(self) -> Dict[str, List[Dict]]:
        """
        获取全量图谱数据用于前端可视化
        
        Returns:
            Dict with 'nodes' and 'edges' lists.
        
        Author: Factory Droid
        Time: 2025-11-20
        """
        self.connect()
        query = """
        MATCH (n)-[r]->(m)
        RETURN n, r, m
        LIMIT 1000
        """
        # Also get isolated nodes if any
        nodes = {}
        edges = []

        with self._driver.session() as session:
            result = session.run(query)
            for record in result:
                start_node = record["n"]
                rel = record["r"]
                end_node = record["m"]

                # Process Node N
                n_id = str(start_node.element_id) if hasattr(start_node, 'element_id') else str(start_node.id)
                if n_id not in nodes:
                    nodes[n_id] = {
                        "id": n_id,
                        "label": list(start_node.labels)[0] if start_node.labels else "Unknown",
                        "properties": dict(start_node)
                    }

                # Process Node M
                m_id = str(end_node.element_id) if hasattr(end_node, 'element_id') else str(end_node.id)
                if m_id not in nodes:
                    nodes[m_id] = {
                        "id": m_id,
                        "label": list(end_node.labels)[0] if end_node.labels else "Unknown",
                        "properties": dict(end_node)
                    }

                # Process Relationship
                r_id = str(rel.element_id) if hasattr(rel, 'element_id') else str(rel.id)
                edges.append({
                    "id": r_id,
                    "source": n_id,
                    "target": m_id,
                    "type": rel.type,
                    "properties": dict(rel)
                })

            # Fetch isolated nodes (optional, but good for complete view)
            query_iso = "MATCH (n) WHERE NOT (n)--() RETURN n LIMIT 100"
            result_iso = session.run(query_iso)
            for record in result_iso:
                node = record["n"]
                n_id = str(node.element_id) if hasattr(node, 'element_id') else str(node.id)
                if n_id not in nodes:
                    nodes[n_id] = {
                        "id": n_id,
                        "label": list(node.labels)[0] if node.labels else "Unknown",
                        "properties": dict(node)
                    }

        return {
            "nodes": list(nodes.values()),
            "edges": edges
        }

    def create_generic_relationship(self, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any] = None):
        """
        创建通用关系（基于Node ID）
        """
        self.connect()
        props = properties or {}
        
        # Try to handle both Neo4j 5+ elementId and 4.x id
        # Heuristic: if IDs are purely numeric, they might be legacy IDs, but elementId is string.
        # The API receives strings. We'll try elementId first.
        
        # Construct SET clause dynamically
        set_clause = ", ".join([f"r.{k} = ${k}" for k in props.keys()])
        if set_clause:
            set_clause = "SET " + set_clause
        
        query = f"""
        MATCH (a), (b)
        WHERE (elementId(a) = $source_id OR toString(id(a)) = $source_id) 
          AND (elementId(b) = $target_id OR toString(id(b)) = $target_id)
        MERGE (a)-[r:{rel_type}]->(b)
        {set_clause}
        RETURN r
        """
        
        params = {"source_id": source_id, "target_id": target_id, **props}
        self._execute_query(query, params)

    def delete_relationship_by_id(self, rel_id: str):
        """
        根据ID删除关系
        """
        self.connect()
        query = """
        MATCH ()-[r]-() 
        WHERE elementId(r) = $rel_id OR toString(id(r)) = $rel_id
        DELETE r
        """
        self._execute_query(query, {"rel_id": rel_id})

    def create_generic_node(self, label: str, properties: Dict[str, Any]):
        """
        创建通用节点并返回基础信息，方便前端立即渲染。
        """
        self.connect()
        props = properties or {}
        prop_string = ", ".join([f"{k}: ${k}" for k in props.keys()])
        query = f"CREATE (n:{label} {{{prop_string}}}) RETURN n"

        with self._driver.session() as session:
            result = session.run(query, props)
            record = result.single()
            if not record:
                raise ValueError("Failed to create node")
            node = record["n"]
            node_id = str(node.element_id) if hasattr(node, "element_id") else str(node.id)
            return {
                "id": node_id,
                "label": list(node.labels)[0] if node.labels else label,
                "properties": dict(node)
            }

