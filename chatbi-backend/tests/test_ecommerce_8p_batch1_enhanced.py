"""
ChatBI 电商复杂查询（8表+）测试 - 批次1 增强版

目标：
- 专门覆盖 8 张及以上表的多表联结场景
- 问答到最终结构输出的端到端耗时统计
- 场景均来自电商 BI 分析真实问题
- 增加详细汇总报告、分类统计、SQL分析导出

Author: CYJ
Time: 2025-11-25
"""

import os
import sys
import re
import time
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.dialog.orchestrator import orchestrator_app
from langchain_core.messages import HumanMessage

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
log_file = os.path.join(LOG_DIR, f"ecom_8p_batch1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ecom_8p_batch1")


class AnalysisCategory(Enum):
    """
    BI分析场景分类
    
    Author: CYJ
    Time: 2025-11-25
    """
    SALES = "销售分析"
    USER = "用户分析"
    MARKETING = "营销分析"
    LOGISTICS = "物流分析"
    CONVERSION = "转化分析"
    REFUND = "退款分析"
    COMPREHENSIVE = "综合分析"


@dataclass
class EightPlusCase:
    """
    8表+ 多表联结测试用例

    Attributes:
        name: 用例名
        query: 自然语言问题
        min_tables: 预期最少表数量（>=8）
        category: 分析场景分类
        notes: 业务场景说明
        expect_tables_hint: 期望涉及的表（提示/对齐，不做强约束）

    Author: CYJ
    Time: 2025-11-25
    """
    name: str
    query: str
    min_tables: int = 8
    category: AnalysisCategory = AnalysisCategory.COMPREHENSIVE
    notes: str = ""
    expect_tables_hint: List[str] = field(default_factory=list)


@dataclass
class CaseResult:
    """
    单用例结果

    Author: CYJ
    Time: 2025-11-25
    """
    case: EightPlusCase
    success: bool
    sql: Optional[str]
    table_count: int
    tables: List[str]
    data_rows: int
    final_answer: Optional[str]
    elapsed_ms: float
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


def _extract_tables_from_sql(sql: str) -> List[str]:
    """
    基于正则从 SQL 中提取出现的表名，支持 schema 前缀与别名。

    Author: CYJ
    Time: 2025-11-25
    """
    if not sql:
        return []
    # 捕获 FROM/JOIN 后的标识，允许 chatbi.orders 形式
    pattern = r"(?:FROM|JOIN)\s+([a-zA-Z_][\w\.]*)(?:\s+AS\s+\w+|\s+\w+)?"
    matches = re.findall(pattern, sql, flags=re.IGNORECASE)
    cleaned: Set[str] = set()
    for m in matches:
        # 去掉 schema 前缀
        tbl = m.split(".")[-1].strip().lower()
        # 排除子查询关键字等伪命中
        if tbl not in {"select", "with", "on", "where"}:
            cleaned.add(tbl)
    return sorted(cleaned)


def run_case(c: EightPlusCase) -> CaseResult:
    """
    执行单个 8表+ 用例并统计耗时。

    Author: CYJ
    Time: 2025-11-25
    """
    start = time.perf_counter()
    try:
        raw = orchestrator_app.invoke(
            {"messages": [HumanMessage(content=c.query)]},
            config={"configurable": {"thread_id": f"ecom_8p_{int(time.time())}"}},
        )
        end = time.perf_counter()
        elapsed_ms = (end - start) * 1000

        sql = raw.get("sql_query")
        data_result = raw.get("data_result") or []
        final_answer = raw.get("final_answer")

        tables = _extract_tables_from_sql(sql or "")
        table_count = len(tables)

        success = (
            sql is not None
            and final_answer is not None
            and table_count >= c.min_tables
            and "clarification" not in str(sql).lower()
        )

        return CaseResult(
            case=c,
            success=success,
            sql=sql,
            table_count=table_count,
            tables=tables,
            data_rows=len(data_result) if isinstance(data_result, list) else 0,
            final_answer=final_answer,
            elapsed_ms=elapsed_ms,
            raw=raw,
        )
    except Exception as e:
        end = time.perf_counter()
        return CaseResult(
            case=c,
            success=False,
            sql=None,
            table_count=0,
            tables=[],
            data_rows=0,
            final_answer=None,
            elapsed_ms=(end - start) * 1000,
            error=str(e),
        )


