"""
功能：SQL 执行工具 (SQL Executor Tool)
说明：
    封装 SQLAlchemy 或 MySQL MCP 执行生成的 SQL。
    用于 SQL Agent 或 Executor Node 调用。
作者：CYJ
时间：2025-11-22
"""
from langchain_core.tools import BaseTool
from typing import List, Dict, Any
from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.core.config import get_settings
import logging
import json
from decimal import Decimal
from datetime import datetime, date

logger = logging.getLogger(__name__)
settings = get_settings()

class SqlExecutorInput(BaseModel):
    sql_query: str = Field(description="The SQL query to execute. Must be a SELECT statement.")

class SqlExecutorTool(BaseTool):
    name: str = "execute_sql_query"
    description: str = "Execute a SQL query against the database and return the results as a list of dictionaries."
    args_schema: type[BaseModel] = SqlExecutorInput
    
    # Use PrivateAttr for internal state that shouldn't be validated by Pydantic
    _engine: Engine = PrivateAttr()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Init engine
        user = settings.MYSQL_USER
        pwd = settings.MYSQL_PASSWORD
        host = settings.MYSQL_HOST
        port = settings.MYSQL_PORT
        db = settings.MYSQL_DB
        self._engine = create_engine(f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}")

    def _run(self, sql_query: str) -> str:
        """Execute the SQL query."""
        try:
            # Safety check: Only allow SELECT or WITH (CTE)
            sql_lower = sql_query.strip().lower()
            if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
                return "ERROR: Only SELECT or WITH (CTE) statements are allowed."
            
            # Execute
            with self._engine.connect() as conn:
                result = conn.execute(text(sql_query))
                keys = result.keys()
                data = [dict(zip(keys, row)) for row in result]
                
            # V2: 使用 JSON 序列化，正确处理 Decimal/datetime 类型
            # Author: CYJ
            # Time: 2025-11-26
            def json_serializer(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            return json.dumps(data, default=json_serializer, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"SQL Execution failed: {e}")
            return f"ERROR: {str(e)}"
