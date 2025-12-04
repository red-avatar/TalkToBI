"""
功能：意图识别 Agent (Intent Recognition)
说明：
    1. 接收用户输入，判断意图类型 (查询数据/闲聊/模糊)。
    2. 如果是查询数据，进行 Query Rewriting (问题改写)，消除指代歧义。
    3. 提取关键实体 (Entities)。
作者：CYJ
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from app.core.llm import get_llm
from app.core.config import get_settings
from app.core.state import AgentState, IntentSchema
from app.services.term_service import get_term_service
import json

_settings = get_settings()

# 1. 定义输出结构 (Pydantic)
class FilterCondition(BaseModel):
    """
    筛选条件结构
    
    用于明确告知SQL Agent哪些条件必须出现在WHERE子句中
    
    Author: CYJ
    """
    field_hint: str = Field(description="字段类型提示，如 'coupon_type', 'category', 'city', 'pay_method'")
    value: str = Field(description="用户提到的筛选值，如 '折扣券', '服饰鞋包', '微信支付'")
    operator: str = Field(default="=", description="操作符: '=', 'IN', 'LIKE', '>', '<', 'BETWEEN'")
    required: bool = Field(default=True, description="是否必须出现在WHERE子句中")


class IntentOutput(BaseModel):
    intent_type: str = Field(description="Intent type: 'query_data', 'chitchat', 'unclear', 'rejection'")
    rewritten_query: Optional[str] = Field(description="The rewritten query, self-contained and unambiguous. Resolve 'it', 'last month', etc.")
    # V13: 新增 - 是否可以基于历史数据直接回答（query_data 的变体分支）
    # Author: CYJ
    # Time: 2025-11-27
    can_answer_from_history: bool = Field(
        default=False,
        description="仅当 intent_type='query_data' 时有效。如果用户的问题可以完全基于历史查询结果中的数据回答（如计算差值、比例、排名等），设为 true；如果需要查询新数据，设为 false"
    )
    history_answer_reason: Optional[str] = Field(
        default=None,
        description="当 can_answer_from_history=true 时，说明为什么可以基于历史数据回答，以及需要计算什么"
    )
    entities: dict = Field(description="Extracted entities like {'city': 'Hangzhou', 'product': 'iPhone'}")
    # V2: 新增结构化筛选条件 - 明确告知SQL Agent哪些条件必须转为WHERE
    filter_conditions: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        description="结构化筛选条件列表，每个条件必须在SQL的WHERE子句中体现"
    )
    reason: str = Field(description="Reasoning for the classification")
    guidance: Optional[str] = Field(description="Guidance for user if rejection or unclear")
    detected_keywords: Optional[List[str]] = Field(description="List of potential keywords detected in the query, even if intent is unclear")
    # 当模型对改写结果存在主观推断或信息不完整时，应要求用户先确认
    need_user_confirmation: bool = Field(
        default=False,
        description="Whether the rewritten_query must be confirmed by the user before executing SQL",
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="If need_user_confirmation is true, the natural language question to ask the user",
    )
    # V14: 新增查询需求结构化提取 - 用于语义完整性验证
    # Author: CYJ
    query_requirements: Optional[Dict[str, Any]] = Field(
        default={},
        description="查询需求结构化提取，包含排序、限制、分组、指标等要求"
    )

# 2. 定义 Prompt
INTENT_PROMPT = """你是商业智能(BI)系统的意图识别专家。
你的任务是分析用户输入和对话历史，判断用户的意图，并在需要时给出改写建议和澄清问题。

### 意图分类 (Intent Categories):
1. query_data: 用户正在索要具体的业务数据、统计指标或报表。
   - 即使包含口语化填充词（"那个...额..."、"帮我查下"），只要核心是查数据，都视为 query_data。
2. chitchat: 闲聊、问候或与业务无关的对话。
3. unclear: 请求过于模糊，信息不足以生成 SQL 或给出可靠改写。
4. rejection: 逻辑上不可行或超出系统能力范围（如查询未来、明显不存在的星球数据等）。

{business_terms_section}

