"""
关联路径意图验证器 (Path Intent Validator)

功能：
    当存在多条路径到同一目标表时，根据用户的业务意图选择正确的路径。
    
    使用 LLM + Few-shot 方式推断最佳路径，不依赖硬编码规则。
    关系描述中包含业务语义，LLM 可以根据描述理解并选择。

Author: CYJ
Time: 2025-12-04 (重构：去掉硬编码规则，改用 Few-shot)
"""

import json
import os
import logging
import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field
from app.core.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


@dataclass
class PathRecommendation:
    """路径推荐结果"""
    target_table: str
    recommended_path: List[str]
    recommended_condition: str
    alternative_paths: List[Dict]
    reason: str
    confidence: float


@dataclass
class PathValidationResult:
    """路径验证结果"""
    is_valid: bool
    has_alternatives: bool
    recommendations: List[PathRecommendation] = field(default_factory=list)
    join_hints: Dict[str, str] = field(default_factory=dict)
    warning: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "has_alternatives": self.has_alternatives,
            "recommendations": [
                {
                    "target_table": r.target_table,
                    "recommended_path": r.recommended_path,
                    "recommended_condition": r.recommended_condition,
                    "reason": r.reason,
                    "confidence": r.confidence
                }
                for r in self.recommendations
            ],
            "join_hints": self.join_hints,
            "warning": self.warning
        }


# Few-shot 示例：帮助 LLM 理解如何选择路径
PATH_SELECTION_EXAMPLES = """
### 示例 1
用户查询: "各省份销售额是多少"
可选路径:
- 路径1: orders → dim_region (条件: orders.shipping_region_id = dim_region.id, 描述: 订单收货地址所在地区(买家地区)。用于：各地区销售额、订单地区分布等)
- 路径2: orders → shops → dim_region (条件: shops.region_id = dim_region.id, 描述: 店铺/卖家所在地区)
正确选择: 路径1
原因: "省份销售额"指的是买家所在省份的销售额，应该用订单收货地址。路径2是卖家/店铺省份，不符合意图。

### 示例 2
用户查询: "各省份店铺数量"
可选路径:
- 路径1: shops → dim_region (条件: shops.region_id = dim_region.id, 描述: 店铺/卖家所在地区)
- 路径2: orders → dim_region (条件: orders.shipping_region_id = dim_region.id, 描述: 订单收货地址所在地区)
正确选择: 路径1
原因: "省份店铺数量"指的是店铺所在省份，应该用店铺表关联地区。

### 示例 3
用户查询: "各渠道新用户数"
可选路径:
- 路径1: users → dim_channel (条件: users.register_channel_code = dim_channel.channel_code, 描述: 用户注册渠道)
- 路径2: orders → dim_channel (条件: orders.order_channel_code = dim_channel.channel_code, 描述: 订单来源渠道)
正确选择: 路径1
原因: "新用户数"是统计用户注册，应该用用户注册渠道，不是订单渠道。

### 示例 4
用户查询: "各渠道销售额"
可选路径:
- 路径1: orders → dim_channel (条件: orders.order_channel_code = dim_channel.channel_code, 描述: 订单来源渠道)
- 路径2: users → dim_channel (条件: users.register_channel_code = dim_channel.channel_code, 描述: 用户注册渠道)
正确选择: 路径1
原因: "销售额"来自订单，应该用订单来源渠道，不是用户注册渠道。
"""


