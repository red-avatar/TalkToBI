"""
功能：查询缓存服务 (Cache Service)
说明：
    负责查询结果的缓存管理，支持精确匹配和异步写入。
    
    V2: 改用同步 psycopg2 连接，避免异步事件循环问题
    
核心功能：
    1. check_cache: 检查缓存（精确匹配）
    2. save_to_cache: 保存到缓存
    3. calculate_cache_score: 计算缓存评分
    4. invalidate_cache: 失效缓存

使用方式：
    cache_service = get_cache_service()
    
    # 检查缓存（同步调用）
    cache_hit = cache_service.check_cache("今年销售额多少")
    if cache_hit:
        sql = cache_hit.sql
        
    # 保存缓存
    cache_service.save_to_cache(query, sql, score)

Author: ChatBI Team
Time: 2025-11-28 (V2)
"""

import hashlib
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CacheHit:
    """缓存命中结果"""
    id: int
    query_hash: str
    original_query: str
    rewritten_query: Optional[str]
    sql: str
    tables_used: List[str]
    cache_score: int
    hit_count: int


class CacheService:
    """
    查询缓存服务 (V2 - 同步版本)
    
    功能：
    1. 精确匹配缓存查询
    2. 同步写入缓存
    3. 缓存评分计算
    4. 缓存失效管理
    """
    
    def __init__(self):
        """初始化缓存服务"""
        self._settings = get_settings()
        self._conn_params = {
            'host': self._settings.VECTOR_DB_HOST,
            'port': self._settings.VECTOR_DB_PORT,
            'user': self._settings.VECTOR_DB_USER,
            'password': self._settings.VECTOR_DB_PASSWORD,
            'database': self._settings.VECTOR_DB_NAME,
        }
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(**self._conn_params)
    
    @staticmethod
    def _hash_query(query: str) -> str:
        """
        计算查询的哈希值
        
        Args:
            query: 用户原始问题
            
        Returns:
            SHA256 哈希值
        """
        # 标准化：去除首尾空格，统一为小写
        normalized = query.strip().lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def check_cache(self, query: str) -> Optional[CacheHit]:
        """
        检查缓存（精确匹配，同步版本）
        
        Args:
            query: 用户原始问题
            
        Returns:
            CacheHit 如果命中，否则 None
        """
        conn = None
        try:
            conn = self._get_connection()
            query_hash = self._hash_query(query)
            logger.info(f"[CacheService] 检查缓存: query='{query[:50]}', hash={query_hash[:16]}...")
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, query_hash, original_query, rewritten_query, 
                           sql, tables_used, cache_score, hit_count
                    FROM query_cache
                    WHERE query_hash = %s AND status = 'active'
                    """,
                    (query_hash,)
                )
                row = cur.fetchone()
                
                if row:
                    # 更新命中次数
                    cur.execute(
                        "UPDATE query_cache SET hit_count = hit_count + 1 WHERE id = %s",
                        (row['id'],)
                    )
                    conn.commit()
                    
                    # V16.1: 增强日志，显示评分信息
                    logger.info(f"[CacheService] 缓存命中: query_hash={query_hash[:16]}..., hit_count={row['hit_count'] + 1}, cache_score={row['cache_score']}")
                    
                    return CacheHit(
                        id=row['id'],
                        query_hash=row['query_hash'],
                        original_query=row['original_query'],
                        rewritten_query=row['rewritten_query'],
                        sql=row['sql'],
                        tables_used=row['tables_used'] or [],
                        cache_score=row['cache_score'],
                        hit_count=row['hit_count'] + 1
                    )
                
                logger.debug(f"[CacheService] 缓存未命中: query_hash={query_hash[:16]}...")
                return None
                
        except Exception as e:
            logger.error(f"[CacheService] 检查缓存失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def save_to_cache(
        self,
        original_query: str,
        sql: str,
        cache_score: int,
        rewritten_query: Optional[str] = None,
        tables_used: Optional[List[str]] = None
    ) -> bool:
        """
        保存到缓存（同步版本）
        
        Args:
            original_query: 用户原始问题
            sql: 生成的 SQL
            cache_score: 缓存评分
            rewritten_query: 改写后的问题
            tables_used: 使用的表名列表
            
        Returns:
            是否保存成功
        """
        conn = None
        try:
            conn = self._get_connection()
            query_hash = self._hash_query(original_query)
            
            with conn.cursor() as cur:
                # 使用 UPSERT 避免重复
                cur.execute(
                    """
                    INSERT INTO query_cache 
                        (query_hash, original_query, rewritten_query, sql, tables_used, cache_score)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (query_hash) 
                    DO UPDATE SET 
                        sql = EXCLUDED.sql,
                        rewritten_query = EXCLUDED.rewritten_query,
                        tables_used = EXCLUDED.tables_used,
                        cache_score = EXCLUDED.cache_score,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (query_hash, original_query, rewritten_query, sql, tables_used or [], cache_score)
                )
                conn.commit()
                
                logger.info(f"[CacheService] 缓存已保存: query_hash={query_hash[:16]}..., score={cache_score}")
                return True
                
        except Exception as e:
            logger.error(f"[CacheService] 保存缓存失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    @staticmethod
    def calculate_cache_score(
        sql_success: bool,
        result_not_empty: bool,
        result_validator_passed: bool = False,
        completeness_validator_passed: bool = False,
        path_validator_passed: bool = False
    ) -> int:
        """
        计算缓存评分
        
        评分规则：
        - SQL 执行成功（无报错）: +30
        - 返回结果非空: +20
        - ResultValidator 通过: +20
        - CompletenessValidator 通过: +20
        - PathIntentValidator 通过: +10
        
        Args:
            sql_success: SQL 是否执行成功
            result_not_empty: 结果是否非空
            result_validator_passed: 结果验证器是否通过
            completeness_validator_passed: 完整性验证器是否通过
            path_validator_passed: 路径意图验证器是否通过
            
        Returns:
            缓存评分 (0-100)
        """
        score = 0
        
        if sql_success:
            score += 30
        
        if result_not_empty:
            score += 20
        
        if result_validator_passed:
            score += 20
        
        if completeness_validator_passed:
            score += 20
        
        if path_validator_passed:
            score += 10
        
        return score
    
    def invalidate_cache(self, cache_id: int) -> bool:
        """
        失效指定缓存（同步版本）
        
        Args:
            cache_id: 缓存 ID
            
        Returns:
            是否操作成功
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE query_cache SET status = 'invalid' WHERE id = %s",
                    (cache_id,)
                )
                conn.commit()
                
                logger.info(f"[CacheService] 缓存已失效: id={cache_id}")
                return True
                
        except Exception as e:
            logger.error(f"[CacheService] 失效缓存失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def invalidate_by_tables(self, table_names: List[str]) -> int:
        """
        失效使用指定表的所有缓存（同步版本）
        
        Args:
            table_names: 变更的表名列表
            
        Returns:
            失效的缓存数量
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE query_cache 
                    SET status = 'deprecated' 
                    WHERE status = 'active' 
                    AND tables_used && %s
                    """,
                    (table_names,)
                )
                count = cur.rowcount
                conn.commit()
                
                logger.info(f"[CacheService] 已失效 {count} 条缓存（涉及表: {table_names}）")
                return count
                
        except Exception as e:
            logger.error(f"[CacheService] 批量失效缓存失败: {e}")
            return 0
        finally:
            if conn:
                conn.close()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息（同步版本）
        
        Returns:
            统计信息字典
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        COUNT(*) FILTER (WHERE status = 'invalid') as invalid,
                        COUNT(*) FILTER (WHERE status = 'deprecated') as deprecated,
                        SUM(hit_count) as total_hits,
                        AVG(cache_score) as avg_score
                    FROM query_cache
                    """
                )
                stats = cur.fetchone()
                
                return {
                    "total": stats['total'] or 0,
                    "active": stats['active'] or 0,
                    "invalid": stats['invalid'] or 0,
                    "deprecated": stats['deprecated'] or 0,
                    "total_hits": stats['total_hits'] or 0,
                    "avg_score": round(float(stats['avg_score'] or 0), 2)
                }
                
        except Exception as e:
            logger.error(f"[CacheService] 获取统计信息失败: {e}")
            return {}
        finally:
            if conn:
                conn.close()
    
    # ========== 以下为管理接口新增方法 (Author: CYJ, Time: 2025-11-29) ==========
    
    def get_cache_list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取缓存列表（分页）
        
        Args:
            page: 页码
            page_size: 每页大小
            status: 状态筛选 (active/invalid/deprecated)
            keyword: 关键词搜索（搜索原始问题）
            
        Returns:
            包含 items, total, page, page_size 的字典
            
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            # 构建查询条件
            conditions = []
            values = []
            
            if status:
                conditions.append("status = %s")
                values.append(status)
            if keyword:
                conditions.append("original_query ILIKE %s")
                values.append(f"%{keyword}%")
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 查询总数
                cur.execute(
                    f"SELECT COUNT(*) as total FROM query_cache {where_clause}",
                    values
                )
                total = cur.fetchone()['total']
                
                # 查询数据
                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    SELECT id, query_hash, original_query, rewritten_query, sql,
                           tables_used, cache_score, hit_count, status,
                           created_at, updated_at
                    FROM query_cache
                    {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    values + [page_size, offset]
                )
                rows = cur.fetchall()
                
                items = []
                for row in rows:
                    items.append({
                        "id": row['id'],
                        "query_hash": row['query_hash'],
                        "original_query": row['original_query'],
                        "rewritten_query": row['rewritten_query'],
                        "sql": row['sql'],
                        "tables_used": row['tables_used'] or [],
                        "cache_score": row['cache_score'],
                        "hit_count": row['hit_count'],
                        "status": row['status'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                        "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                    })
                
                return {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
                
        except Exception as e:
            logger.error(f"[CacheService] 获取缓存列表失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        finally:
            if conn:
                conn.close()
    
    def get_cache_by_id(self, cache_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条缓存详情
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM query_cache WHERE id = %s",
                    (cache_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row['id'],
                    "query_hash": row['query_hash'],
                    "original_query": row['original_query'],
                    "rewritten_query": row['rewritten_query'],
                    "sql": row['sql'],
                    "tables_used": row['tables_used'] or [],
                    "cache_score": row['cache_score'],
                    "hit_count": row['hit_count'],
                    "status": row['status'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                }
                
        except Exception as e:
            logger.error(f"[CacheService] 获取缓存详情失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def delete_cache(self, cache_id: int) -> bool:
        """
        删除缓存记录（硬删除）
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM query_cache WHERE id = %s",
                    (cache_id,)
                )
                deleted = cur.rowcount > 0
                conn.commit()
                
                if deleted:
                    logger.info(f"[CacheService] 缓存已删除: id={cache_id}")
                return deleted
                
        except Exception as e:
            logger.error(f"[CacheService] 删除缓存失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def update_cache_status(self, cache_id: int, status: str) -> bool:
        """
        更新缓存状态
        
        Args:
            cache_id: 缓存ID
            status: 新状态 (active/invalid/deprecated)
            
        Author: CYJ
        Time: 2025-11-29
        """
        if status not in ('active', 'invalid', 'deprecated'):
            logger.warning(f"[CacheService] 无效的状态值: {status}")
            return False
        
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE query_cache SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (status, cache_id)
                )
                updated = cur.rowcount > 0
                conn.commit()
                
                if updated:
                    logger.info(f"[CacheService] 缓存状态已更新: id={cache_id}, status={status}")
                return updated
                
        except Exception as e:
            logger.error(f"[CacheService] 更新缓存状态失败: {e}")
            return False
        finally:
            if conn:
                conn.close()


# 单例模式
_cache_service_instance: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    获取 CacheService 单例
    
    Returns:
        CacheService 实例
    """
    global _cache_service_instance
    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
    return _cache_service_instance