### 任务 (Task):
1. 思考 (Thinking):
   - 分析用户输入的句子成分：主体(实体)、动作、时间、过滤条件等。
   - 过滤无意义口语废话 (如 "那个", "额", "帮我看看", "我要看下" 等)。
2. 可行性检查 (Feasibility Check):
   - 如果涉及未来时间、明显不存在的实体（如"火星分公司"），则应判定为 rejection，并给出 reason 和 guidance。
3. 意图分类: 判断属于上述哪一类 intent_type。
4. 改写问题 (Rewrite):
   - 仅当 intent_type 为 query_data 时尝试生成 rewritten_query。
   - 改写后的句子必须独立、完整、无指代歧义。
   - 对口语噪音进行清洗（如 "帮我看看那个...额...杭州的单子" -> "查询收货地址为杭州的订单列表"）。
   - 对代词进行解析（如 在历史中已提到用户ID=1 时，"那他的退款次数呢" -> "查询用户ID为1的退款次数"）。
5. 实体提取 (Entities):
   - 提取城市、用户ID、时间范围、指标类型（销售额、订单数、退款额、退款次数等）。
6. 【核心】筛选条件提取 (Filter Conditions) - 必须完整提取！:
   - 仔细分析用户提问，提取所有筛选/过滤条件
   - 每个筛选条件都必须记录到 filter_conditions 列表中
   - 筛选条件包括但不限于：
     * 类型筛选：优惠券类型(满减券/折扣券)、店铺类型(自营/第三方)、支付方式(微信/支付宝)
     * 状态筛选：订单状态、支付状态、退款状态
     * 维度筛选：城市、品类、品牌、渠道、物流商
     * 时间筛选：日期范围、年月
   
   ❗❗❗ 【关键 - 对比类查询必须提取所有值】 ❗❗❗
   当用户提问中包含"和"、"VS"、"对比"、"与"等表示多个值时，必须将每个值都提取出来！
   - "一线和二线城市" → 必须提取两个条件: city_level=一线 + city_level=二线
   - "自营与第三方店铺" → 必须提取两个条件: shop_type=自营 + shop_type=第三方
   - "顺丰或中通配送" → 必须提取两个条件: logistics=顺丰 + logistics=中通
   - "苹果、华为、小米" → 必须提取三个条件: brand=苹果 + brand=华为 + brand=小米
   
   格式说明:
   - 单值条件: {{"field_hint": "字段", "value": "单个值", "operator": "=", "required": true}}
   - 多值对比: {{"field_hint": "字段", "value": ["值1", "值2"], "operator": "IN", "required": true}}
   
   基础示例:
     * "使用折扣券购买" → {{"field_hint": "coupon_type", "value": "折扣券", "operator": "=", "required": true}}
     * "在自营店铺" → {{"field_hint": "shop_type", "value": "自营", "operator": "=", "required": true}}
     * "通过微信支付" → {{"field_hint": "pay_method", "value": "微信", "operator": "=", "required": true}}
     * "服饰鞋包类商品" → {{"field_hint": "category", "value": "服饰鞋包", "operator": "=", "required": true}}
7. 关键词提取 (Keyword Extraction):
   - 即使最终判定为 unclear，也要尽量给出 detected_keywords，帮助后续做澄清询问。
8. 用户确认 (need_user_confirmation):
   - 当你在改写中填充了用户未明确给出的条件（例如时间范围、城市），或者对"他/那个"这类指代做了主观推断时，必须将 need_user_confirmation 设为 true。
   - 此时填写 clarification_question，向用户自然语言询问，例如：
     - "我理解为您想查看最近一段时间的退款订单列表，对吗？如果有具体时间范围也可以告诉我。"
   - 只有当用户在下一轮明确确认后，系统才会使用该改写去生成 SQL。

### 示例 (行为示意，无需逐字复制):
- 输入："那个...额...查一下低单表数据"
  - intent_type: query_data
  - rewritten_query: "查询订单表数据" (纠正错别字：低单->订单)
  - need_user_confirmation: true
  - clarification_question: "我推测您想查询'订单表'的数据，对吗？请问具体需要查询哪些指标（如金额、数量）？"

