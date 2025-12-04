"""
功能：关系推断数据模型 (Relationship Inference Schemas)
说明:
    定义LLM关系推断的Pydantic Schema，确保输出结构与现有JSON格式一致。
    
    现有JSON结构 (relationships_enhanced.json):
    {
      "source": "orders",
      "target": "users",
      "type": "JOIN_ON",
      "properties": {
        "condition": "orders.user_id = users.id",
        "confidence": 1.0,
        "join_type": "FOREIGN_KEY",
        "description": "Order user"
      }
    }
    
    使用方式:
    - RelationshipList 用于 LLM structured output
    - Relationship.model_dump() 输出与现有JSON 100% 一致

Author: CYJ
Time: 2025-12-03
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class RelationshipProperties(BaseModel):
    """
    关系属性 - 与现有JSON结构严格一致
    
    Author: CYJ
    Time: 2025-12-03
    """
    condition: str = Field(
        description="JOIN条件，格式: source.column = target.column，例如: orders.user_id = users.id"
    )
    confidence: float = Field(
        ge=0, 
        le=1, 
        default=0.9,
        description="置信度: 1.0=人工确认/物理FK, 0.x=LLM推断"
    )
    join_type: Literal["FOREIGN_KEY", "LOGICAL", "SEMANTIC"] = Field(
        default="FOREIGN_KEY",
        description="关系类型: FOREIGN_KEY=外键关系, LOGICAL=逻辑关联, SEMANTIC=语义关联"
    )
    description: str = Field(
        description="关系描述，英文，简洁说明关系含义，例如: Order belongs to user"
    )

class Relationship(BaseModel):
    """
    单个关系 - 与现有JSON结构完全一致
    
    这是LLM输出的基本单元，使用 model_dump() 后直接写入JSON文件。
    
    Author: CYJ
    Time: 2025-12-03
    """
    source: str = Field(
        description="源表名，必须是数据库中存在的表名"
    )
    target: str = Field(
        description="目标表名，必须是数据库中存在的表名"
    )
    type: Literal["JOIN_ON"] = Field(
        default="JOIN_ON",
        description="关系类型，固定为JOIN_ON"
    )
    properties: RelationshipProperties

class RelationshipList(BaseModel):
    """
    关系列表 - LLM structured output的目标类型
    
    使用方式:
        llm_with_structure = llm.with_structured_output(RelationshipList)
        result: RelationshipList = llm_with_structure.invoke(prompt)
        relations = [rel.model_dump() for rel in result.relationships]
    
    Author: CYJ
    Time: 2025-12-03
    """
    relationships: List[Relationship] = Field(
        description="推断出的关系列表"
    )

# ============================================================================
# 辅助数据结构
# ============================================================================

class TableInfo(BaseModel):
    """
    表信息 - 用于构建LLM输入
    
    Author: CYJ
    Time: 2025-12-03
    """
    name: str = Field(description="表名")
    comment: Optional[str] = Field(default=None, description="表注释")
    columns: List["ColumnInfo"] = Field(default_factory=list, description="列信息列表")

class ColumnInfo(BaseModel):
    """
    列信息 - 用于构建LLM输入
    
    只包含推断关系所需的字段，减少Token消耗。
    
    Author: CYJ
    Time: 2025-12-03
    """
    name: str = Field(description="列名")
    data_type: str = Field(description="数据类型")
    comment: Optional[str] = Field(default=None, description="列注释")
    is_primary_key: bool = Field(default=False, description="是否主键")
    is_foreign_key: bool = Field(default=False, description="是否外键")

class InferenceResult(BaseModel):
    """
    推断结果 - Agent返回的完整结果
    
    Author: CYJ
    Time: 2025-12-03
    """
    relationships: List[Relationship] = Field(description="推断出的关系")
    tables_analyzed: int = Field(description="分析的表数量")
    total_batches: int = Field(description="分批数量")
    success: bool = Field(default=True, description="是否成功")
    message: str = Field(default="", description="结果消息")

# 解决循环引用
TableInfo.model_rebuild()
