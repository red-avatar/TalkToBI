"""
认证服务

提供用户认证、密码管理、登录日志等功能

Author: CYJ
Time: 2025-12-03
"""
import hashlib
import logging
from typing import Optional, List, Tuple
from datetime import datetime

from sqlalchemy import text
from app.core.database import get_sys_db_engine

logger = logging.getLogger(__name__)

# 默认密码
DEFAULT_PASSWORD = "123456"

def hash_password(password: str) -> str:
    """
    密码哈希（SHA256）
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码
    
    Args:
        password: 明文密码
        password_hash: 存储的哈希值
        
    Returns:
        密码是否正确
    """
    return hash_password(password) == password_hash

async def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[dict], str]:
    """
    验证用户登录
    
    Args:
        username: 用户名
        password: 密码
        
    Returns:
        (是否成功, 用户信息, 错误消息)
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, username, password_hash, nickname, is_root, status, created_at, updated_at FROM sys_users WHERE username = :username"),
                {"username": username}
            )
            row = result.fetchone()
            
            if not row:
                return False, None, "用户不存在"
            
            user = dict(row._mapping)
            
            if user["status"] != 1:
                return False, None, "用户已被禁用"
            
            if not verify_password(password, user["password_hash"]):
                return False, None, "密码错误"
            
            # 移除敏感信息
            del user["password_hash"]
            user["is_root"] = bool(user["is_root"])
            
            return True, user, ""
            
    except Exception as e:
        logger.error(f"[AuthService] 用户验证失败: {e}")
        return False, None, f"系统错误: {str(e)}"

async def record_login_log(
    user_id: Optional[int],
    username: str,
    ip_address: str,
    location: str,
    user_agent: str,
    status: int,
    message: str = ""
):
    """
    记录登录日志
    
    Args:
        user_id: 用户ID（登录失败时可为 None）
        username: 用户名
        ip_address: IP地址
        location: 登录地点
        user_agent: 浏览器UA
        status: 登录状态：0-失败 1-成功
        message: 备注信息
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO sys_login_logs (user_id, username, ip_address, location, user_agent, status, message)
                    VALUES (:user_id, :username, :ip_address, :location, :user_agent, :status, :message)
                """),
                {
                    "user_id": user_id,
                    "username": username,
                    "ip_address": ip_address,
                    "location": location,
                    "user_agent": user_agent[:500] if user_agent else "",
                    "status": status,
                    "message": message
                }
            )
            conn.commit()
    except Exception as e:
        logger.error(f"[AuthService] 记录登录日志失败: {e}")

async def change_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    """
    修改密码
    
    Args:
        user_id: 用户ID
        old_password: 旧密码
        new_password: 新密码
        
    Returns:
        (是否成功, 错误消息)
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            # 验证旧密码
            result = conn.execute(
                text("SELECT password_hash FROM sys_users WHERE id = :id"),
                {"id": user_id}
            )
            row = result.fetchone()
            
            
            if not verify_password(old_password, row[0]):
                return False, "旧密码错误"
            
            # 更新密码
            conn.execute(
                text("UPDATE sys_users SET password_hash = :hash WHERE id = :id"),
                {"hash": hash_password(new_password), "id": user_id}
            )
            conn.commit()
            
            return True, ""
            
    except Exception as e:
        logger.error(f"[AuthService] 修改密码失败: {e}")
        return False, f"系统错误: {str(e)}"

async def reset_password(user_id: int) -> Tuple[bool, str]:
    """
    重置密码为默认密码
    
    Args:
        user_id: 用户ID
        
    Returns:
        (是否成功, 错误消息)
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("UPDATE sys_users SET password_hash = :hash WHERE id = :id"),
                {"hash": hash_password(DEFAULT_PASSWORD), "id": user_id}
            )
            conn.commit()
            
            if result.rowcount == 0:
                return False, "用户不存在"
            
            return True, ""
            
    except Exception as e:
        logger.error(f"[AuthService] 重置密码失败: {e}")
        return False, f"系统错误: {str(e)}"

async def create_user(username: str, password: str, nickname: str) -> Tuple[bool, str, Optional[int]]:
    """
    创建用户
    
    Args:
        username: 用户名
        password: 密码
        nickname: 昵称
        
    Returns:
        (是否成功, 错误消息, 新用户ID)
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            # 检查用户名是否已存在
            result = conn.execute(
                text("SELECT id FROM sys_users WHERE username = :username"),
                {"username": username}
            )
            if result.fetchone():
                return False, "用户名已存在", None
            
            # 创建用户
            result = conn.execute(
                text("""
                    INSERT INTO sys_users (username, password_hash, nickname, is_root, status)
                    VALUES (:username, :password_hash, :nickname, 0, 1)
                """),
                {
                    "username": username,
                    "password_hash": hash_password(password),
                    "nickname": nickname or username
                }
            )
            conn.commit()
            
            return True, "", result.lastrowid
            
    except Exception as e:
        logger.error(f"[AuthService] 创建用户失败: {e}")
        return False, f"系统错误: {str(e)}", None

async def get_user_list(page: int = 1, page_size: int = 20) -> Tuple[List[dict], int]:
    """
    获取用户列表
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        (用户列表, 总数)
    """
    engine = get_sys_db_engine()
    offset = (page - 1) * page_size
    
    try:
        with engine.connect() as conn:
            # 获取总数
            count_result = conn.execute(text("SELECT COUNT(*) FROM sys_users"))
            total = count_result.scalar()
            
            # 获取列表
            result = conn.execute(
                text("""
                    SELECT id, username, nickname, is_root, status, created_at, updated_at
                    FROM sys_users
                    ORDER BY id ASC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": page_size, "offset": offset}
            )
            
            users = []
            for row in result:
                user = dict(row._mapping)
                user["is_root"] = bool(user["is_root"])
                users.append(user)
            
            return users, total
            
    except Exception as e:
        logger.error(f"[AuthService] 获取用户列表失败: {e}")
        return [], 0

async def get_login_logs(page: int = 1, page_size: int = 20) -> Tuple[List[dict], int]:
    """
    获取登录日志
    
    Args:
        page: 页码
        page_size: 每页数量
        
    Returns:
        (日志列表, 总数)
    """
    engine = get_sys_db_engine()
    offset = (page - 1) * page_size
    
    try:
        with engine.connect() as conn:
            # 获取总数
            count_result = conn.execute(text("SELECT COUNT(*) FROM sys_login_logs"))
            total = count_result.scalar()
            
            # 获取列表
            result = conn.execute(
                text("""
                    SELECT id, user_id, username, ip_address, location, user_agent, login_time, status, message
                    FROM sys_login_logs
                    ORDER BY login_time DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": page_size, "offset": offset}
            )
            
            logs = [dict(row._mapping) for row in result]
            
            return logs, total
            
    except Exception as e:
        logger.error(f"[AuthService] 获取登录日志失败: {e}")
        return [], 0

async def get_user_by_id(user_id: int) -> Optional[dict]:
    """
    根据ID获取用户信息
    
    Args:
        user_id: 用户ID
        
    Returns:
        用户信息或None
    """
    engine = get_sys_db_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, username, nickname, is_root, status, created_at, updated_at
                    FROM sys_users WHERE id = :id
                """),
                {"id": user_id}
            )
            row = result.fetchone()
            
            if row:
                user = dict(row._mapping)
                user["is_root"] = bool(user["is_root"])
                return user
            return None
            
    except Exception as e:
        logger.error(f"[AuthService] 获取用户信息失败: {e}")
        return None