- 输入："看看肖米的销量"
  - intent_type: query_data
  - rewritten_query: "查询小米品牌的销量" (纠正错别字：肖米->小米)
  - need_user_confirmation: true

- 输入："那个...额...我要看下退款的单子"
  - intent_type: query_data
  - rewritten_query: 例如 "查询最近一段时间的退款订单列表"
  - need_user_confirmation: true（因为时间范围并未被用户显式指定）
  - clarification_question: 提示用户确认是否需要按某个时间范围或全部退款记录。

- 输入："查询2024年1月1日后的订单总金额"
  - intent_type: query_data
  - rewritten_query: "查询2024年1月1日后的订单总金额"
  - need_user_confirmation: false（用户已给出清晰时间和指标）

- 输入："查询杭州的用户数量"
  - intent_type: query_data
  - rewritten_query: "查询所在城市为杭州的用户数量"
  - need_user_confirmation: false

- 输入："查询冥王星分公司的退款额"
  - intent_type: rejection
  - reason: 数据库中不存在该分公司
  - guidance: 告诉用户当前有哪些真实存在的城市或分公司可选。

- 上下文中上一轮用户已问： "查询用户ID为888的订单总金额"，当前输入: "那他的退款次数呢？"
  - intent_type: query_data
  - rewritten_query: "查询用户ID为888的退款次数"
  - need_user_confirmation: false

- 上下文中 AI 已问："我理解为您想查询杭州的订单，对吗？"，当前输入："是的"
  - intent_type: query_data
  - rewritten_query: "查询收货地址为杭州的订单列表" (根据上下文补全)
  - need_user_confirmation: false

- 输入："使用折扣券购买服饰鞋包类商品的各城市订单数"
  - intent_type: query_data
  - rewritten_query: "统计使用折扣券购买服饰鞋包类商品的各城市订单数量"
  - entities: {{"category": "服饰鞋包", "coupon_type": "折扣券", "metric": "订单数"}}
  - filter_conditions: [
      {{"field_hint": "coupon_type", "value": "折扣券", "operator": "=", "required": true}},
      {{"field_hint": "category", "value": "服饰鞋包", "operator": "=", "required": true}}
    ]
  - need_user_confirmation: false

- 输入："通过APP渠道在自营店铺购买手机的订单"
  - intent_type: query_data
  - filter_conditions: [
      {{"field_hint": "channel", "value": "APP", "operator": "=", "required": true}},
      {{"field_hint": "shop_type", "value": "自营", "operator": "=", "required": true}},
      {{"field_hint": "category", "value": "手机", "operator": "=", "required": true}}
    ]

- 输入："使用满减优惠券且由京东物流配送的一线城市订单"
  - intent_type: query_data
  - filter_conditions: [
      {{"field_hint": "coupon_type", "value": "满减", "operator": "=", "required": true}},
      {{"field_hint": "logistics_provider", "value": "京东物流", "operator": "=", "required": true}},
      {{"field_hint": "city_level", "value": "一线城市", "operator": "=", "required": true}}
    ]

- 输入："各物流商在一线城市和二线城市的配送订单数量对比"
  - intent_type: query_data
  - rewritten_query: "统计各物流商在一线城市和二线城市的配送订单数量对比"
  - filter_conditions: [
      {{"field_hint": "city_level", "value": ["一线", "二线"], "operator": "IN", "required": true}}
    ]
  - 注意：用户说"和"表示同时需要两个值，使用数组格式！

- 输入："自营店铺和第三方店铺在手机品类的销售额对比"
  - intent_type: query_data
  - filter_conditions: [
      {{"field_hint": "shop_type", "value": ["自营", "第三方"], "operator": "IN", "required": true}},
      {{"field_hint": "category", "value": "手机", "operator": "=", "required": true}}
    ]