def _cases_batch1() -> List[EightPlusCase]:
    """
    批次1：6个 8表+ 电商 BI 多表联结问题

    Author: CYJ
    Time: 2025-11-25
    """
    return [
        EightPlusCase(
            name="一线城市-APP-自营-手机-顺丰-微信支付",
            query=(
                "统计最近30天一线城市用户通过APP渠道在自营店铺购买手机类商品，且由顺丰配送并使用微信支付成功的"
                "订单数量与GMV，以及各城市占比"
            ),
            min_tables=8,
            category=AnalysisCategory.COMPREHENSIVE,
            notes="城市层级+渠道+店铺类型+品类+物流+支付状态+时间窗",
            expect_tables_hint=[
                "orders","order_items","products","categories","shops",
                "dim_region","dim_channel","shipments","logistics_providers","payments"
            ],
        ),
        EightPlusCase(
            name="二线城市-第三方-电子产品-支付宝-满减券-退款成功",
            query=(
                "二线城市第三方店铺售出的电子产品类商品中，通过支付宝支付且使用满减券，后续退款成功的订单数量与退款金额"
            ),
            min_tables=8,
            category=AnalysisCategory.REFUND,
            notes="地区+店铺类型+品类+支付方式+券类型+退款状态",
            expect_tables_hint=[
                "orders","order_items","products","categories","shops","dim_region",
                "payments","refunds","order_coupons","coupons"
            ],
        ),
        EightPlusCase(
            name="北上广-小程序-品牌对比-京东物流",
            query=(
                "近180天北京/上海/广州通过小程序渠道购买手机/家电两大品类，分别对比苹果与华为品牌的订单数、GMV和客单价，"
                "仅统计由京东物流配送且已签收的订单"
            ),
            min_tables=9,
            category=AnalysisCategory.SALES,
            notes="多城市+多渠道+多品类+品牌+物流商+签收状态",
            expect_tables_hint=[
                "orders","order_items","products","categories","users","dim_region",
                "dim_channel","shipments","logistics_providers"
            ],
        ),
        EightPlusCase(
            name="VIP用户-官网-电子-折扣券-顺丰-已签收",
            query=(
                "分析VIP(等级>=3)用户通过官网渠道购买电子产品并使用折扣券，且由顺丰配送并已签收的订单数量与GMV"
            ),
            min_tables=9,
            category=AnalysisCategory.USER,
            notes="用户等级+渠道+品类+优惠券类型+物流商+签收",
            expect_tables_hint=[
                "users","orders","order_items","products","categories","dim_channel",
                "order_coupons","coupons","shipments","logistics_providers","shipment_tracking_events"
            ],
        ),
        EightPlusCase(
            name="自营VS第三方-一二线-手机-退款率",
            query=(
                "最近90天一线和二线城市手机类商品在自营与第三方店铺的订单量、GMV以及退款率对比"
            ),
            min_tables=8,
            category=AnalysisCategory.REFUND,
            notes="城市等级+品类+店铺类型+退款率",
            expect_tables_hint=[
                "orders","order_items","products","categories","shops","dim_region",
                "payments","refunds","dim_channel"
            ],
        ),
        EightPlusCase(
            name="新客VS老客-注册/下单渠道-电子产品-用券-顺丰/中通",
            query=(
                "对比新客与老客在电子产品类商品上的客单价，分注册渠道与下单渠道拆分，限制使用过优惠券且由顺丰或中通配送"
            ),
            min_tables=10,
            category=AnalysisCategory.USER,
            notes="新客定义可按首单时间，涉及注册渠道+下单渠道+用券+物流商",
            expect_tables_hint=[
                "users","orders","order_items","products","categories",
                "dim_channel","order_coupons","coupons","shipments","logistics_providers","shops"
            ],
        ),
    ]


