"""
数据库 Schema 数据模型

定义数据库表结构、列信息和关系的 Pydantic 模型。
用于 Schema 提取和知识图谱构建。

Author: CYJ
Refactored: 2025-12-03 (从 app/models/schema.py 迁移)
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ColumnSchema(BaseModel):
    """列信息模型"""
    name: str = Field(description="Column name")
    data_type: str = Field(description="Data type, e.g., 'varchar', 'int'")
    comment: Optional[str] = Field(None, description="Column description or comment")
    is_primary_key: bool = Field(False, description="Whether this column is part of the primary key")
    is_foreign_key: bool = Field(False, description="Whether this column is a foreign key")
    sample_values: Optional[List[str]] = Field(default=None, description="Sample values or enum options for categorical columns")

class Relationship(BaseModel):
    """表关系模型"""
    source_column: str = Field(description="Source column name in this table")
    target_table: str = Field(description="Target table name")
    target_column: str = Field(description="Target column name in target table")
    relation_type: str = Field("MANY_TO_ONE", description="Relationship type: MANY_TO_ONE, ONE_TO_MANY, ONE_TO_ONE")

class TableSchema(BaseModel):
    """表结构模型"""
    name: str = Field(description="Table name")
    comment: Optional[str] = Field(None, description="Table description")
    columns: List[ColumnSchema] = Field(default_factory=list, description="List of columns")
    relationships: List[Relationship] = Field(default_factory=list, description="List of foreign key relationships")

class SchemaMetadata(BaseModel):
    """数据库 Schema 元数据"""
    tables: List[TableSchema] = Field(default_factory=list, description="List of all tables in the schema")
    database_name: str = Field(description="Database name")