- 输入："顺丰或中通配送的订单"
  - intent_type: query_data  
  - filter_conditions: [
      {{"field_hint": "logistics_provider", "value": ["顺丰", "中通"], "operator": "IN", "required": true}}
    ]
  - 注意："或"也表示多个值！

   - 输入："对比苹果、华为、小米三个品牌的销量"
  - intent_type: query_data
  - filter_conditions: [
      {{"field_hint": "brand", "value": ["苹果", "华为", "小米"], "operator": "IN", "required": true}}
    ]

9. 【核心】查询需求提取 (Query Requirements) - 必须完整提取！:
   分析用户提问，提取以下查询需求（如果有的话）：
   
   a) **排序要求 (sort_by)**:
      - 用户说"降序"、"升序"、"从高到低"、"从低到高"、"排列"、"排序"等
      - 格式: {{"field": "销售金额", "order": "DESC"}} 或 {{"field": "订单数", "order": "ASC"}}
      - 示例: "按销售金额降序" → sort_by: {{"field": "销售金额", "order": "DESC"}}
   
   b) **数量限制 (limit)**:
      - 用户说"前N条"、"top N"、"取N个"、"最多N条"、"N名"等
      - 格式: 整数
      - 示例: "取前10条" → limit: 10
   
   c) **分组维度 (group_dimensions)**:
      - 用户说"按...统计"、"各..."、"分...看"、"每个..."、"不同..."等
      - 格式: 字符串数组
      - 示例: "按省份、品类统计" → group_dimensions: ["省份", "品类"]
   
   d) **输出指标 (required_metrics)**:
      - 用户说"订单数"、"销售额"、"金额"、"数量"、"平均..."、"总..."等聚合指标
      - 格式: 字符串数组
      - 示例: "统计订单数和销售金额" → required_metrics: ["订单数", "销售金额"]
   
   e) **是否需要聚合 (has_aggregation)**:
      - 如果用户需要统计、汇总、分组等操作，设为 true
      - 如果只是查询明细列表，设为 false
   
   示例输出:
   - 输入: "查询2025年各省份、各品类的订单数和销售金额，按销售金额降序取前10条"
   - query_requirements: {{
       "sort_by": {{"field": "销售金额", "order": "DESC"}},
       "limit": 10,
       "group_dimensions": ["省份", "品类"],
       "required_metrics": ["订单数", "销售金额"],
       "has_aggregation": true
     }}
   
   - 输入: "查询用户ID为888的订单列表"
   - query_requirements: {{
       "sort_by": null,
       "limit": null,
       "group_dimensions": [],
       "required_metrics": [],
       "has_aggregation": false
     }}

### 当前时间 (Current Time):
{current_time_context}

### 历史查询结果 (Query Results in History):
{last_query_context}

### 上下文信息 (Context):
History: {history}
User Input: {input}
Verified Entities: {context_entities}

### 重要提示 - query_data 的变体判断 (can_answer_from_history):

当 intent_type='query_data' 时，请进一步判断：用户的问题是否可以完全基于上面的历史查询结果回答？

**【核心原则】can_answer_from_history = true 的前提条件（必须全部满足）**：
1. 历史数据的字段中包含回答所需的信息
2. 用户的问题是针对历史数据进行二次计算或追问
3. 不需要查询数据库中的其他表或其他字段

**can_answer_from_history = true 的情况（仅限以下场景）**：
- 基于历史数据的比较计算："北京比上海多多少？"
- 基于历史数据的排名查询："哪个城市排第二？"
- 基于历史数据的比例计算："北京占总量的百分比？"
- 基于历史数据的求和/平均："这些城市的总和是多少？"
- 解释历史结果："为什么北京最高？"、"这个结果说明了什么？"

→ 必须确认历史数据字段能够回答问题，才能设 can_answer_from_history = true

**can_answer_from_history = false 的情况（默认选项，有疑问就选 false）**：
- 【主题不同】用户问的主题与历史数据无关（如历史是"发货签收"，新问"订单数量"）
- 【字段缺失】历史数据中没有回答所需的字段（如历史无"退款金额"字段，却问"退款多少"）
- 【指标变化】"那订单量呢？"（之前查的是金额）
- 【筛选变化】"那 2024 年的呢？"、"只看广东省的"
- 【维度变化】"按月份统计呢？"
- 【新实体】"那成都的情况呢？"（成都不在历史结果中）
- 【聚合不足】用户问明细但历史只有汇总值
- 【独立问题】问题看起来是一个独立的新查询，如"今年多少订单"、"退款了多少钱"

