"""
功能：诊断模块 - 数据模型定义
说明：
    定义诊断结果、Schema检查结果等数据模型
    
Author: CYJ
"""
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


class DiagnosisType(Enum):
    """
    诊断结果类型
    
    Author: CYJ
    """
    ENTITY_MAPPING = "entity_mapping"       # 实体值映射问题（如 家电≠家用电器）
    SCHEMA_INCOMPLETE = "schema_incomplete"  # Schema召回不全（缺少关联表）
    SQL_LOGIC_ERROR = "sql_logic_error"     # SQL逻辑错误（JOIN类型、聚合函数等）
    DATA_TRULY_EMPTY = "data_truly_empty"   # 数据确实为空（正确的0）
    UNKNOWN = "unknown"                      # 无法判断


class SuggestedAction(Enum):
    """
    建议的修复动作
    
    Author: CYJ
    """
    RECALL_MORE_TABLES = "recall_more_tables"  # 回到召回层，补充召回缺失的表
    REWRITE_SQL = "rewrite_sql"                # 重写SQL（提供修复建议）
    REGENERATE_SQL = "regenerate_sql"          # 重新生成SQL（表/列不存在等致命错误）
    PROBE_ENTITIES = "probe_entities"          # 执行探针查询验证实体值
    CONFIRM_EMPTY = "confirm_empty"            # 确认数据为空，告知用户


@dataclass
class SuggestedActionItem:
    """
    建议的修复动作项
    
    Author: CYJ
    """
    action_type: str  # add_table, rewrite_sql, probe_entity, etc.
    target: Optional[str] = None  # 目标（如表名、字段名）
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosisResult:
    """
    诊断结果
    
    Author: CYJ
    """
    diagnosis_type: DiagnosisType
    confidence: float  # 置信度 0-1
    root_cause: str = ""  # 根本原因描述
    evidence: List[str] = field(default_factory=list)  # 诊断依据
    suggested_action: SuggestedAction = SuggestedAction.CONFIRM_EMPTY
    suggested_actions: List[SuggestedActionItem] = field(default_factory=list)  # 建议的修复动作列表
    
    # 针对不同诊断类型的额外信息
    missing_tables: List[str] = field(default_factory=list)  # SCHEMA_INCOMPLETE时使用
    entities_to_probe: List[Dict[str, str]] = field(default_factory=list)  # ENTITY_MAPPING时使用
    sql_fix_suggestions: List[Dict[str, str]] = field(default_factory=list)  # SQL_LOGIC_ERROR时使用
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        Author: CYJ
        """
        return {
            "diagnosis_type": self.diagnosis_type.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action.value,
            "missing_tables": self.missing_tables,
            "entities_to_probe": self.entities_to_probe,
            "sql_fix_suggestions": self.sql_fix_suggestions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiagnosisResult":
        """
        从字典创建实例
        
        Author: CYJ
        """
        return cls(
            diagnosis_type=DiagnosisType(data.get("diagnosis_type", "unknown")),
            confidence=data.get("confidence", 0.0),
            evidence=data.get("evidence", []),
            suggested_action=SuggestedAction(data.get("suggested_action", "confirm_empty")),
            missing_tables=data.get("missing_tables", []),
            entities_to_probe=data.get("entities_to_probe", []),
            sql_fix_suggestions=data.get("sql_fix_suggestions", [])
        )


@dataclass
class SchemaCheckResult:
    """
    Schema完整性检查结果
    
    Author: CYJ
    """
    is_complete: bool
    missing_tables: List[str] = field(default_factory=list)
    missing_columns: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    
    # 外键关系详情
    fk_analysis: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class SQLLogicCheckResult:
    """
    SQL逻辑检查结果
    
    Author: CYJ
    """
    has_issues: bool
    issues: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class EntityMappingCheckResult:
    """
    实体映射检查结果
    
    Author: CYJ
    """
    has_mismatch: bool
    entities: List[Dict[str, str]] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class SchemaCompletionResult:
    """
    Schema补全结果
    
    Author: CYJ
    """
    success: bool
    added_tables: List[str] = field(default_factory=list)
    complete_ddl: str = ""
    error: str = ""
