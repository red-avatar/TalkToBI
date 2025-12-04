"""
统一响应模型

定义全局API响应格式、状态码枚举、工厂函数

Author: CYJ
Time: 2025-11-29
"""
from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel, Field
from enum import IntEnum


# =============================================================================
# 状态码枚举
# =============================================================================

class ResponseCode(IntEnum):
    """
    API响应状态码
    
    状态码规范:
    - 0: 成功
    - 1xxx: 客户端错误（参数、资源等）
    - 2xxx: 数据库错误
    - 5xxx: 服务端内部错误
    
    Author: CYJ
    Time: 2025-11-29
    """
    SUCCESS = 0
    
    # 1xxx - 客户端错误
    PARAM_ERROR = 1001          # 参数错误
    RESOURCE_NOT_FOUND = 1002   # 资源不存在
    OPERATION_FAILED = 1003     # 操作失败
    VALIDATION_ERROR = 1004     # 验证错误
    
    # 2xxx - 数据库错误
    DB_ERROR = 2001             # 数据库错误
    DB_CONNECTION_ERROR = 2002  # 数据库连接错误
    
    # 5xxx - 服务端错误
    INTERNAL_ERROR = 5000       # 系统内部错误
    SERVICE_UNAVAILABLE = 5001  # 服务不可用


# =============================================================================
# 响应模型
# =============================================================================

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """
    统一API响应模型
    
    所有API接口统一使用此格式返回:
    - code: 状态码，0表示成功
    - message: 状态描述
    - data: 响应数据（可为null）
    
    Example:
        成功: {"code": 0, "message": "success", "data": {...}}
        失败: {"code": 1001, "message": "参数错误", "data": null}
    
    Author: CYJ
    Time: 2025-11-29
    """
    code: int = Field(default=0, description="状态码，0表示成功")
    message: str = Field(default="success", description="状态描述")
    data: Optional[T] = Field(default=None, description="响应数据")


class PaginatedData(BaseModel, Generic[T]):
    """
    分页数据模型
    
    用于列表接口的分页返回
    
    Author: CYJ
    Time: 2025-11-29
    """
    items: List[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页大小")
    total_pages: int = Field(default=0, description="总页数")


# =============================================================================
# 工厂函数
# =============================================================================

def success(data: Any = None, message: str = "success") -> dict:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        message: 成功描述
        
    Returns:
        响应字典
        
    Author: CYJ
    Time: 2025-11-29
    """
    return {
        "code": ResponseCode.SUCCESS,
        "message": message,
        "data": data
    }


def error(
    code: ResponseCode = ResponseCode.INTERNAL_ERROR,
    message: str = "操作失败",
    data: Any = None
) -> dict:
    """
    创建错误响应
    
    Args:
        code: 错误状态码
        message: 错误描述
        data: 附加数据（可选）
        
    Returns:
        响应字典
        
    Author: CYJ
    Time: 2025-11-29
    """
    return {
        "code": code,
        "message": message,
        "data": data
    }


def paginated(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    创建分页成功响应
    
    Args:
        items: 数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        
    Returns:
        包含分页信息的响应字典
        
    Author: CYJ
    Time: 2025-11-29
    """
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return success(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    })


# =============================================================================
# 便捷错误函数
# =============================================================================

def param_error(message: str = "参数错误") -> dict:
    """参数错误响应"""
    return error(ResponseCode.PARAM_ERROR, message)


def not_found(message: str = "资源不存在") -> dict:
    """资源不存在响应"""
    return error(ResponseCode.RESOURCE_NOT_FOUND, message)


def operation_failed(message: str = "操作失败") -> dict:
    """操作失败响应"""
    return error(ResponseCode.OPERATION_FAILED, message)


def db_error(message: str = "数据库错误") -> dict:
    """数据库错误响应"""
    return error(ResponseCode.DB_ERROR, message)


def internal_error(message: str = "系统内部错误") -> dict:
    """系统内部错误响应"""
    return error(ResponseCode.INTERNAL_ERROR, message)
