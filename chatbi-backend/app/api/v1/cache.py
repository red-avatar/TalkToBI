"""
缓存管理 API

功能：
    提供查询缓存的增删改查接口

路由：
    GET  /api/v1/cache/          - 获取缓存列表
    GET  /api/v1/cache/stats     - 获取缓存统计
    GET  /api/v1/cache/{id}      - 获取缓存详情
    DELETE /api/v1/cache/{id}    - 删除缓存
    PUT  /api/v1/cache/{id}/status - 更新缓存状态

Author: CYJ
"""
from typing import Optional
from fastapi import APIRouter, Query, Path

from app.schemas.response import ApiResponse, ResponseCode, success, error
from app.services.cache_service import get_cache_service

router = APIRouter(prefix="/cache", tags=["缓存管理"])


@router.get("/", response_model=ApiResponse)
async def get_cache_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选: active/invalid/deprecated"),
    keyword: Optional[str] = Query(None, description="关键词搜索")
):
    """
    获取缓存列表
    
    Author: CYJ
    Time: 2025-11-29
    """
    cache_service = get_cache_service()
    result = cache_service.get_cache_list(
        page=page,
        page_size=page_size,
        status=status,
        keyword=keyword
    )
    return success(data=result, message="获取成功")


@router.get("/stats", response_model=ApiResponse)
async def get_cache_stats():
    """
    获取缓存统计信息
    
    Author: CYJ
    Time: 2025-11-29
    """
    cache_service = get_cache_service()
    stats = cache_service.get_cache_stats()
    return success(data=stats, message="获取成功")


@router.get("/{cache_id}", response_model=ApiResponse)
async def get_cache_detail(
    cache_id: int = Path(..., description="缓存ID")
):
    """
    获取缓存详情
    
    Author: CYJ
    Time: 2025-11-29
    """
    cache_service = get_cache_service()
    cache = cache_service.get_cache_by_id(cache_id)
    
    if not cache:
        return error(code=ResponseCode.NOT_FOUND, message="缓存不存在")
    
    return success(data=cache, message="获取成功")


@router.delete("/{cache_id}", response_model=ApiResponse)
async def delete_cache(
    cache_id: int = Path(..., description="缓存ID")
):
    """
    删除缓存
    
    Author: CYJ
    Time: 2025-11-29
    """
    cache_service = get_cache_service()
    
    # 先检查是否存在
    cache = cache_service.get_cache_by_id(cache_id)
    if not cache:
        return error(code=ResponseCode.NOT_FOUND, message="缓存不存在")
    
    deleted = cache_service.delete_cache(cache_id)
    
    if deleted:
        return success(message="删除成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="删除失败")


@router.put("/{cache_id}/status", response_model=ApiResponse)
async def update_cache_status(
    cache_id: int = Path(..., description="缓存ID"),
    status: str = Query(..., description="新状态: active/invalid/deprecated")
):
    """
    更新缓存状态
    
    Author: CYJ
    Time: 2025-11-29
    """
    # 验证状态值
    if status not in ('active', 'invalid', 'deprecated'):
        return error(
            code=ResponseCode.PARAM_ERROR,
            message="无效的状态值，可选: active/invalid/deprecated"
        )
    
    cache_service = get_cache_service()
    
    # 先检查是否存在
    cache = cache_service.get_cache_by_id(cache_id)
    if not cache:
        return error(code=ResponseCode.NOT_FOUND, message="缓存不存在")
    
    updated = cache_service.update_cache_status(cache_id, status)
    
    if updated:
        return success(message="状态更新成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="状态更新失败")