class PathIntentValidator:
    """
    关联路径意图验证器
    
    核心功能：
    1. 加载知识图谱中的所有关系(包含业务描述)
    2. 找出所有可能的关联路径
    3. 使用 LLM + Few-shot 推断最符合业务意图的路径
    
    Author: CYJ
    Time: 2025-12-04
    """
    
    def __init__(self):
        from app.core.config import get_settings
        self._settings = get_settings()
        self.relationships = self._load_relationships()
        self.llm = get_llm(temperature=self._settings.LLM_TEMPERATURE_PRECISE)
    
    def _load_relationships(self) -> List[Dict]:
        """加载知识图谱关系数据"""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        json_path = os.path.join(base_path, "scripts", "phase2_knowledge_base", "data", "relationships_enhanced.json")
        
        if not os.path.exists(json_path):
            logger.warning(f"[PathIntentValidator] Relationships file not found: {json_path}")
            return []
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[PathIntentValidator] Failed to load relationships: {e}")
            return []
    
    def _find_all_paths_to_table(self, 
                                  source_tables: Set[str], 
                                  target_table: str,
                                  max_depth: int = 3) -> List[Dict]:
        """
        找出从源表集合到目标表的所有可能路径
        
        Args:
            source_tables: 已召回的表集合
            target_table: 目标表（如 dim_region）
            max_depth: 最大搜索深度
            
        Returns:
            所有可能的路径列表
        """
        # 构建邻接表
        adj = {}
        for r in self.relationships:
            s, t = r['source'], r['target']
            if s not in adj:
                adj[s] = []
            if t not in adj:
                adj[t] = []
            adj[s].append((t, r['properties']))
            adj[t].append((s, r['properties']))  # 双向
        
        all_paths = []
        
        # 从每个源表 BFS 找路径
        for start in source_tables:
            if start == target_table:
                # 直接关联
                for r in self.relationships:
                    if (r['source'] == start and r['target'] == target_table) or \
                       (r['target'] == start and r['source'] == target_table):
                        all_paths.append({
                            "path": [start, target_table],
                            "condition": r['properties'].get('condition', ''),
                            "description": r['properties'].get('description', ''),
                            "hops": 1
                        })
                continue
            
            # BFS 搜索
            queue = [([start], [])]  # (path, conditions)
            visited = {start}
            
            while queue:
                path, conditions = queue.pop(0)
                current = path[-1]
                
                if len(path) > max_depth:
                    continue
                
                if current not in adj:
                    continue
                
                for neighbor, props in adj[current]:
                    if neighbor == target_table:
                        # 找到路径
                        full_path = path + [target_table]
                        all_paths.append({
                            "path": full_path,
                            "condition": props.get('condition', ''),
                            "description": props.get('description', ''),
                            "hops": len(full_path) - 1,
                            "intermediate_conditions": conditions + [props.get('condition', '')]
                        })
                    elif neighbor not in visited and len(path) < max_depth:
                        visited.add(neighbor)
                        queue.append((path + [neighbor], conditions + [props.get('condition', '')]))
        
        return all_paths
    
    def validate(self, 
                 user_query: str, 
                 selected_tables: List[str],
                 target_tables: Optional[List[str]] = None) -> PathValidationResult:
        """
        验证召回表的关联路径是否符合业务意图
        
        使用 LLM + Few-shot 方式推断最佳路径，不依赖硬编码规则。
        
        Args:
            user_query: 用户原始查询
            selected_tables: 召回的表清单
            target_tables: 需要重点验证的目标表（如维度表）
            
        Returns:
            验证结果，包含推荐的路径
            
        Author: CYJ
        Time: 2025-12-04
        """
        logger.info(f"[PathIntentValidator] Validating paths for tables: {selected_tables}")
        
        # 默认验证维度表
        if target_tables is None:
            target_tables = ["dim_region", "dim_channel", "dim_date"]
        
        source_tables = set(selected_tables)
        recommendations = []
        join_hints = {}
        has_alternatives = False
        warning = None
        
        for target in target_tables:
            if target not in source_tables:
                continue
            
            # 找出所有可能的路径
            all_paths = self._find_all_paths_to_table(source_tables - {target}, target)
            
            if not all_paths:
                continue
            
            logger.info(f"[PathIntentValidator] Found {len(all_paths)} paths to '{target}'")
            for p in all_paths:
                logger.info(f"  - {' → '.join(p['path'])}: {p['condition']} ({p.get('description', '')})")
            
            if len(all_paths) == 1:
                # 只有一条路径，直接使用
                p = all_paths[0]
                rec = PathRecommendation(
                    target_table=target,
                    recommended_path=p['path'],
                    recommended_condition=p['condition'],
                    alternative_paths=[],
                    reason="唯一可用路径",
                    confidence=1.0
                )
                recommendations.append(rec)
                join_hints[f"{p['path'][0]}_{target}"] = p['condition']
            else:
                # 多条路径，使用 LLM + Few-shot 选择
                has_alternatives = True
                llm_recommendation = self._llm_select_path(user_query, target, all_paths)
                if llm_recommendation:
                    recommendations.append(llm_recommendation)
                    join_hints[f"{llm_recommendation.recommended_path[0]}_{target}"] = llm_recommendation.recommended_condition
                    warning = f"注意：到 {target} 存在多条路径，系统已根据业务意图选择最优路径"
        
        return PathValidationResult(
            is_valid=len(recommendations) > 0 or not has_alternatives,
            has_alternatives=has_alternatives,
            recommendations=recommendations,
            join_hints=join_hints,
            warning=warning
        )
    
    def _llm_select_path(self, 
                         user_query: str, 
                         target_table: str, 
                         paths: List[Dict]) -> Optional[PathRecommendation]:
        """
        使用 LLM 选择最合适的路径
        
        Args:
            user_query: 用户查询
            target_table: 目标表
            paths: 可选路径列表
            
        Returns:
            推荐的路径
        """
        try:
            paths_desc = "\n".join([
                f"路径{i+1}: {' → '.join(p['path'])} (条件: {p['condition']}, 说明: {p.get('description', '')})"
                for i, p in enumerate(paths)
            ])
            
            prompt = ChatPromptTemplate.from_template("""
你是一个电商数据分析专家。用户提出了一个数据查询需求，现在需要你判断应该使用哪条关联路径。

【参考示例】
{examples}

【当前查询】
用户查询: {user_query}
目标表: {target_table}

【可选路径】
{paths_desc}

【任务】
请根据用户的业务意图和上面的参考示例，选择最合适的路径。

返回格式（严格遵循）：
路径编号: <1或2或...>
原因: <简短说明>
""")
            
            chain = prompt | self.llm
            response = chain.invoke({
                "examples": PATH_SELECTION_EXAMPLES,
                "user_query": user_query,
                "target_table": target_table,
                "paths_desc": paths_desc
            })
            
            # 解析响应
            content = response.content
            path_idx = 0
            reason = ""
            
            for line in content.split('\n'):
                if '路径编号' in line or '路径' in line:
                    # 提取数字
                    nums = re.findall(r'\d+', line)
                    if nums:
                        path_idx = int(nums[0]) - 1
                elif '原因' in line:
                    reason = line.split(':', 1)[-1].strip() if ':' in line else line
            
            if 0 <= path_idx < len(paths):
                selected = paths[path_idx]
                return PathRecommendation(
                    target_table=target_table,
                    recommended_path=selected['path'],
                    recommended_condition=selected['condition'],
                    alternative_paths=[p for i, p in enumerate(paths) if i != path_idx],
                    reason=reason or "LLM 推荐",
                    confidence=0.8
                )
                
        except Exception as e:
            logger.error(f"[PathIntentValidator] LLM selection failed: {e}")
        
        return None
    
    def get_join_hints_for_planner(self, 
                                    user_query: str, 
                                    selected_tables: List[str]) -> str:
        """
        获取给 SQL Planner 的 JOIN 提示
        
        Args:
            user_query: 用户查询
            selected_tables: 召回的表
            
        Returns:
            JOIN 提示字符串，可直接附加到 Schema Context
        """
        result = self.validate(user_query, selected_tables)
        
        if not result.recommendations:
            return ""
        
        hints = ["\n[🔗 JOIN PATH RECOMMENDATION - 关联路径推荐]"]
        hints.append("系统检测到存在多条关联路径，以下是根据业务意图推荐的路径：")
        
        for rec in result.recommendations:
            hints.append(f"\n目标表: {rec.target_table}")
            hints.append(f"推荐路径: {' → '.join(rec.recommended_path)}")
            hints.append(f"推荐条件: {rec.recommended_condition}")
            hints.append(f"原因: {rec.reason}")
            
            if rec.alternative_paths:
                hints.append(f"⚠️ 备选路径（不推荐）:")
                for alt in rec.alternative_paths[:2]:  # 最多显示2个备选
                    hints.append(f"  - {' → '.join(alt['path'])}: {alt['condition']}")
        
        hints.append("\n【重要】请使用推荐的 JOIN 条件，不要使用备选路径！")
        
        return "\n".join(hints)


# 单例
_path_intent_validator = None

def get_path_intent_validator() -> PathIntentValidator:
    """获取 PathIntentValidator 单例"""
    global _path_intent_validator
    if _path_intent_validator is None:
        _path_intent_validator = PathIntentValidator()
    return _path_intent_validator
