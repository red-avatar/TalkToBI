"""
认证相关数据模型

Author: CYJ
Time: 2025-12-03
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# =============================================================================
# 请求模型
# =============================================================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=100, description="密码")

class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")

class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(default="123456", min_length=6, max_length=100, description="初始密码")
    nickname: str = Field(default="", max_length=100, description="昵称")

# =============================================================================
# 响应模型
# =============================================================================

class UserInfo(BaseModel):
    """用户信息"""
    id: int
    username: str
    nickname: str
    is_root: bool
    status: int
    created_at: datetime
    updated_at: datetime

class LoginResponse(BaseModel):
    """登录响应"""
    user: UserInfo
    token: str = ""  # 简单实现，暂不使用JWT

class UserListItem(BaseModel):
    """用户列表项"""
    id: int
    username: str
    nickname: str
    is_root: bool
    status: int
    created_at: datetime
    updated_at: datetime

class LoginLogItem(BaseModel):
    """登录日志项"""
    id: int
    user_id: Optional[int]
    username: str
    ip_address: str
    location: str
    user_agent: str
    login_time: datetime
    status: int
    message: str
