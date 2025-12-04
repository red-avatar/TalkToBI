"""
功能：智能探针 (Intelligent Probe)
说明：
    CoT思维链驱动的探针机制，用于验证SQL中的实体值是否与数据库实际值匹配
    
    核心流程：
    1. [分析] 从智能诊断器获取可疑实体列表
    2. [推理] 基于DDL注释推断可能的正确值变体
    3. [生成] 为每个可疑实体生成探针SQL
    4. [执行] 查询数据库获取实际值
    5. [结论] 输出映射关系和证据链

Author: CYJ
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.core.llm import get_llm
from app.modules.tools.execution import SqlExecutorTool
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """单个实体的探针结果"""
    entity_key: str  # 实体标识 (table.column)
    original_value: Any  # 用户输入的原始值
    found_values: List[str]  # 数据库中找到的实际值
    matched: bool  # 是否找到匹配
    mapping: Optional[str] = None  # 映射后的值 (如果找到)
    probe_sql: str = ""  # 执行的探针SQL
    evidence: List[str] = field(default_factory=list)  # 证据链


@dataclass
class IntelligentProbeResult:
    """智能探针综合结果"""
    success: bool  # 探针是否成功
    probe_results: List[ProbeResult] = field(default_factory=list)  # 各实体探针结果
    entity_mappings: Dict[str, str] = field(default_factory=dict)  # 发现的映射关系
    evidence_chain: List[str] = field(default_factory=list)  # 完整证据链
    suggestion: str = ""  # 修复建议


class IntelligentProbe:
    """
    智能探针
    
    核心特性：
    1. 基于智能诊断器的可疑实体列表执行探针
    2. CoT思维链输出完整证据
    3. 利用DDL推理可能的值变体
    4. 结果写入跨轮缓存
    
    Author: CYJ
    """
    
    def __init__(self):
        """初始化智能探针"""
        from app.core.config import get_settings
        self._settings = get_settings()
        self.llm = get_llm(temperature=self._settings.LLM_TEMPERATURE_PRECISE)
        self.sql_executor = SqlExecutorTool()
    
    async def probe(self,
                    suspicious_entities: List[Dict[str, Any]],
                    schema_ddl: str = "",
                    verified_mappings: Dict[str, str] = None) -> IntelligentProbeResult:
        """
        执行智能探针
        
        Args:
            suspicious_entities: 可疑实体列表 (来自智能诊断器)
            schema_ddl: Schema DDL (用于推理)
            verified_mappings: 已验证的映射缓存
            
        Returns:
            IntelligentProbeResult: 探针结果
            
        Author: CYJ
        """
        verified_mappings = verified_mappings or {}
        
        if not suspicious_entities:
            logger.info("[IntelligentProbe] 无可疑实体需要探针")
            return IntelligentProbeResult(
                success=True,
                evidence_chain=["无可疑实体需要探针验证"]
            )
        
        logger.info(f"[IntelligentProbe] 开始探针验证 {len(suspicious_entities)} 个可疑实体")
        
        probe_results = []
        new_mappings = {}
        evidence_chain = []
        
        for entity in suspicious_entities:
            # 跳过已缓存的映射
            original_value = entity.get("value", "")
            if isinstance(original_value, list):
                original_value_str = str(original_value[0]) if original_value else ""
            else:
                original_value_str = str(original_value)
                
            if original_value_str in verified_mappings:
                logger.info(f"[IntelligentProbe] 跳过已缓存: {original_value_str} -> {verified_mappings[original_value_str]}")
                evidence_chain.append(f"跳过已缓存映射: {original_value_str} -> {verified_mappings[original_value_str]}")
                continue
            
            # 执行探针
            result = await self._probe_entity(entity, schema_ddl)
            probe_results.append(result)
            
            # 记录证据
            evidence_chain.extend(result.evidence)
            
            # 收集新映射
            if result.matched and result.mapping:
                if isinstance(original_value, list):
                    for ov in original_value:
                        new_mappings[str(ov)] = result.mapping
                else:
                    new_mappings[original_value_str] = result.mapping
                logger.info(f"[IntelligentProbe] 发现映射: {original_value} -> {result.mapping}")
        
        # 汇总结果
        success = any(r.matched for r in probe_results) if probe_results else True
        
        return IntelligentProbeResult(
            success=success,
            probe_results=probe_results,
            entity_mappings=new_mappings,
            evidence_chain=evidence_chain,
            suggestion=self._generate_suggestion(probe_results) if probe_results else ""
        )
    
    async def _probe_entity(self, entity: Dict[str, Any], schema_ddl: str) -> ProbeResult:
        """
        对单个实体执行探针
        
        Args:
            entity: 可疑实体信息
            schema_ddl: Schema DDL
            
        Returns:
            ProbeResult: 探针结果
            
        Author: CYJ
        """
        table = entity.get("table", "")
        column = entity.get("column", "")
        value = entity.get("value", "")
        possible_values = entity.get("possible_values", [])
        probe_sql = entity.get("probe_sql", "")
        
        evidence = []
        entity_key = f"{table}.{column}"
        
        # 如果诊断器没有生成探针SQL，自己生成
        if not probe_sql:
            probe_sql = await self._generate_probe_sql(table, column, value, possible_values, schema_ddl)
        
        evidence.append(f"[探针] 实体: {entity_key}, 原值: {value}")
        evidence.append(f"[探针] SQL: {probe_sql}")
        
        # 执行探针SQL
        try:
            result_str = self.sql_executor.invoke(probe_sql)
            evidence.append(f"[探针] 结果: {result_str[:200] if result_str else 'Empty'}")
            
            if result_str and not result_str.startswith("ERROR:") and result_str != "[]":
                # 解析结果
                found_values = self._parse_probe_result(result_str, column)
                
                if found_values:
                    # 找到匹配
                    best_match = self._find_best_match(value, found_values)
                    evidence.append(f"[探针] 找到 {len(found_values)} 个候选值")
                    evidence.append(f"[探针] 最佳匹配: {best_match}")
                    
                    return ProbeResult(
                        entity_key=entity_key,
                        original_value=value,
                        found_values=found_values,
                        matched=True,
                        mapping=best_match,
                        probe_sql=probe_sql,
                        evidence=evidence
                    )
            
            # 没找到匹配
            evidence.append(f"[探针] 未找到匹配值")
            return ProbeResult(
                entity_key=entity_key,
                original_value=value,
                found_values=[],
                matched=False,
                probe_sql=probe_sql,
                evidence=evidence
            )
            
        except Exception as e:
            logger.error(f"[IntelligentProbe] 探针执行失败: {e}")
            evidence.append(f"[探针] 执行失败: {str(e)}")
            return ProbeResult(
                entity_key=entity_key,
                original_value=value,
                found_values=[],
                matched=False,
                probe_sql=probe_sql,
                evidence=evidence
            )
    
    async def _generate_probe_sql(self,
                                   table: str,
                                   column: str,
                                   value: Any,
                                   possible_values: List[str],
                                   schema_ddl: str) -> str:
        """
        生成探针SQL
        
        基于CoT推理生成覆盖多种变体的探针SQL
        
        Author: CYJ
        """
        # 处理列表值
        if isinstance(value, list):
            value_str = value[0] if value else ""
        else:
            value_str = str(value)
        
        # 构建LIKE条件
        like_conditions = [f"{column} LIKE '%{value_str}%'"]
        
        # 添加可能的变体
        for pv in possible_values[:5]:  # 限制数量
            like_conditions.append(f"{column} LIKE '%{pv}%'")
        
        # 常见中英文变体推理
        chinese_hints = {
            '微信': ['wechat', 'weixin'],
            '支付宝': ['alipay'],
            '自营': ['self', 'direct'],
            '第三方': ['third_party', 'partner'],
            '一线': ['tier1', 'first'],
            '二线': ['tier2', 'second'],
            '成功': ['success', 'completed'],
            '失败': ['failed', 'failure'],
            '顺丰': ['sf', 'shunfeng'],
            '中通': ['zto', 'zhongtong'],
            '京东': ['jd', 'jingdong'],
        }
        
        for ch, en_list in chinese_hints.items():
            if ch in value_str:
                for en in en_list:
                    like_conditions.append(f"{column} LIKE '%{en}%'")
        
        # 去重
        like_conditions = list(set(like_conditions))
        
        # 生成SQL
        where_clause = " OR ".join(like_conditions)
        probe_sql = f"SELECT DISTINCT {column} FROM {table} WHERE {where_clause} LIMIT 10;"
        
        return probe_sql
    
    def _parse_probe_result(self, result_str: str, column: str) -> List[str]:
        """
        解析探针查询结果
        
        Time: 2025-11-26
        """
        try:
            import ast
            result_list = ast.literal_eval(result_str)
            
            values = []
            for item in result_list:
                if isinstance(item, dict):
                    # 取字段值
                    for k, v in item.items():
                        if v and str(v) not in values:
                            values.append(str(v))
            
            return values
            
        except Exception as e:
            logger.warning(f"[IntelligentProbe] 解析探针结果失败: {e}")
            return []
    
    def _find_best_match(self, original_value: Any, found_values: List[str]) -> Optional[str]:
        """
        从探针结果中找到最佳匹配
        
        匹配策略：
        1. 完全匹配
        2. 包含匹配
        3. 相似度匹配
        
        Author: CYJ
        """
        if not found_values:
            return None
        
        # 处理列表值
        if isinstance(original_value, list):
            original_str = str(original_value[0]).lower() if original_value else ""
        else:
            original_str = str(original_value).lower()
        
        # 1. 完全匹配
        for fv in found_values:
            if fv.lower() == original_str:
                return fv
        
        # 2. 包含匹配
        for fv in found_values:
            if original_str in fv.lower() or fv.lower() in original_str:
                return fv
        
        # 3. 返回第一个（最可能的）
        return found_values[0] if found_values else None
    
    def _generate_suggestion(self, probe_results: List[ProbeResult]) -> str:
        """
        生成修复建议
        
        Author: CYJ
        """
        successful = [r for r in probe_results if r.matched]
        failed = [r for r in probe_results if not r.matched]
        
        suggestions = []
        
        if successful:
            mappings = [f"{r.original_value} → {r.mapping}" for r in successful]
            suggestions.append(f"发现映射: {', '.join(mappings)}")
        
        if failed:
            failed_values = [str(r.original_value) for r in failed]
            suggestions.append(f"未找到匹配: {', '.join(failed_values)}，数据可能确实不存在")
        
        return "; ".join(suggestions)


# 单例实例
_intelligent_probe = None

def get_intelligent_probe() -> IntelligentProbe:
    """获取智能探针单例"""
    global _intelligent_probe
    if _intelligent_probe is None:
        _intelligent_probe = IntelligentProbe()
    return _intelligent_probe
