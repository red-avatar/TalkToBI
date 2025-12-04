"""
数据库连接管理模块

提供统一的数据库连接池管理，支持:
1. MySQL (业务数据库) - SQLAlchemy 连接池
2. PostgreSQL (向量/缓存数据库) - psycopg2 连接池

使用方式:
    from app.core.database import (
        get_mysql_engine,
        get_pg_connection,
        release_pg_connection
    )
    
    # MySQL (SQLAlchemy)
    engine = get_mysql_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
    
    # PostgreSQL (psycopg2 连接池)
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        release_pg_connection(conn)
    
    # 或使用上下文管理器
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

Author: CYJ
"""
import logging
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import psycopg2
from psycopg2 import pool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 全局连接池实例
_mysql_engine: Optional[Engine] = None
_sys_db_engine: Optional[Engine] = None  # 系统数据库连接池
_pg_pool: Optional[pool.ThreadedConnectionPool] = None

# =============================================================================
# MySQL (SQLAlchemy) 连接管理
# =============================================================================

def get_mysql_engine() -> Engine:
    """
    获取 MySQL SQLAlchemy Engine（带连接池）
    
    SQLAlchemy 默认使用连接池，这里使用 QueuePool 配置。
    
    Returns:
        SQLAlchemy Engine 实例
        
    Author: CYJ
    """
    global _mysql_engine
    
    if _mysql_engine is None:
        settings = get_settings()
        
        url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
            settings.MYSQL_USER,
            settings.MYSQL_PASSWORD,
            settings.MYSQL_HOST,
            settings.MYSQL_PORT,
            settings.MYSQL_DB
        )
        
        _mysql_engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,           # 连接池大小
            max_overflow=10,       # 超出 pool_size 后最多创建的连接数
            pool_timeout=30,       # 等待连接超时（秒）
            pool_recycle=3600,     # 连接回收时间（秒），避免 MySQL 8小时断开
            pool_pre_ping=True,    # 使用前 ping 检测连接是否有效
            echo=False             # 不打印 SQL 日志
        )
        
        logger.info("[Database] MySQL 连接池已初始化 (pool_size=5, max_overflow=10)")
    
    return _mysql_engine

def close_mysql_engine():
    """
    关闭 MySQL 连接池
    
    用于应用关闭时清理资源。
    
    Author: CYJ
    """
    global _mysql_engine
    
    if _mysql_engine is not None:
        _mysql_engine.dispose()
        _mysql_engine = None
        logger.info("[Database] MySQL 连接池已关闭")

# =============================================================================
# 系统数据库 (MySQL) 连接管理
# Author: CYJ
# Time: 2025-12-03
# =============================================================================

def get_sys_db_engine() -> Engine:
    """
    获取系统数据库 SQLAlchemy Engine（带连接池）
    
    用于存储系统数据（用户、登录日志等）
    
    Returns:
        SQLAlchemy Engine 实例
    """
    global _sys_db_engine
    
    if _sys_db_engine is None:
        settings = get_settings()
        
        url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
            settings.SYS_DB_USER,
            settings.SYS_DB_PASSWORD,
            settings.SYS_DB_HOST,
            settings.SYS_DB_PORT,
            settings.SYS_DB_NAME
        )
        
        _sys_db_engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=3,           # 连接池大小（系统库访问量小）
            max_overflow=5,        # 超出 pool_size 后最多创建的连接数
            pool_timeout=30,       # 等待连接超时（秒）
            pool_recycle=3600,     # 连接回收时间（秒）
            pool_pre_ping=True,    # 使用前 ping 检测连接是否有效
            echo=False
        )
        
        logger.info("[Database] 系统数据库连接池已初始化 (pool_size=3, max_overflow=5)")
    
    return _sys_db_engine

def close_sys_db_engine():
    """关闭系统数据库连接池"""
    global _sys_db_engine
    
    if _sys_db_engine is not None:
        _sys_db_engine.dispose()
        _sys_db_engine = None
        logger.info("[Database] 系统数据库连接池已关闭")

# =============================================================================
# PostgreSQL (psycopg2) 连接池管理
# =============================================================================

def _init_pg_pool() -> pool.ThreadedConnectionPool:
    """
    初始化 PostgreSQL 连接池
    
    Returns:
        ThreadedConnectionPool 实例
        
    Author: CYJ
    """
    settings = get_settings()
    
    pg_pool = pool.ThreadedConnectionPool(
        minconn=2,              # 最小连接数
        maxconn=10,             # 最大连接数
        host=settings.VECTOR_DB_HOST,
        port=settings.VECTOR_DB_PORT,
        user=settings.VECTOR_DB_USER,
        password=settings.VECTOR_DB_PASSWORD,
        database=settings.VECTOR_DB_NAME,
    )
    
    logger.info("[Database] PostgreSQL 连接池已初始化 (minconn=2, maxconn=10)")
    return pg_pool

def get_pg_connection():
    """
    从连接池获取 PostgreSQL 连接
    
    注意：使用完毕后必须调用 release_pg_connection() 归还连接。
    推荐使用 pg_connection() 上下文管理器。
    
    Returns:
        psycopg2 connection 对象
        
    Author: CYJ
    """
    global _pg_pool
    
    if _pg_pool is None:
        _pg_pool = _init_pg_pool()
    
    try:
        conn = _pg_pool.getconn()
        return conn
    except pool.PoolError as e:
        logger.error(f"[Database] PostgreSQL 连接池耗尽: {e}")
        raise

def release_pg_connection(conn):
    """
    归还 PostgreSQL 连接到连接池
    
    Args:
        conn: psycopg2 connection 对象
        
    Author: CYJ
    """
    global _pg_pool
    
    if _pg_pool is not None and conn is not None:
        try:
            _pg_pool.putconn(conn)
        except Exception as e:
            logger.warning(f"[Database] 归还 PostgreSQL 连接失败: {e}")

@contextmanager
def pg_connection():
    """
    PostgreSQL 连接上下文管理器
    
    自动获取和归还连接，推荐使用此方式。
    
    Usage:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                
    Author: CYJ
    """
    conn = None
    try:
        conn = get_pg_connection()
        yield conn
    finally:
        if conn is not None:
            release_pg_connection(conn)

def close_pg_pool():
    """
    关闭 PostgreSQL 连接池
    
    用于应用关闭时清理资源。
    
    Author: CYJ
    """
    global _pg_pool
    
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None
        logger.info("[Database] PostgreSQL 连接池已关闭")

# =============================================================================
# 应用生命周期管理
# =============================================================================

def init_database():
    """
    初始化所有数据库连接池
    
    在应用启动时调用。
    
    Author: CYJ
    """
    # 预初始化连接池
    get_mysql_engine()
    get_pg_connection()  # 触发 pool 初始化
    # 立即归还测试连接
    release_pg_connection(get_pg_connection())
    
    logger.info("[Database] 数据库连接池初始化完成")

def close_database():
    """
    关闭所有数据库连接池
    
    在应用关闭时调用。
    
    Author: CYJ
    """
    close_mysql_engine()
    close_sys_db_engine()
    close_pg_pool()
    logger.info("[Database] 所有数据库连接池已关闭")
