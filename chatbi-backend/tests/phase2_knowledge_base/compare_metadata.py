"""
功能：对比 verified_metadata.json 和 relationships_enhanced.json
说明：检查是否有遗漏或错误
作者：陈怡坚
时间：2025-11-20
"""
import json
import os
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
data_dir = os.path.join(PROJECT_ROOT, "scripts", "phase2_knowledge_base", "data")

# 读取实际数据库元数据
with open(os.path.join(data_dir, "verified_metadata.json"), 'r', encoding='utf-8') as f:
    verified = json.load(f)

# 读取我创建的增强版关系
with open(os.path.join(data_dir, "relationships_enhanced.json"), 'r', encoding='utf-8') as f:
    enhanced = json.load(f)

print("=" * 80)
print("元数据对比报告")
print("=" * 80)

# 1. 对比表数量
verified_tables = {t["table_name"] for t in verified["tables"]}
enhanced_tables = {t["table_name"] for t in enhanced["tables"]}

print(f"\n【表数量对比】")
print(f"实际数据库: {len(verified_tables)} 张表")
print(f"enhanced.json: {len(enhanced_tables)} 张表")
if verified_tables == enhanced_tables:
    print("✅ 表列表完全一致")
else:
    missing = verified_tables - enhanced_tables
    extra = enhanced_tables - verified_tables
    if missing:
        print(f"❌ enhanced.json 缺少: {missing}")
    if extra:
        print(f"❌ enhanced.json 多余: {extra}")

# 2. 对比主键
print(f"\n【主键对比】")
pk_verified = {t["table_name"]: t["primary_keys"] for t in verified["tables"]}
pk_enhanced = {t["table_name"]: t["primary_keys"] for t in enhanced["tables"]}

pk_errors = []
for table in verified_tables:
    v_pks = set(pk_verified.get(table, []))
    e_pks = set(pk_enhanced.get(table, []))
    if v_pks != e_pks:
        pk_errors.append(f"  {table}: 实际={v_pks}, enhanced={e_pks}")

if pk_errors:
    print(f"❌ 发现 {len(pk_errors)} 个主键不一致:")
    for err in pk_errors:
        print(err)
else:
    print(f"✅ 所有主键一致 ({len(verified_tables)} 张表)")

# 3. 对比外键
print(f"\n【外键对比】")
fk_verified_set = set()
for fk in verified["foreign_keys_summary"]:
    key = (fk["source_table"], fk["source_column"], fk["target_table"], fk["target_column"])
    fk_verified_set.add(key)

fk_enhanced_set = set()
for ref in enhanced["column_references"]:
    key = (ref["source_table"], ref["source_column"], ref["target_table"], ref["target_column"])
    fk_enhanced_set.add(key)

print(f"实际数据库: {len(fk_verified_set)} 个外键")
print(f"enhanced.json: {len(fk_enhanced_set)} 个外键")

missing_fks = fk_verified_set - fk_enhanced_set
extra_fks = fk_enhanced_set - fk_verified_set

if missing_fks:
    print(f"\n❌ enhanced.json 缺少 {len(missing_fks)} 个外键:")
    for fk in sorted(missing_fks):
        print(f"  - {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")

if extra_fks:
    print(f"\n❌ enhanced.json 多余 {len(extra_fks)} 个外键:")
    for fk in sorted(extra_fks):
        print(f"  - {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")

if not missing_fks and not extra_fks:
    print("✅ 所有外键完全一致")

# 4. 对比索引（统计）
print(f"\n【索引对比】")
idx_verified_count = len(verified["indexes_summary"])
idx_enhanced_count = sum(len(t["indexes"]) for t in enhanced["tables"])

print(f"实际数据库: {idx_verified_count} 个索引")
print(f"enhanced.json: {idx_enhanced_count} 个索引")

if idx_verified_count == idx_enhanced_count:
    print("✅ 索引数量一致")
else:
    print(f"⚠️ 索引数量差异: {abs(idx_verified_count - idx_enhanced_count)}")

# 5. 检查索引详情
print(f"\n【索引详细检查】")
for table in sorted(verified_tables):
    v_table = next((t for t in verified["tables"] if t["table_name"] == table), None)
    e_table = next((t for t in enhanced["tables"] if t["table_name"] == table), None)
    
    if not v_table or not e_table:
        continue
    
    v_indexes = {idx["name"]: idx["columns"] for idx in v_table["indexes"]}
    e_indexes = {idx["name"]: idx["columns"] for idx in e_table["indexes"]}
    
    v_names = set(v_indexes.keys())
    e_names = set(e_indexes.keys())
    
    missing_idx = v_names - e_names
    extra_idx = e_names - v_names
    
    if missing_idx or extra_idx:
        print(f"\n表 {table}:")
        if missing_idx:
            print(f"  ❌ 缺少索引: {missing_idx}")
        if extra_idx:
            print(f"  ❌ 多余索引: {extra_idx}")

print(f"\n{'='*80}")
print("对比完成")
print(f"{'='*80}")
