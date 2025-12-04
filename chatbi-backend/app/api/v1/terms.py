"""
专业名词管理 API

功能：
    提供专业名词的增删改查接口（操作本地 JSON 文件）

路由：
    GET  /api/v1/terms/          - 获取名词列表
    POST /api/v1/terms/          - 添加名词
    GET  /api/v1/terms/{name}    - 获取名词详情
    PUT  /api/v1/terms/{name}    - 更新名词
    DELETE /api/v1/terms/{name}  - 删除名词
    POST /api/v1/terms/reload    - 重新加载配置

Author: CYJ
"""
from typing import Optional, List
from fastapi import APIRouter, Path, Body
from pydantic import BaseModel, Field

from app.schemas.response import ApiResponse, ResponseCode, success, error
from app.services.term_service import get_term_service

router = APIRouter(prefix="/terms", tags=["专业名词管理"])


class TermCreateRequest(BaseModel):
    """创建名词请求"""
    name: str = Field(..., description="名词名称")
    meaning: str = Field(..., description="含义解释")
    sql_hint: Optional[str] = Field(None, description="SQL提示")
    examples: Optional[List[str]] = Field(None, description="示例列表")


class TermUpdateRequest(BaseModel):
    """更新名词请求"""
    meaning: Optional[str] = Field(None, description="含义解释")
    sql_hint: Optional[str] = Field(None, description="SQL提示")
    examples: Optional[List[str]] = Field(None, description="示例列表")


@router.get("/", response_model=ApiResponse)
async def get_terms_list():
    """
    获取专业名词列表
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    terms = term_service.get_terms_list()
    return success(
        data={
            "items": terms,
            "total": len(terms)
        },
        message="获取成功"
    )


@router.post("/", response_model=ApiResponse)
async def add_term(request: TermCreateRequest):
    """
    添加专业名词
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    
    # 检查是否已存在
    if term_service.get_term(request.name):
        return error(
            code=ResponseCode.OPERATION_FAILED,
            message=f"名词 '{request.name}' 已存在"
        )
    
    added = term_service.add_term(
        name=request.name,
        meaning=request.meaning,
        sql_hint=request.sql_hint,
        examples=request.examples
    )
    
    if added:
        return success(message="添加成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="添加失败")


@router.get("/{name}", response_model=ApiResponse)
async def get_term_detail(
    name: str = Path(..., description="名词名称")
):
    """
    获取名词详情
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    term = term_service.get_term(name)
    
    if not term:
        return error(code=ResponseCode.NOT_FOUND, message="名词不存在")
    
    return success(
        data={
            "name": name,
            "meaning": term.get("meaning", ""),
            "sql_hint": term.get("sql_hint", ""),
            "examples": term.get("examples", [])
        },
        message="获取成功"
    )


@router.put("/{name}", response_model=ApiResponse)
async def update_term(
    name: str = Path(..., description="名词名称"),
    request: TermUpdateRequest = Body(...)
):
    """
    更新专业名词
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    
    # 检查是否存在
    if not term_service.get_term(name):
        return error(code=ResponseCode.NOT_FOUND, message="名词不存在")
    
    updated = term_service.update_term(
        name=name,
        meaning=request.meaning,
        sql_hint=request.sql_hint,
        examples=request.examples
    )
    
    if updated:
        return success(message="更新成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="更新失败")


@router.delete("/{name}", response_model=ApiResponse)
async def delete_term(
    name: str = Path(..., description="名词名称")
):
    """
    删除专业名词
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    
    # 检查是否存在
    if not term_service.get_term(name):
        return error(code=ResponseCode.NOT_FOUND, message="名词不存在")
    
    deleted = term_service.delete_term(name)
    
    if deleted:
        return success(message="删除成功")
    else:
        return error(code=ResponseCode.OPERATION_FAILED, message="删除失败")


@router.post("/reload", response_model=ApiResponse)
async def reload_terms():
    """
    重新加载配置文件
    
    Author: CYJ
    Time: 2025-11-29
    """
    term_service = get_term_service()
    term_service.reload()
    
    return success(
        data={"count": term_service.count},
        message=f"重新加载成功，共 {term_service.count} 个名词"
    )