→ 设 can_answer_from_history = false

**【重要】判断流程**：
1. 先看历史数据的字段列表（如 "省份, 品类, 物流公司, 发货数量, 签收数量"）
2. 再看用户的新问题需要什么字段（如 "订单数量" 需要 COUNT(orders)）
3. 如果新问题需要的字段不在历史数据中 → can_answer_from_history = false
4. 如果不确定 → can_answer_from_history = false（宁可重新查询，不要给出错误答案）

**示例1 - 可以基于历史回答**：
- 历史字段: [省份, 金额]
- 历史数据: [{{"省份": "北京", "金额": 1000}}, {{"省份": "上海", "金额": 800}}]
- 用户追问: "北京比上海多多少？"
- → can_answer_from_history = true（金额字段存在，可以计算差值）

**示例2 - 必须重新查询**：
- 历史字段: [省份, 品类, 发货数量, 签收数量]
- 用户新问: "今年一共有多少订单？"
- → can_answer_from_history = false（历史没有订单数量字段，必须查 orders 表）

**示例3 - 必须重新查询**：
- 历史字段: [省份, 品类, 发货数量]
- 用户新问: "退款了多少钱？"
- → can_answer_from_history = false（历史没有退款字段，必须查 refunds 表）

### 输出格式要求 (Output Requirements):
- 仅返回一个 JSON 对象字符串，可被严格解析为 IntentOutput。
- 必须包含字段: intent_type, rewritten_query, entities, filter_conditions, query_requirements, reason, guidance, detected_keywords, need_user_confirmation, clarification_question.
- 【重要】filter_conditions 必须完整列出用户提问中的所有筛选条件，不能遗漏！
- 【重要】query_requirements 必须完整提取排序、限制、分组、指标等需求！
"""

class IntentAgent:
    def __init__(self):
        # 精确任务使用低温度（从配置读取）
        self.llm = get_llm(temperature=_settings.LLM_TEMPERATURE_PRECISE)
        self.parser = JsonOutputParser(pydantic_object=IntentOutput)
        self.prompt = ChatPromptTemplate.from_template(INTENT_PROMPT)
        self.chain = self.prompt | self.llm | self.parser
        # V15: 加载专业名词服务
        self._term_service = get_term_service()
    
    def _get_business_terms_prompt(self) -> str:
        """
        获取专业名词提示词段落
        
        如果配置了专业名词，返回格式化的名词列表；否则返回空字符串。
        
        Author: ChatBI Team
        """
        return self._term_service.get_terms_prompt()
    
    def _generate_time_context(self) -> str:
        """
        动态生成当前时间上下文，用于注入到提示词中
        
        Author: CYJ
        """
        now = datetime.now()
        
        # 计算各种时间引用
        current_year = now.year
        last_year = current_year - 1
        current_month = now.month
        last_month = current_month - 1 if current_month > 1 else 12
        last_month_year = current_year if current_month > 1 else current_year - 1
        
        # 星期几
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[now.weekday()]
        
        context = f"""今天是 {now.year}年{now.month}月{now.day}日（{weekday}）。