def print_summary(results: List[CaseResult]):
    """
    打印详细测试汇总报告
    
    Author: CYJ
    Time: 2025-11-25
    """
    print("\n\n" + "=" * 90)
    print("📊 测试结果汇总报告")
    print("=" * 90)
    
    if not results:
        print("没有测试结果")
        return
    
    # 整体统计
    total = len(results)
    success_count = sum(1 for r in results if r.success)
    fail_count = total - success_count
    
    total_time = sum(r.elapsed_ms for r in results)
    avg_time = total_time / total if total > 0 else 0
    
    print(f"\n【整体统计】")
    print(f"  总用例数: {total}")
    print(f"  成功: {success_count} ({success_count/total*100:.1f}%)")
    print(f"  失败: {fail_count} ({fail_count/total*100:.1f}%)")
    print(f"  总耗时: {total_time:.2f}ms ({total_time/1000:.2f}秒)")
    print(f"  平均耗时: {avg_time:.2f}ms ({avg_time/1000:.2f}秒)")
    
    # 按分析场景统计
    categories = {}
    for r in results:
        cat = r.case.category.value
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "times": []}
        categories[cat]["total"] += 1
        if r.success:
            categories[cat]["success"] += 1
        categories[cat]["times"].append(r.elapsed_ms)
    
    print(f"\n【按分析场景统计】")
    for cat, stats in sorted(categories.items()):
        success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        avg_cat_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
        print(f"  {cat}: {stats['success']}/{stats['total']} 成功 ({success_rate:.1f}%), 平均耗时 {avg_cat_time:.2f}ms")
    
    # 按表数量统计
    table_stats = {}
    for r in results:
        min_t = r.case.min_tables
        if min_t not in table_stats:
            table_stats[min_t] = {"total": 0, "success": 0, "avg_actual": []}
        table_stats[min_t]["total"] += 1
        if r.success:
            table_stats[min_t]["success"] += 1
        table_stats[min_t]["avg_actual"].append(r.table_count)
    
    print(f"\n【按预期表数统计】")
    for min_t, stats in sorted(table_stats.items()):
        success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        avg_actual = sum(stats["avg_actual"]) / len(stats["avg_actual"]) if stats["avg_actual"] else 0
        print(f"  {min_t}表+: {stats['success']}/{stats['total']} 成功 ({success_rate:.1f}%), 实际平均 {avg_actual:.1f}表")
    
    # 耗时排行
    print(f"\n【耗时TOP5（最慢）】")
    sorted_by_time = sorted(results, key=lambda x: x.elapsed_ms, reverse=True)
    for i, r in enumerate(sorted_by_time[:5], 1):
        status = "✅" if r.success else "❌"
        print(f"  {i}. [{status}] {r.case.name}: {r.elapsed_ms:.2f}ms ({r.elapsed_ms/1000:.2f}s), {r.table_count}表")
    
    # 失败用例详情
    failed = [r for r in results if not r.success]
    if failed:
        print(f"\n【失败用例详情】")
        for r in failed:
            print(f"\n  ❌ {r.case.name} ({r.case.min_tables}表+)")
            print(f"     提问: {r.case.query[:80]}...")
            print(f"     实际表数: {r.table_count}")
            print(f"     错误: {r.error or 'SQL生成失败或表数不达标'}")
            if r.sql:
                print(f"     SQL: {r.sql[:150]}...")
    
    # 成功用例展示
    success_results = [r for r in results if r.success]
    if success_results:
        print(f"\n【成功用例示例】")
        for r in success_results[:3]:
            print(f"\n  ✅ {r.case.name}:")
            print(f"     提问: {r.case.query[:60]}...")
            print(f"     表数: {r.table_count}, 耗时: {r.elapsed_ms:.2f}ms")
            print(f"     涉及表: {', '.join(r.tables[:10])}")
    
    print("\n" + "=" * 90)
    print("测试完成")
    print("=" * 90)


