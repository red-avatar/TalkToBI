"""
功能：关系推断Prompt模板 (Relationship Inference Prompts)
说明:
    定义LLM关系推断所需的Prompt模板。
    
    设计原则:
    1. 精简输入：只传必要的表/列信息
    2. 明确输出格式：使用JSON Schema
    3. 推断规则清晰：命名规范 + 类型匹配
    4. 支持分批：单次处理10-15个表

Author: CYJ
Time: 2025-12-03
"""

# ============================================================================
# 系统提示词
# ============================================================================

SYSTEM_PROMPT = """你是一个专业的数据库关系分析专家。你的任务是分析数据库表结构，推断表之间的关联关系。

你需要：
1. 分析表名和列名的语义含义
2. 识别外键列（通常为 xxx_id, xxx_code 格式）
3. 推断外键指向的目标表和目标列
4. 为每个关系提供置信度和简短描述

推断规则:
- xxx_id 列通常指向 xxx 或 xxxs 表的 id 列
- xxx_code 列通常指向 dim_xxx 表的 xxx_code 或 code 列
- shipping_xxx_id 通常指向 dim_xxx 表
- 列注释可能包含关系信息
- 类型必须兼容（bigint 对 bigint, varchar 对 varchar）

输出要求:
- 只输出确定度较高的关系（confidence >= 0.7）
- 避免重复关系（A->B 和 B->A 只输出一个）
- 自关联关系也要识别（如 categories.parent_id -> categories.id）""

# ============================================================================
# 用户提示词模板
# ============================================================================

INFERENCE_PROMPT_TEMPLATE = """## 任务
分析以下数据库表结构，推断表之间的关联关系。

## 表结构
{tables_json}

## 输出要求
1. 分析每个表的列，识别可能的外键列
2. 推断每个外键指向的目标表和目标列
3. 为每个关系设置：
   - source: 源表名
   - target: 目标表名
   - condition: JOIN条件，格式为 "source_table.column = target_table.column"
   - confidence: 置信度(0.7-1.0)
   - join_type: "FOREIGN_KEY" (外键) 或 "LOGICAL" (逻辑关联)
   - description: 简短的英文描述

## 示例
输入: orders (id, user_id, shop_id), users (id, name)
输出关系: 
- source: "orders", target: "users", condition: "orders.user_id = users.id"

请分析并输出所有可能的关系。"""

# ============================================================================
# 简化版提示词（用于大表场景，减少Token）
# ============================================================================

SIMPLIFIED_INFERENCE_PROMPT = """分析以下表的外键关系。

{tables_json}

只关注 *_id 和 *_code 列，推断它们指向哪个表。
输出关系列表。"""

# ============================================================================
# 验证提示词（用于验证推断结果）
# ============================================================================

VALIDATION_PROMPT_TEMPLATE = """## 任务
验证以下推断的关系是否合理。

## 推断的关系
{relationships_json}

## 表结构
{tables_json}

## 验证要点
1. 源表和目标表是否都存在
2. 源列和目标列是否存在
3. 列类型是否兼容
4. 关系是否合理（语义上）

请标记每个关系的验证结果：valid/invalid，并说明原因。""

# ============================================================================
# 辅助函数
# ============================================================================

def build_inference_prompt(tables_json: str) -> str:
    """
    构建推断提示词
    
    Args:
        tables_json: 表结构JSON字符串
        
    Returns:
        完整的用户提示词
        
    Author: CYJ
    Time: 2025-12-03
    """
    return INFERENCE_PROMPT_TEMPLATE.format(tables_json=tables_json)

def build_simplified_prompt(tables_json: str) -> str:
    """
    构建简化版提示词（大表场景）
    
    Args:
        tables_json: 表结构JSON字符串
        
    Returns:
        简化的用户提示词
        
    Author: CYJ
    Time: 2025-12-03
    """
    return SIMPLIFIED_INFERENCE_PROMPT.format(tables_json=tables_json)

def build_validation_prompt(relationships_json: str, tables_json: str) -> str:
    """
    构建验证提示词
    
    Args:
        relationships_json: 待验证的关系JSON
        tables_json: 表结构JSON
        
    Returns:
        验证提示词
        
    Author: CYJ
    Time: 2025-12-03
    """
    return VALIDATION_PROMPT_TEMPLATE.format(
        relationships_json=relationships_json,
        tables_json=tables_json
    )
