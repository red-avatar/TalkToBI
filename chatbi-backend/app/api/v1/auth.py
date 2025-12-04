"""
认证 API 路由

提供用户登录、登出、密码管理、用户管理等接口

Author: CYJ
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query

from app.schemas.auth import (
    LoginRequest,
    ChangePasswordRequest,
    CreateUserRequest,
    LoginResponse,
    UserInfo,
    UserListItem,
    LoginLogItem,
)
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证管理"])

def get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    # 尝试从代理头获取
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    # 直连IP
    return request.client.host if request.client else "unknown"

@router.post("/login", summary="用户登录")
async def login(req: LoginRequest, request: Request):
    """
    用户登录
    
    - username: 用户名
    - password: 密码
    """
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    
    success, user, message = await auth_service.authenticate_user(
        req.username, req.password
    )
    
    # 记录登录日志
    await auth_service.record_login_log(
        user_id=user["id"] if user else None,
        username=req.username,
        ip_address=ip_address,
        location="",  # 可以后续接入IP定位服务
        user_agent=user_agent,
        status=1 if success else 0,
        message="" if success else message
    )
    
    if not success:
        return {"code": 1, "message": message, "data": None}
    
    return {
        "code": 0,
        "message": "登录成功",
        "data": {
            "user": user,
            "token": ""  # 简单实现，前端 localStorage 存储用户信息
        }
    }

@router.post("/logout", summary="用户登出")
async def logout():
    """用户登出"""
    return {"code": 0, "message": "登出成功", "data": None}

@router.put("/password", summary="修改密码")
async def change_password(
    req: ChangePasswordRequest,
    user_id: int = Query(..., description="当前用户ID")
):
    """
    修改密码
    
    - old_password: 旧密码
    - new_password: 新密码
    - user_id: 当前登录用户的ID
    """
    success, message = await auth_service.change_password(
        user_id, req.old_password, req.new_password
    )
    
    if not success:
        return {"code": 1, "message": message, "data": None}
    
    return {"code": 0, "message": "密码修改成功", "data": None}

@router.get("/users", summary="获取用户列表")
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_root: bool = Query(False, description="当前用户是否为root")
):
    """
    获取用户列表（仅 root 可用）
    """
    if not is_root:
        return {"code": 403, "message": "无权限访问", "data": None}
    
    users, total = await auth_service.get_user_list(page, page_size)
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": users,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }

@router.post("/users", summary="创建用户")
async def create_user(
    req: CreateUserRequest,
    is_root: bool = Query(False, description="当前用户是否为root")
):
    """
    创建用户（仅 root 可用）
    
    - username: 用户名
    - password: 初始密码（默认 123456）
    - nickname: 昵称
    """
    if not is_root:
        return {"code": 403, "message": "无权限操作", "data": None}
    
    success, message, user_id = await auth_service.create_user(
        req.username, req.password, req.nickname
    )
    
    if not success:
        return {"code": 1, "message": message, "data": None}
    
    return {
        "code": 0,
        "message": "用户创建成功",
        "data": {"id": user_id}
    }

@router.put("/users/{user_id}/reset-password", summary="重置用户密码")
async def reset_password(
    user_id: int,
    is_root: bool = Query(False, description="当前用户是否为root")
):
    """
    重置用户密码为默认 123456（仅 root 可用）
    """
    if not is_root:
        return {"code": 403, "message": "无权限操作", "data": None}
    
    success, message = await auth_service.reset_password(user_id)
    
    if not success:
        return {"code": 1, "message": message, "data": None}
    
    return {"code": 0, "message": "密码已重置为 123456", "data": None}

@router.get("/logs", summary="获取登录日志")
async def get_login_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    is_root: bool = Query(False, description="当前用户是否为root")
):
    """
    获取登录日志（仅 root 可用）
    """
    if not is_root:
        return {"code": 403, "message": "无权限访问", "data": None}
    
    logs, total = await auth_service.get_login_logs(page, page_size)
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": logs,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    }

@router.get("/me", summary="获取当前用户信息")
async def get_current_user(user_id: int = Query(..., description="当前用户ID")):
    """
    获取当前登录用户信息
    """
    user = await auth_service.get_user_by_id(user_id)
    
    if not user:
        return {"code": 1, "message": "用户不存在", "data": None}
    
    return {"code": 0, "message": "success", "data": user}
