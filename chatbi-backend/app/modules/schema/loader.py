"""
功能：Schema 加载器
说明：封装 SQLAlchemy 逻辑，用于连接数据库并提取全量表结构元数据（Schema Introspection）。
作者：CYJ
"""
import logging
from typing import List, Dict, Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from app.core.config import get_settings
from app.models.schema import TableSchema, ColumnSchema

settings = get_settings()
logger = logging.getLogger(__name__)

class SchemaLoader:
    """
    Extracts full schema metadata from the live database via SQLAlchemy.
    """
    def __init__(self):
        # Construct connection URL from settings
        user = settings.MYSQL_USER
        pwd = settings.MYSQL_PASSWORD
        host = settings.MYSQL_HOST
        port = settings.MYSQL_PORT
        db = settings.MYSQL_DB
        self.url = "mysql+pymysql://{}:{}@{}:{}/{}".format(user, pwd, host, port, db)
        self.engine = create_engine(self.url)
        
    def get_all_tables(self) -> List[str]:
        """Get list of all table names."""
        inspector = inspect(self.engine)
        return inspector.get_table_names()
    
    def get_table_schema(self, table_name: str) -> TableSchema:
        """Get detailed schema for a single table."""
        inspector = inspect(self.engine)
        
        # 1. Get columns
        columns_info = inspector.get_columns(table_name)
        
        # 2. Get constraints
        pk_constraint = inspector.get_pk_constraint(table_name)
        pks = pk_constraint.get('constrained_columns', []) if pk_constraint else []
        
        fks = inspector.get_foreign_keys(table_name)
        fk_columns = [fk['constrained_columns'][0] for fk in fks if fk['constrained_columns']]
        
        # 3. Get table comment (Try multiple ways as driver support varies)
        table_comment = inspector.get_table_comment(table_name).get('text', '')
        
        # Build ColumnSchema objects
        columns = []
        for col in columns_info:
            # Helper to clean type string
            data_type_str = str(col['type']).lower()
            col_name = col['name']
            col_comment = col.get('comment', '') or ''
            
            # Heuristic to fetch sample values for categorical columns
            sample_values = []
            should_fetch_samples = False
            
            # Condition 1: Explicitly mentioned in comments (e.g. "0=No, 1=Yes")
            if "=" in col_comment and ("0" in col_comment or "1" in col_comment):
                 # We might rely on comment parsing, but fetching distinct values is safer verification
                 should_fetch_samples = True
            
            # Condition 2: Data type is enum-like or small int, or name suggests status/type
            # Exclude IDs, dates, and large text
            is_id = "id" in col_name.lower() and "status" not in col_name.lower()
            is_status_or_type = "status" in col_name.lower() or "type" in col_name.lower() or "code" in col_name.lower()
            is_small = "tinyint" in data_type_str or "smallint" in data_type_str or "enum" in data_type_str
            
            if (is_status_or_type or is_small) and not is_id:
                should_fetch_samples = True

            if should_fetch_samples:
                try:
                    # Limit to 20 distinct values to avoid performance hit on large tables
                    # Use safe parameter injection
                    query = text(f"SELECT DISTINCT `{col_name}` FROM `{table_name}` WHERE `{col_name}` IS NOT NULL LIMIT 20")
                    with self.engine.connect() as conn:
                        result = conn.execute(query)
                        sample_values = [str(row[0]) for row in result]
                except Exception as e:
                    logger.warning(f"Could not fetch samples for {table_name}.{col_name}: {e}")

            columns.append(ColumnSchema(
                name=col_name,
                data_type=data_type_str,
                comment=col_comment,
                is_primary_key=col_name in pks,
                is_foreign_key=col_name in fk_columns,
                sample_values=sample_values if sample_values else None
            ))
            
        return TableSchema(
            name=table_name,
            comment=table_comment,
            columns=columns,
            relationships=[] # Relationships are loaded separately from relationships.json
        )

    def extract_full_schema(self) -> List[TableSchema]:
        """Extract schema for all tables in the database."""
        tables = self.get_all_tables()
        schemas = []
        for table in tables:
            logger.info(f"Extracting schema for table: {table}")
            try:
                schemas.append(self.get_table_schema(table))
            except Exception as e:
                logger.error(f"Failed to extract table {table}: {e}")
        return schemas