def export_json(results: List[CaseResult], filepath: str, batch: int):
    """
    导出JSON结果
    
    Author: CYJ
    Time: 2025-11-25
    """
    total = len(results)
    succ = sum(1 for x in results if x.success)
    avg = sum(x.elapsed_ms for x in results) / total if total else 0.0
    
    payload = {
        "batch": batch,
        "time": datetime.now().isoformat(),
        "total": total,
        "success": succ,
        "avg_ms": avg,
        "results": [
            {
                "name": r.case.name,
                "category": r.case.category.value,
                "success": r.success,
                "elapsed_ms": r.elapsed_ms,
                "min_tables": r.case.min_tables,
                "table_count": r.table_count,
                "tables": r.tables,
                "data_rows": r.data_rows,
                "sql": r.sql,
                "final_answer": r.final_answer[:500] if r.final_answer else None,
                "error": r.error,
            }
            for r in results
        ],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n📁 JSON结果已导出: {filepath}")


def export_sql_analysis(results: List[CaseResult], batch_name: str):
    """
    导出SQL对比分析文件，便于后续MCP验证
    
    Args:
        results: 测试结果列表
        batch_name: 批次名称
        
    Author: CYJ
    Time: 2025-11-25
    """
    filepath = os.path.join(LOG_DIR, f"{batch_name}_sql_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {batch_name.upper()} SQL分析报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for i, r in enumerate(results, 1):
            f.write(f"## {i}. {r.case.name}\n\n")
            f.write(f"**预期最少表数**: {r.case.min_tables}\n")
            f.write(f"**实际表数**: {r.table_count}\n")
            f.write(f"**场景**: {r.case.category.value}\n")
            f.write(f"**提问**: {r.case.query}\n")
            f.write(f"**涉及表**: {', '.join(r.tables)}\n")
            f.write(f"**状态**: {'✅ 成功' if r.success else '❌ 失败'}\n")
            f.write(f"**耗时**: {r.elapsed_ms:.2f}ms ({r.elapsed_ms/1000:.2f}s)\n")
            f.write(f"**数据行数**: {r.data_rows}\n\n")
            
            f.write(f"### 生成的SQL\n")
            f.write(f"```sql\n{r.sql or 'NULL'}\n```\n\n")
            
            if r.error:
                f.write(f"### 错误信息\n")
                f.write(f"```\n{r.error}\n```\n\n")
            
            if r.final_answer:
                answer_preview = r.final_answer[:500] if len(r.final_answer) > 500 else r.final_answer
                f.write(f"### 回答摘要\n")
                f.write(f"{answer_preview}\n\n")
            
            f.write(f"---\n\n")
        
        # 汇总统计
        f.write(f"## 汇总统计\n\n")
        total = len(results)
        success = sum(1 for r in results if r.success)
        f.write(f"- 总用例: {total}\n")
        f.write(f"- 成功: {success} ({success/total*100:.1f}%)\n")
        f.write(f"- 失败: {total-success}\n")
        f.write(f"- 平均耗时: {sum(r.elapsed_ms for r in results)/total:.2f}ms\n")
    
    print(f"📝 SQL分析报告已导出: {filepath}")


def run_batch(cases: List[EightPlusCase]) -> List[CaseResult]:
    """
    执行一批用例并输出概览与JSON日志。

    Author: CYJ
    Time: 2025-11-25
    """
    print("\n" + "=" * 90)
    print("🧪 ChatBI 电商复杂查询（8表+）测试 - 批次1")
    print("=" * 90)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试用例数: {len(cases)}")
    print(f"测试范围: 8-10+表关联的电商BI分析场景")
    print("=" * 90)

    results: List[CaseResult] = []
    for i, c in enumerate(cases, 1):
        print(f"\n{'='*90}")
        print(f">>> 进度: {i}/{len(cases)} - {c.name}")
        print(f"{'='*90}")
        print(f"场景分类: {c.category.value}")
        print(f"业务场景: {c.notes}")
        print(f"提问: {c.query}")
        print(f"预期最少表数: {c.min_tables}")
        print(f"{'-'*90}")
        
        r = run_case(c)
        results.append(r)
        
        # 详细输出
        print(f"\n⏱️  总耗时: {r.elapsed_ms:.2f}ms ({r.elapsed_ms/1000:.2f}秒)")
        print(f"\n📊 表分析:")
        print(f"   - 表数量: {r.table_count} (要求≥{c.min_tables})")
        print(f"   - 涉及表: {', '.join(r.tables) if r.tables else 'N/A'}")
        
        if r.sql:
            print(f"\n📝 生成SQL:")
            sql_lines = r.sql.split('\n')
            for line in sql_lines[:15]:  # 显示前15行
                print(f"   {line}")
            if len(sql_lines) > 15:
                print(f"   ... (共{len(sql_lines)}行)...")
        
        print(f"\n📈 数据行数: {r.data_rows}")
        
        if r.final_answer:
            answer_preview = str(r.final_answer)[:300]
            print(f"\n💬 回答摘要:")
            print(f"   {answer_preview}{'...' if len(str(r.final_answer)) > 300 else ''}")
        
        status = "✅ 成功" if r.success else "❌ 失败"
        print(f"\n状态: {status}")
        
        if r.error:
            print(f"\n❌ 错误: {r.error}")

    # 详细汇总报告
    print_summary(results)

    # 导出 JSON
    out_path = os.path.join(LOG_DIR, f"ecom_8p_batch1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    export_json(results, out_path, batch=1)
    
    # 导出 SQL 分析报告
    export_sql_analysis(results, "batch1")

    return results


if __name__ == "__main__":
    run_batch(_cases_batch1())
