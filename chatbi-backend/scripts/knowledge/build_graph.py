"""
功能：知识图谱构建脚本（增强版）
说明：读取 full_schema.json (物理元数据) 和 relationships_enhanced.json (完整关系元数据)，
     构建包含表、列节点，以及字段级引用关系、主键标识、索引信息的完整知识图谱
作者：陈怡坚
时间：2025-11-20
修改：增加字段级关系、主键和索引支持
"""
import json
import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.modules.graph.service import GraphService
from app.models.schema import SchemaMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_graph")

def load_metadata(file_path: str) -> SchemaMetadata:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return SchemaMetadata(**data)

def build_knowledge_graph():
    """
    构建完整的知识图谱，包含:
    1. 表和列节点
    2. 字段级引用关系（REFERENCES）
    3. 主键标识（IS_PRIMARY_KEY_OF）
    4. 索引信息（列属性）
    5. 表级 JOIN 关系（JOIN_ON，兼容旧版）
    
    Author: CYJ
    Time: 2025-11-20
    """
    # Update paths to read from scripts/data/
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    schema_path = os.path.join(data_dir, "full_schema.json")
    
    # 优先使用增强版 relationships_enhanced.json
    relationships_enhanced_path = os.path.join(data_dir, "relationships_enhanced.json")
    relationships_path = os.path.join(data_dir, "relationships.json")
    
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}. Run extract_schema.py first.")
        return
    
    # 选择关系文件
    if os.path.exists(relationships_enhanced_path):
        rel_file = relationships_enhanced_path
        logger.info("Using enhanced relationships file (with primary keys & indexes)")
    elif os.path.exists(relationships_path):
        rel_file = relationships_path
        logger.info("Using legacy relationships file (table-level only)")
    else:
        logger.warning("No relationships file found. Building basic graph only.")
        rel_file = None
        
    logger.info("Loading schema and relationships...")
    
    # Load Full Schema (Physical)
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    schema = SchemaMetadata(**schema_data)
    
    # Load Relationships
    rel_data = None
    if rel_file:
        with open(rel_file, 'r', encoding='utf-8') as f:
            rel_data = json.load(f)
    
    graph_service = GraphService()
    
    try:
        logger.info("Connecting to Neo4j...")
        graph_service.connect()
        
        logger.info("Clearing existing graph...")
        graph_service.clear_graph()
        
        # ===== 步骤1: 创建表和列节点 =====
        logger.info(f"Step 1: Creating {len(schema.tables)} tables and columns...")
        for table in schema.tables:
            # 1.1 Create Table Node
            graph_service.create_table_node(table.name, table.comment or "")
            
            # 1.2 Create Column Nodes
            for col in table.columns:
                graph_service.create_column_node(
                    table.name, 
                    col.name, 
                    col.data_type, 
                    col.comment or ""
                )
        
        # ===== 步骤2: 标记主键 =====
        if rel_data and "tables" in rel_data:
            logger.info(f"Step 2: Marking primary keys...")
            pk_count = 0
            for table_info in rel_data["tables"]:
                for pk_col in table_info.get("primary_keys", []):
                    try:
                        graph_service.mark_primary_key(table_info["table_name"], pk_col)
                        pk_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to mark PK {table_info['table_name']}.{pk_col}: {e}")
            logger.info(f"  ✓ Marked {pk_count} primary key columns")
        
        # ===== 步骤3: 标记索引列 =====
        if rel_data and "tables" in rel_data:
            logger.info(f"Step 3: Marking indexed columns...")
            idx_count = 0
            for table_info in rel_data["tables"]:
                for idx in table_info.get("indexes", []):
                    # 跳过主键索引（已在步骤2处理）
                    if idx.get("type") == "PRIMARY":
                        continue
                    for col_name in idx.get("columns", []):
                        try:
                            graph_service.mark_indexed_column(
                                table_info["table_name"], 
                                col_name,
                                idx.get("name", ""),
                                idx.get("type", "INDEX"),
                                idx.get("is_unique", False)
                            )
                            idx_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to mark index on {table_info['table_name']}.{col_name}: {e}")
            logger.info(f"  ✓ Marked {idx_count} indexed columns")
        
        # ===== 步骤4: 创建字段级引用关系（核心） =====
        if rel_data and "column_references" in rel_data:
            logger.info(f"Step 4: Creating {len(rel_data['column_references'])} column-level references...")
            ref_count = 0
            for ref in rel_data["column_references"]:
                try:
                    graph_service.create_column_reference(
                        ref["source_table"],
                        ref["source_column"],
                        ref["target_table"],
                        ref["target_column"],
                        ref.get("reference_type", "FOREIGN_KEY"),
                        ref.get("cardinality", "N:1"),
                        ref.get("confidence", 1.0),
                        ref.get("description", "")
                    )
                    ref_count += 1
                except Exception as e:
                    logger.warning(f"Failed to create column reference: {ref} - {e}")
            logger.info(f"  ✓ Created {ref_count} REFERENCES relationships")
        
        # ===== 步骤5: 创建表级 JOIN 关系（兼容旧版，可选） =====
        if isinstance(rel_data, list):
            # 处理新版纯列表格式的 relationships_enhanced.json
            logger.info(f"Step 5: Creating {len(rel_data)} table-level JOIN relationships (new format)...")
            join_count = 0
            for rel in rel_data:
                try:
                    # 提取 properties 里的信息
                    props = rel.get("properties", {})
                    condition = props.get("condition", "")
                    confidence = props.get("confidence", 1.0)
                    
                    # 如果 properties 里有 condition，尝试解析出 source_column 和 target_column
                    # 假设 condition 格式为 "tableA.colA = tableB.colB"
                    source_col = ""
                    target_col = ""
                    if condition and "=" in condition:
                        parts = condition.split("=")
                        left_part = parts[0].strip()
                        right_part = parts[1].strip()
                        
                        # 简单解析：假设是 "sourceTable.col" 格式
                        if "." in left_part:
                            source_col = left_part.split(".")[1]
                        if "." in right_part:
                            target_col = right_part.split(".")[1]

                    graph_service.create_join_relationship(
                        rel["source"],
                        source_col,  # 如果解析失败则传空，GraphService 需要处理
                        rel["target"],
                        target_col,
                        relationship_type=rel.get("type", "JOIN_ON"),
                        properties=props
                    )
                    join_count += 1
                except Exception as e:
                    logger.warning(f"Failed to create JOIN: {rel} - {e}")
            logger.info(f"  ✓ Created {join_count} JOIN_ON relationships")

        # Try to extract other metadata (PKs, Indexes, References) from the list format if possible
        # Since the current JSON is a flat list of relationships, we might not have this info directly.
        # However, we can infer column references from the JOIN conditions if needed.
        if isinstance(rel_data, list):
             logger.info(f"Step 6: Inferring column references from JOIN conditions (new format)...")
             ref_count = 0
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
                            
                            # Create explicit column reference
                            graph_service.create_column_reference(
                                source_table,
                                source_col,
                                target_table,
                                target_col,
                                reference_type=props.get("join_type", "FOREIGN_KEY"),
                                description=props.get("description", "")
                            )
                            ref_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to infer reference from {condition}: {e}")
             logger.info(f"  ✓ Inferred {ref_count} REFERENCES relationships")

        elif rel_data and "relationships" in rel_data:
            # 旧版 JSON 格式兼容 (dict with "relationships" key)
            logger.info(f"Step 5: Creating table-level JOIN relationships (legacy)...")
            join_count = 0
            for rel in rel_data["relationships"]:
                try:
                    graph_service.create_join_relationship(
                        rel["source_table"],
                        rel["source_column"],
                        rel["target_table"],
                        rel["target_column"]
                    )
                    join_count += 1
                except Exception as e:
                    logger.warning(f"Failed to create JOIN: {rel} - {e}")
            logger.info(f"  ✓ Created {join_count} JOIN_ON relationships")
        elif rel_data and "column_references" in rel_data:
            # 从字段级关系生成表级 JOIN（新版）
            logger.info(f"Step 5: Deriving table-level JOIN paths from column references...")
            join_count = 0
            for ref in rel_data["column_references"]:
                try:
                    graph_service.create_join_relationship(
                        ref["source_table"],
                        ref["source_column"],
                        ref["target_table"],
                        ref["target_column"]
                    )
                    join_count += 1
                except Exception as e:
                    pass  # 静默失败，因为可能重复
            logger.info(f"  ✓ Created {join_count} derived JOIN_ON relationships")

        logger.info("=" * 60)
        logger.info("✓ Knowledge Graph built successfully!")
        logger.info(f"   - Tables: {len(schema.tables)}")
        logger.info(f"   - Columns: {sum(len(t.columns) for t in schema.tables)}")
        logger.info(f"   - Primary Keys: {pk_count if 'pk_count' in locals() else 'N/A'}")
        logger.info(f"   - Indexed Columns: {idx_count if 'idx_count' in locals() else 'N/A'}")
        logger.info(f"   - Column References: {ref_count if 'ref_count' in locals() else 'N/A'}")
        logger.info(f"   - Table JOINs: {join_count if 'join_count' in locals() else 'N/A'}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error building graph: {e}")
        import traceback
        traceback.print_exc()
    finally:
        graph_service.close()

if __name__ == "__main__":
    build_knowledge_graph()
