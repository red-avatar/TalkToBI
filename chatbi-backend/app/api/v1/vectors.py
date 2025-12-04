"""
向量管理 API

功能：
    提供向量数据的查看和构建触发接口

路由：
    GET  /api/v1/vectors/           - 获取向量列表
    GET  /api/v1/vectors/stats      - 获取向量统计
    GET  /api/v1/vectors/status     - 获取构建状态
    GET  /api/v1/vectors/{id}       - 获取向量详情
    POST /api/v1/vectors/extract    - 触发元数据提取
    POST /api/v1/vectors/enhance    - 触发语义增强
    POST /api/v1/vectors/build      - 触发向量构建

Author: CYJ
"""
from typing import Optional
from fastapi import APIRouter, Query, Path

from app.schemas.response import ApiResponse, ResponseCode, success, error
from app.services.vector_service import get_vector_service

router = APIRouter(prefix="/vectors", tags=["向量管理"])


@router.get("/", response_model=ApiResponse)
async def get_vectors_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    object_type: Optional[str] = Query(None, description="类型筛选: table/column"),
    keyword: Optional[str] = Query(None, description="关键词搜索")
):
    """
    获取向量列表
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    result = vector_service.get_vectors(
        page=page,
        page_size=page_size,
        object_type=object_type,
        keyword=keyword
    )
    return success(data=result, message="获取成功")


@router.get("/stats", response_model=ApiResponse)
async def get_vectors_stats():
    """
    获取向量统计信息
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    stats = vector_service.get_stats()
    return success(data=stats, message="获取成功")


@router.get("/status", response_model=ApiResponse)
async def get_build_status():
    """
    获取构建状态
    
    返回各阶段数据文件状态和数据库向量数量
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    status = vector_service.get_build_status()
    return success(data=status, message="获取成功")


@router.get("/{vector_id}", response_model=ApiResponse)
async def get_vector_detail(
    vector_id: int = Path(..., description="向量ID")
):
    """
    获取向量详情
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    vector = vector_service.get_vector_by_id(vector_id)
    
    if not vector:
        return error(code=ResponseCode.NOT_FOUND, message="向量不存在")
    
    return success(data=vector, message="获取成功")


@router.post("/extract", response_model=ApiResponse)
async def trigger_extract():
    """
    触发元数据提取
    
    从业务数据库提取表结构信息，生成 full_schema.json
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    result = vector_service.trigger_extract()
    
    if result["success"]:
        return success(data=result, message="元数据提取成功")
    else:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=result["message"],
            data={"output": result["output"]}
        )


@router.post("/enhance", response_model=ApiResponse)
async def trigger_enhance():
    """
    触发语义增强
    
    调用 LLM 对 Schema 进行语义扩写，生成 enriched_schema.json
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    result = vector_service.trigger_enhance()
    
    if result["success"]:
        return success(data=result, message="语义增强成功")
    else:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=result["message"],
            data={"output": result["output"]}
        )


@router.post("/build", response_model=ApiResponse)
async def trigger_build():
    """
    触发向量构建
    
    将增强后的描述转换为向量，写入 PostgreSQL
    
    Author: CYJ
    """
    vector_service = get_vector_service()
    result = vector_service.trigger_build()
    
    if result["success"]:
        return success(data=result, message="向量构建成功")
    else:
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=result["message"],
            data={"output": result["output"]}
        )
