"""
诊断模块 (Diagnosis Module)

提供统一的诊断与验证机制（V4 重构后）：
- SchemaCompleter: Schema补全器，检测并补充缺失的关联表
- IntelligentAnalyzer: 统一智能诊断器（合并原 ResultDiagnoser）
- IntelligentProbe: 智能探针，CoT链式思维探测机制
- ResultValidator: 统一结果验证器（合并原 SemanticValidator）

Author: CYJ
Time: 2025-11-25 (V4: 2025-11-26 模块合并重构)
"""
from app.modules.diagnosis.models import (
    DiagnosisType,
    SuggestedAction,
    SuggestedActionItem,
    DiagnosisResult,
    SchemaCheckResult,
    SQLLogicCheckResult,
    EntityMappingCheckResult,
    SchemaCompletionResult
)
from app.modules.diagnosis.schema_completer import SchemaCompleter
from app.modules.diagnosis.intelligent_analyzer import (
    IntelligentAnalyzer,
    IntelligentDiagnosisResult,
    DiagnosisPhase,
    UnderstandingDiagnosis,
    SqlBuildingDiagnosis,
    get_intelligent_analyzer
)
from app.modules.diagnosis.intelligent_probe import (
    IntelligentProbe,
    IntelligentProbeResult,
    ProbeResult,
    get_intelligent_probe
)
from app.modules.diagnosis.result_validator import (
    ResultValidator,
    ResultValidationResult,
    get_result_validator
)

__all__ = [
    # 基础模型
    "DiagnosisType",
    "SuggestedAction",
    "SuggestedActionItem",
    "DiagnosisResult",
    "SchemaCheckResult",
    "SQLLogicCheckResult",
    "EntityMappingCheckResult",
    "SchemaCompletionResult",
    # Schema补全器
    "SchemaCompleter",
    # 统一智能诊断分析器
    "IntelligentAnalyzer",
    "IntelligentDiagnosisResult",
    "DiagnosisPhase",
    "UnderstandingDiagnosis",
    "SqlBuildingDiagnosis",
    "get_intelligent_analyzer",
    # 智能探针
    "IntelligentProbe",
    "IntelligentProbeResult",
    "ProbeResult",
    "get_intelligent_probe",
    # 统一结果验证器
    "ResultValidator",
    "ResultValidationResult",
    "get_result_validator"
]
