"""
执行记录 API

功能：
    提供查询执行历史的查看接口

路由：
    GET  /api/v1/logs/           - 获取执行记录列表
    GET  /api/v1/logs/stats      - 获取执行统计
    GET  /api/v1/logs/{id}       - 获取记录详情

Author: CYJ
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Query, Path

from app.schemas.response import ApiResponse, ResponseCode, success, error
from app.services.execution_log_service import get_execution_log_service

router = APIRouter(prefix="/logs", tags=["执行记录"])


@router.get("/", response_model=ApiResponse)
async def get_logs_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    status: Optional[str] = Query(None, description="状态筛选: success/error/timeout/pending"),
    session_id: Optional[str] = Query(None, description="会话ID筛选"),
    user_id: Optional[str] = Query(None, description="用户ID筛选"),
    start_date: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_date: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """
    获取执行记录列表
    
    Author: CYJ
    Time: 2025-11-29
    """
    log_service = get_execution_log_service()
    
    # 解析日期
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            return error(code=ResponseCode.PARAM_ERROR, message="无效的开始时间格式")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            return error(code=ResponseCode.PARAM_ERROR, message="无效的结束时间格式")
    
    result = log_service.get_logs(
        page=page,
        page_size=page_size,
        status=status,
        session_id=session_id,
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt
    )
    return success(data=result, message="获取成功")


@router.get("/stats", response_model=ApiResponse)
async def get_logs_stats(
    start_date: Optional[str] = Query(None, description="开始时间 (ISO格式)"),
    end_date: Optional[str] = Query(None, description="结束时间 (ISO格式)")
):
    """
    获取执行统计信息
    
    返回：总数、成功数、失败数、成功率、缓存命中率、平均耗时等
    
    Author: CYJ
    Time: 2025-11-29
    """
    log_service = get_execution_log_service()
    
    # 解析日期
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except ValueError:
            return error(code=ResponseCode.PARAM_ERROR, message="无效的开始时间格式")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            return error(code=ResponseCode.PARAM_ERROR, message="无效的结束时间格式")
    
    stats = log_service.get_stats(start_date=start_dt, end_date=end_dt)
    return success(data=stats, message="获取成功")


@router.get("/{log_id}", response_model=ApiResponse)
async def get_log_detail(
    log_id: int = Path(..., description="记录ID")
):
    """
    获取执行记录详情
    
    Author: CYJ
    Time: 2025-11-29
    """
    log_service = get_execution_log_service()
    log = log_service.get_log_by_id(log_id)
    
    if not log:
        return error(code=ResponseCode.NOT_FOUND, message="记录不存在")
    
    return success(data=log, message="获取成功")
