"""
执行记录服务 (ExecutionLogService)

功能：
    记录每次查询的执行历史，用于统计分析和历史查看

使用方式：
    log_service = get_execution_log_service()
    
    # 记录执行
    log_id = log_service.log_execution(
        query_text="今年销售额多少",
        sql_generated="SELECT SUM(amount) FROM orders",
        status="success",
        ...
    )
    
    # 查询历史
    logs = log_service.get_logs(page=1, page_size=20)

Author: CYJ
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLogRecord:
    """执行记录数据类"""
    id: int
    query_text: str
    rewritten_query: Optional[str]
    sql_generated: Optional[str]
    tables_used: Optional[List[str]]
    status: str
    error_message: Optional[str]
    result_row_count: Optional[int]
    execution_time_ms: Optional[int]
    cache_score: Optional[int]
    cache_hit: bool
    session_id: Optional[str]
    message_id: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    chart_type: Optional[str]
    created_at: datetime
    extra_data: Optional[Dict]


class ExecutionLogService:
    """
    执行记录服务
    
    功能：
    1. 记录每次查询执行
    2. 查询历史记录（分页）
    3. 统计信息
    
    Author: CYJ
    Time: 2025-11-29
    """
    
    def __init__(self):
        """初始化服务"""
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
    
    def log_execution(
        self,
        query_text: str,
        status: str = "pending",
        rewritten_query: Optional[str] = None,
        sql_generated: Optional[str] = None,
        tables_used: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        result_row_count: Optional[int] = None,
        execution_time_ms: Optional[int] = None,
        cache_score: Optional[int] = None,
        cache_hit: bool = False,
        session_id: Optional[str] = None,
        message_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        chart_type: Optional[str] = None,
        extra_data: Optional[Dict] = None
    ) -> Optional[int]:
        """
        记录一次执行
        
        Args:
            query_text: 用户原始问题
            status: 状态 (success/error/timeout/pending)
            rewritten_query: 改写后的问题
            sql_generated: 生成的SQL
            tables_used: 使用的表列表
            error_message: 错误信息
            result_row_count: 结果行数
            execution_time_ms: 执行耗时(ms)
            cache_score: 缓存评分
            cache_hit: 是否命中缓存
            session_id: 会话ID
            message_id: 消息ID
            user_id: 用户ID (预留)
            user_name: 用户名 (预留)
            chart_type: 图表类型
            extra_data: 额外数据
            
        Returns:
            记录ID，失败返回None
            
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO execution_log 
                        (query_text, rewritten_query, sql_generated, tables_used,
                         status, error_message, result_row_count, execution_time_ms,
                         cache_score, cache_hit, session_id, message_id,
                         user_id, user_name, chart_type, extra_data)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (query_text, rewritten_query, sql_generated, tables_used,
                     status, error_message, result_row_count, execution_time_ms,
                     cache_score, cache_hit, session_id, message_id,
                     user_id, user_name, chart_type, 
                     psycopg2.extras.Json(extra_data) if extra_data else None)
                )
                log_id = cur.fetchone()[0]
                conn.commit()
                
                logger.debug(f"[ExecutionLog] 记录已保存: id={log_id}")
                return log_id
                
        except Exception as e:
            logger.error(f"[ExecutionLog] 记录保存失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def update_execution(
        self,
        log_id: int,
        status: Optional[str] = None,
        sql_generated: Optional[str] = None,
        tables_used: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        result_row_count: Optional[int] = None,
        execution_time_ms: Optional[int] = None,
        cache_score: Optional[int] = None,
        chart_type: Optional[str] = None
    ) -> bool:
        """
        更新执行记录
        
        用于在执行过程中逐步更新记录状态
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            # 动态构建更新字段
            updates = []
            values = []
            
            if status is not None:
                updates.append("status = %s")
                values.append(status)
            if sql_generated is not None:
                updates.append("sql_generated = %s")
                values.append(sql_generated)
            if tables_used is not None:
                updates.append("tables_used = %s")
                values.append(tables_used)
            if error_message is not None:
                updates.append("error_message = %s")
                values.append(error_message)
            if result_row_count is not None:
                updates.append("result_row_count = %s")
                values.append(result_row_count)
            if execution_time_ms is not None:
                updates.append("execution_time_ms = %s")
                values.append(execution_time_ms)
            if cache_score is not None:
                updates.append("cache_score = %s")
                values.append(cache_score)
            if chart_type is not None:
                updates.append("chart_type = %s")
                values.append(chart_type)
            
            if not updates:
                return True
            
            values.append(log_id)
            
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE execution_log SET {', '.join(updates)} WHERE id = %s",
                    values
                )
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"[ExecutionLog] 更新失败: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        查询执行记录列表
        
        Args:
            page: 页码
            page_size: 每页大小
            status: 状态筛选
            session_id: 会话ID筛选
            user_id: 用户ID筛选
            start_date: 开始时间
            end_date: 结束时间
            
        Returns:
            包含items, total, page, page_size的字典
            
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
            if session_id:
                conditions.append("session_id = %s")
                values.append(session_id)
            if user_id:
                conditions.append("user_id = %s")
                values.append(user_id)
            if start_date:
                conditions.append("created_at >= %s")
                values.append(start_date)
            if end_date:
                conditions.append("created_at <= %s")
                values.append(end_date)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 查询总数
                cur.execute(f"SELECT COUNT(*) as total FROM execution_log {where_clause}", values)
                total = cur.fetchone()['total']
                
                # 查询数据
                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    SELECT id, query_text, rewritten_query, sql_generated, tables_used,
                           status, error_message, result_row_count, execution_time_ms,
                           cache_score, cache_hit, session_id, message_id,
                           user_id, user_name, chart_type, created_at
                    FROM execution_log 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    values + [page_size, offset]
                )
                rows = cur.fetchall()
                
                items = []
                for row in rows:
                    items.append({
                        "id": row['id'],
                        "query_text": row['query_text'],
                        "rewritten_query": row['rewritten_query'],
                        "sql_generated": row['sql_generated'],
                        "tables_used": row['tables_used'] or [],
                        "status": row['status'],
                        "error_message": row['error_message'],
                        "result_row_count": row['result_row_count'],
                        "execution_time_ms": row['execution_time_ms'],
                        "cache_score": row['cache_score'],
                        "cache_hit": row['cache_hit'],
                        "session_id": row['session_id'],
                        "message_id": row['message_id'],
                        "chart_type": row['chart_type'],
                        "created_at": row['created_at'].isoformat() if row['created_at'] else None
                    })
                
                return {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
                
        except Exception as e:
            logger.error(f"[ExecutionLog] 查询失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        finally:
            if conn:
                conn.close()
    
    def get_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条记录详情
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM execution_log WHERE id = %s
                    """,
                    (log_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row['id'],
                    "query_text": row['query_text'],
                    "rewritten_query": row['rewritten_query'],
                    "sql_generated": row['sql_generated'],
                    "tables_used": row['tables_used'] or [],
                    "status": row['status'],
                    "error_message": row['error_message'],
                    "result_row_count": row['result_row_count'],
                    "execution_time_ms": row['execution_time_ms'],
                    "cache_score": row['cache_score'],
                    "cache_hit": row['cache_hit'],
                    "session_id": row['session_id'],
                    "message_id": row['message_id'],
                    "user_id": row['user_id'],
                    "user_name": row['user_name'],
                    "chart_type": row['chart_type'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "extra_data": row['extra_data']
                }
                
        except Exception as e:
            logger.error(f"[ExecutionLog] 获取详情失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            包含 total, success_count, error_count, success_rate, 
            avg_execution_time, cache_hit_rate 的统计字典
            
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            # 构建时间条件
            conditions = []
            values = []
            if start_date:
                conditions.append("created_at >= %s")
                values.append(start_date)
            if end_date:
                conditions.append("created_at <= %s")
                values.append(end_date)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'success') as success_count,
                        COUNT(*) FILTER (WHERE status = 'error') as error_count,
                        COUNT(*) FILTER (WHERE status = 'timeout') as timeout_count,
                        COUNT(*) FILTER (WHERE cache_hit = true) as cache_hit_count,
                        AVG(execution_time_ms) FILTER (WHERE execution_time_ms IS NOT NULL) as avg_execution_time,
                        AVG(cache_score) FILTER (WHERE cache_score IS NOT NULL) as avg_cache_score
                    FROM execution_log
                    {where_clause}
                    """,
                    values
                )
                stats = cur.fetchone()
                
                total = stats['total'] or 0
                success_count = stats['success_count'] or 0
                cache_hit_count = stats['cache_hit_count'] or 0
                
                return {
                    "total": total,
                    "success_count": success_count,
                    "error_count": stats['error_count'] or 0,
                    "timeout_count": stats['timeout_count'] or 0,
                    "success_rate": round(success_count / total * 100, 2) if total > 0 else 0,
                    "cache_hit_count": cache_hit_count,
                    "cache_hit_rate": round(cache_hit_count / total * 100, 2) if total > 0 else 0,
                    "avg_execution_time_ms": round(float(stats['avg_execution_time'] or 0), 2),
                    "avg_cache_score": round(float(stats['avg_cache_score'] or 0), 2)
                }
                
        except Exception as e:
            logger.error(f"[ExecutionLog] 获取统计失败: {e}")
            return {
                "total": 0,
                "success_count": 0,
                "error_count": 0,
                "timeout_count": 0,
                "success_rate": 0,
                "cache_hit_count": 0,
                "cache_hit_rate": 0,
                "avg_execution_time_ms": 0,
                "avg_cache_score": 0
            }
        finally:
            if conn:
                conn.close()


# 单例模式
_execution_log_service: Optional[ExecutionLogService] = None


def get_execution_log_service() -> ExecutionLogService:
    """
    获取 ExecutionLogService 单例
    
    Author: CYJ
    Time: 2025-11-29
    """
    global _execution_log_service
    if _execution_log_service is None:
        _execution_log_service = ExecutionLogService()
    return _execution_log_service