- 「今年」= {current_year}年（即 {current_year}-01-01 至 {current_year}-12-31）
- 「去年」= {last_year}年
- 「本月/这个月」= {current_year}年{current_month}月
- 「上个月」= {last_month_year}年{last_month}月
- 「最近一周」= 最近7天（从{now.year}-{now.month:02d}-{now.day:02d}往前推）
- 「最近一个月」= 最近30天
请在改写时使用正确的年份，不要将「今年」误解为{last_year}年。"""
        return context

    def invoke(self, state: AgentState) -> dict:
        """
        Run the Intent Agent.
        Returns: updates 'intent' in AgentState.
        
        V12: 增加 last_query_context 支持，让 LLM 知道之前的查询结果
        Author: CYJ
        """
        messages = state['messages']
        user_input = messages[-1].content
        
        # V6: 增强历史记忆，从6条增加到40条（约20轮对话）
        # 解决模型"失忆"问题，保留更多上下文信息
        # Author: CYJ
        # Time: 2025-11-26
        history_str = ""
        if len(messages) > 1:
            for msg in messages[-40:-1]:
                role = "User" if msg.type == "human" else "AI"
                history_str += f"{role}: {msg.content}\n"
        
        # Get verified entities from previous turns to help with context resolution
        # (This would be populated by the Orchestrator if it maintained a 'verified_entities' state)
        # For now, we just pass an empty placeholder or what we can find in state
        context_entities = state.get("verified_entities", {})
        
        # 动态生成当前时间上下文
        current_time_context = self._generate_time_context()
        
        # V12: 获取历史查询上下文，用于追问优化
        # V12.1: 改为基于所有历史查询结果，而不只是上一轮
        # Author: CYJ
        # Time: 2025-11-27
        last_query_context = state.get("last_query_context")
        last_query_str = ""
        
        # 从 messages 中提取历史查询结果（如果有结构化数据）
        if last_query_context:
            # 有结构化的查询结果
            data_result = last_query_context.get('data_result', [])
            # 限制数据量，避免 Token 爆炸（取前 50 条）
            if len(data_result) > 50:
                data_preview = data_result[:50]
                data_note = f"\n(注: 共 {len(data_result)} 条记录，以上仅显示前 50 条)"
            else:
                data_preview = data_result
                data_note = ""
            
            last_query_str = f"""
最近一次查询: {last_query_context.get('query', '')}
结果概要: 共 {last_query_context.get('row_count', 0)} 条记录
字段: {', '.join(last_query_context.get('columns', []))}
结构化数据:
{json.dumps(data_preview, ensure_ascii=False, indent=2)}{data_note}

【重要】以上是最近一次查询的完整结果数据，请根据上方指南判断 can_answer_from_history 字段。
"""
        else:
            last_query_str = "无（这是新对话或之前没有查询数据结果）"

        # V15: 获取专业名词段落
        business_terms_section = self._get_business_terms_prompt()
        
        try:
            result = self.chain.invoke({
                "history": history_str,
                "input": user_input,
                "context_entities": str(context_entities),
                "current_time_context": current_time_context,
                "last_query_context": last_query_str,
                "business_terms_section": business_terms_section
            })
            
            intent_data: IntentSchema = {
                "original_query": user_input,
                "rewritten_query": result.get("rewritten_query"),
                "intent_type": result.get("intent_type"),
                "entities": result.get("entities", {}),
                # V2: 新增结构化筛选条件
                "filter_conditions": result.get("filter_conditions", []),
                "reason": result.get("reason"),
                "guidance": result.get("guidance"),
                "detected_keywords": result.get("detected_keywords", []),
                "need_user_confirmation": result.get("need_user_confirmation", False),
                "clarification_question": result.get("clarification_question"),
                # V13: 新增 - 是否可以基于历史数据回答
                "can_answer_from_history": result.get("can_answer_from_history", False),
                "history_answer_reason": result.get("history_answer_reason"),
                # V14: 新增 - 查询需求结构化提取
                "query_requirements": result.get("query_requirements", {}),
            }

            return {"intent": intent_data}

        except Exception as e:
            # Fallback for parsing errors or LLM failures
            # 保守策略：将意图标记为 unclear，提示用户重试或换一种表达，而不是强行假定为查询。
            fallback_intent: IntentSchema = {
                "original_query": user_input,
                "rewritten_query": None,
                "intent_type": "unclear",
                "entities": {},
                "filter_conditions": [],
                "reason": f"IntentAgent failed to parse LLM output: {str(e)}",
                "guidance": "系统暂时未能正确理解您的意图，请稍后重试或换一种表达方式。",
                "detected_keywords": [],
                "need_user_confirmation": False,
                "clarification_question": None,
                "can_answer_from_history": False,
                "history_answer_reason": None,
                "query_requirements": {},
            }

            return {"intent": fallback_intent}

