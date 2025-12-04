"""
知识图谱构建 API

提供知识图谱的构建、编辑、同步等功能

Author: CYJ
Time: 2025-12-03
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.modules.graph.service import GraphService
from app.modules.schema.loader import SchemaLoader
from app.modules.graph.schemas import (
    GraphVisualizationData, 
    CreateRelationshipRequest, 
    DeleteRelationshipRequest,
    CreateNodeRequest,
    GraphNode,
    GraphEdge
)
from app.models.schema import TableSchema
from app.services.graph_builder_service import get_graph_builder_service
from app.schemas.response import success, error, ResponseCode

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


# ========== Pydantic 请求模型 ==========

class SaveRelationshipsRequest(BaseModel):
    """保存关系请求"""
    relationships: List[Dict[str, Any]]

def get_graph_service():
    service = GraphService()
    try:
        yield service
    finally:
        service.close()

def get_schema_loader():
    return SchemaLoader()

@router.get("/metadata")
async def get_metadata(loader: SchemaLoader = Depends(get_schema_loader)):
    """
    获取 MySQL 中的全量表结构（供前端左侧面板备选）
    
    注意：这个接口会实时连接数据库，较慢。
    建议优先使用 /graph/schema 获取缓存的 Schema。
    
    Author: CYJ
    Time: 2025-12-03
    """
    try:
        tables = loader.extract_full_schema()
        # 返回数组结构，与前端期望一致
        return success(data=[t.model_dump() for t in tables], message="获取成功")
    except Exception as e:
        return error(code=ResponseCode.OPERATION_FAILED, message=f"获取元数据失败: {str(e)}")

@router.get("/visualization", response_model=GraphVisualizationData)
def get_visualization(service: GraphService = Depends(get_graph_service)):
    """
    获取 Neo4j 当前的节点和边（供前端画布初始化渲染）
    """
    try:
        data = service.get_graph_visualization()
        return GraphVisualizationData(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch graph data: {str(e)}")

@router.post("/relationship", status_code=status.HTTP_201_CREATED)
def create_relationship(
    request: CreateRelationshipRequest, 
    service: GraphService = Depends(get_graph_service)
):
    """
    创建/更新两节点之间的关系
    """
    try:
        service.create_generic_relationship(
            source_id=request.source_node_id,
            target_id=request.target_node_id,
            rel_type=request.relationship_type,
            properties=request.properties
        )
        return {"message": "Relationship created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create relationship: {str(e)}")

@router.delete("/relationship/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: str, 
    service: GraphService = Depends(get_graph_service)
):
    """
    删除关系
    """
    try:
        service.delete_relationship_by_id(relationship_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete relationship: {str(e)}")

@router.post("/node", status_code=status.HTTP_201_CREATED)
def create_node(
    request: CreateNodeRequest,
    service: GraphService = Depends(get_graph_service)
):
    """
    手动添加节点
    """
    try:
        node = service.create_generic_node(
            label=request.label,
            properties=request.properties
        )
        return {"message": "Node created successfully", "node": node}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create node: {str(e)}")


# ========== 新增接口：支持前端图谱编辑器 ==========

@router.get("/schema")
async def get_saved_schema():
    """
    获取已保存的 Schema 数据
    
    优先从本地 full_schema.json 读取（快速），
    如果不存在则返回空数据。
    
    Author: CYJ
    Time: 2025-12-03
    """
    service = get_graph_builder_service()
    schema_data = service.get_schema()
    
    if schema_data:
        return success(data=schema_data, message="获取成功")
    else:
        return success(data={"tables": []}, message="Schema文件不存在，请先提取元数据")


@router.get("/relationships/local")
async def get_local_relationships():
    """
    获取本地 JSON 关系数据
    
    读取 relationships_enhanced.json
    
    Author: CYJ
    Time: 2025-12-03
    """
    service = get_graph_builder_service()
    relationships = service.get_local_relationships()
    return success(data=relationships, message="获取成功")


@router.post("/relationships/local")
async def save_local_relationships(request: SaveRelationshipsRequest):
    """
    保存关系数据到本地 JSON
    
    保存到 relationships_enhanced.json
    
    Author: CYJ
    Time: 2025-12-03
    """
    service = get_graph_builder_service()
    result = service.save_local_relationships(request.relationships)
    
    if result:
        return success(data={"saved_count": len(request.relationships)}, message="保存成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="保存失败")


@router.post("/sync-to-neo4j")
async def sync_to_neo4j():
    """
    将本地 JSON 同步到 Neo4j
    
    读取 full_schema.json 和 relationships_enhanced.json，
    写入 Neo4j 图数据库。
    
    Author: CYJ
    Time: 2025-12-03
    """
    service = get_graph_builder_service()
    result = service.sync_to_neo4j()
    
    if result.success:
        return success(
            data={
                "success": True,
                "tables_count": result.tables_count,
                "columns_count": result.columns_count,
                "relations_count": result.relations_count,
            },
            message=result.message
        )
    else:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=result.message,
            data={"success": False}
        )


@router.post("/infer")
async def infer_relationships():
    """
    LLM 推断生成表关系
    
    读取 full_schema.json，使用 LLM 推断表之间的关系。
    
    Author: CYJ
    Time: 2025-12-03
    """
    try:
        # 检查是否有 RelationshipInferenceAgent
        try:
            from app.modules.agents.relationship_inference.agent import RelationshipInferenceAgent
            agent = RelationshipInferenceAgent()
            relationships = agent.generate_relationships()
            return success(
                data={
                    "success": True,
                    "relationships": relationships,
                    "count": len(relationships)
                },
                message=f"推断完成，生成了 {len(relationships)} 条关系"
            )
        except ImportError:
            # Agent 未实现，返回提示
            return error(
                code=ResponseCode.OPERATION_FAILED,
                message="LLM推断功能尚未实现，请手动添加关系",
                data={"success": False}
            )
    except Exception as e:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=f"推断失败: {str(e)}",
            data={"success": False}
        )


@router.post("/extract-schema")
async def extract_schema():
    """
    触发 Schema 提取
    
    从 MySQL 提取元数据，保存到 full_schema.json
    
    Author: CYJ
    Time: 2025-12-03
    """
    try:
        service = get_graph_builder_service()
        schema_data = service.extract_schema()
        return success(
            data={
                "success": True,
                "tables_count": len(schema_data.get("tables", [])),
                "database_name": schema_data.get("database_name", "")
            },
            message="Schema提取成功"
        )
    except Exception as e:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=f"Schema提取失败: {str(e)}"
        )
