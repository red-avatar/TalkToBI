"""
向量管理服务 (VectorService)

功能：
    1. 触发元数据提取、增强、向量化
    2. 查看 PG 向量数据（只读）
    3. 获取向量统计信息

使用方式：
    vector_service = get_vector_service()
    
    # 触发向量构建流程
    result = vector_service.trigger_extract()
    result = vector_service.trigger_enhance()
    result = vector_service.trigger_build()
    
    # 查看向量数据
    vectors = vector_service.get_vectors(page=1, page_size=20)

Author: CYJ
Time: 2025-11-29
"""
import os
import sys
import json
import logging
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VectorService:
    """
    向量管理服务
    
    功能：
    1. 触发向量构建流程（调用脚本）
    2. 查看 PG 向量数据
    3. 向量统计
    
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
        
        # 脚本路径
        self._backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._scripts_dir = os.path.join(self._backend_root, "scripts", "knowledge")
    
    def _get_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(**self._conn_params)
    
    def _run_script(self, script_name: str) -> Dict[str, Any]:
        """
        运行指定的 Python 脚本
        
        Args:
            script_name: 脚本文件名
            
        Returns:
            包含 success, message, output 的字典
            
        Author: CYJ
        Time: 2025-11-29
        """
        script_path = os.path.join(self._scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return {
                "success": False,
                "message": f"脚本不存在: {script_name}",
                "output": ""
            }
        
        try:
            # 使用当前 Python 解释器运行脚本
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                cwd=self._scripts_dir
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "执行成功",
                    "output": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": "执行失败",
                    "output": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "执行超时（超过10分钟）",
                "output": ""
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"执行异常: {str(e)}",
                "output": ""
            }
    
    def trigger_extract(self) -> Dict[str, Any]:
        """
        触发元数据提取
        
        Author: CYJ
        Time: 2025-11-29
        """
        logger.info("[VectorService] 触发元数据提取...")
        return self._run_script("extract_schema.py")
    
    def trigger_enhance(self) -> Dict[str, Any]:
        """
        触发语义增强
        
        Author: CYJ
        Time: 2025-11-29
        """
        logger.info("[VectorService] 触发语义增强...")
        return self._run_script("enhance_schema.py")
    
    def trigger_build(self) -> Dict[str, Any]:
        """
        触发向量构建
        
        Author: CYJ
        Time: 2025-11-29
        """
        logger.info("[VectorService] 触发向量构建...")
        return self._run_script("build_vector_db.py")
    
    def get_vectors(
        self,
        page: int = 1,
        page_size: int = 20,
        object_type: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取向量数据列表（只读）
        
        Args:
            page: 页码
            page_size: 每页大小
            object_type: 类型筛选 (table/column)
            keyword: 关键词搜索
            
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
            
            if object_type:
                conditions.append("object_type = %s")
                values.append(object_type)
            if keyword:
                conditions.append("(object_name ILIKE %s OR enriched_description ILIKE %s)")
                values.extend([f"%{keyword}%", f"%{keyword}%"])
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 查询总数
                cur.execute(
                    f"SELECT COUNT(*) as total FROM schema_embeddings {where_clause}",
                    values
                )
                total = cur.fetchone()['total']
                
                # 查询数据（不包含 embedding 向量，太大）
                offset = (page - 1) * page_size
                cur.execute(
                    f"""
                    SELECT id, object_type, object_name, original_description,
                           enriched_description, metadata_json
                    FROM schema_embeddings
                    {where_clause}
                    ORDER BY id
                    LIMIT %s OFFSET %s
                    """,
                    values + [page_size, offset]
                )
                rows = cur.fetchall()
                
                items = []
                for row in rows:
                    items.append({
                        "id": row['id'],
                        "object_type": row['object_type'],
                        "object_name": row['object_name'],
                        "original_description": row['original_description'],
                        "enriched_description": row['enriched_description'],
                        "metadata": row['metadata_json']
                    })
                
                return {
                    "items": items,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
                
        except Exception as e:
            logger.error(f"[VectorService] 获取向量列表失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        finally:
            if conn:
                conn.close()
    
    def get_vector_by_id(self, vector_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条向量详情
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, object_type, object_name, original_description,
                           enriched_description, metadata_json
                    FROM schema_embeddings WHERE id = %s
                    """,
                    (vector_id,)
                )
                row = cur.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row['id'],
                    "object_type": row['object_type'],
                    "object_name": row['object_name'],
                    "original_description": row['original_description'],
                    "enriched_description": row['enriched_description'],
                    "metadata": row['metadata_json']
                }
                
        except Exception as e:
            logger.error(f"[VectorService] 获取向量详情失败: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取向量统计信息
        
        Author: CYJ
        Time: 2025-11-29
        """
        conn = None
        try:
            conn = self._get_connection()
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE object_type = 'table') as table_count,
                        COUNT(*) FILTER (WHERE object_type = 'column') as column_count
                    FROM schema_embeddings
                    """
                )
                stats = cur.fetchone()
                
                return {
                    "total": stats['total'] or 0,
                    "table_count": stats['table_count'] or 0,
                    "column_count": stats['column_count'] or 0
                }
                
        except Exception as e:
            logger.error(f"[VectorService] 获取向量统计失败: {e}")
            return {"total": 0, "table_count": 0, "column_count": 0}
        finally:
            if conn:
                conn.close()
    
    def get_build_status(self) -> Dict[str, Any]:
        """
        获取构建状态（检查数据文件）
        
        Author: CYJ
        Time: 2025-11-29
        """
        data_dir = os.path.join(self._scripts_dir, "data")
        
        files_status = {}
        
        # 检查各阶段的数据文件
        files_to_check = [
            ("full_schema.json", "元数据提取"),
            ("enriched_schema.json", "语义增强"),
            ("vectors_with_embeddings.json", "向量构建")
        ]
        
        for filename, stage_name in files_to_check:
            filepath = os.path.join(data_dir, filename)
            if os.path.exists(filepath):
                stat = os.stat(filepath)
                files_status[stage_name] = {
                    "exists": True,
                    "size_kb": round(stat.st_size / 1024, 2),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            else:
                files_status[stage_name] = {
                    "exists": False,
                    "size_kb": 0,
                    "modified_at": None
                }
        
        # 获取数据库中的向量数量
        db_stats = self.get_stats()
        
        return {
            "files": files_status,
            "database": db_stats
        }


# 单例模式
_vector_service: Optional[VectorService] = None


def get_vector_service() -> VectorService:
    """
    获取 VectorService 单例
    
    Author: CYJ
    Time: 2025-11-29
    """
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
