"""
功能：验证数据库元数据，生成详细报告
说明：利用 SchemaLoader 提取实际数据库的主键、外键、索引信息
作者：陈怡坚
时间：2025-11-20
"""
import sys
import os
import json
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "scripts", "phase2_knowledge_base", "data")

sys.path.append(PROJECT_ROOT)

from app.modules.schema.loader import SchemaLoader
from sqlalchemy import inspect

def verify_all_metadata():
    loader = SchemaLoader()
    inspector = inspect(loader.engine)
    
    tables = sorted(loader.get_all_tables())
    
    print("=" * 80)
    print("数据库元数据验证报告")
    print("=" * 80)
    print(f"\n总共 {len(tables)} 张表\n")
    
    all_metadata = {
        "tables": [],
        "foreign_keys_summary": [],
        "indexes_summary": []
    }
    
    for table in tables:
        print(f"\n{'='*80}")
        print(f"表名: {table}")
        print(f"{'='*80}")
        
        table_meta = {
            "table_name": table,
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": []
        }
        
        # 1. 主键
        pk_constraint = inspector.get_pk_constraint(table)
        pks = pk_constraint.get('constrained_columns', [])
        table_meta["primary_keys"] = pks
        print(f"\n主键: {', '.join(pks) if pks else '无'}")
        
        # 2. 外键
        fks = inspector.get_foreign_keys(table)
        print(f"\n外键 ({len(fks)} 个):")
        for fk in fks:
            source_cols = fk['constrained_columns']
            target_table = fk['referred_table']
            target_cols = fk['referred_columns']
            
            for i, src_col in enumerate(source_cols):
                tgt_col = target_cols[i] if i < len(target_cols) else target_cols[0]
                fk_info = {
                    "source_table": table,
                    "source_column": src_col,
                    "target_table": target_table,
                    "target_column": tgt_col,
                    "constraint_name": fk.get('name', '')
                }
                table_meta["foreign_keys"].append(fk_info)
                all_metadata["foreign_keys_summary"].append(fk_info)
                print(f"  - {table}.{src_col} → {target_table}.{tgt_col}")
        
        # 3. 索引
        indexes = inspector.get_indexes(table)
        print(f"\n索引 ({len(indexes)} 个):")
        for idx in indexes:
            idx_name = idx['name']
            idx_cols = idx['column_names']
            is_unique = idx.get('unique', False)
            idx_type = 'UNIQUE' if is_unique else 'INDEX'
            
            # 跳过主键索引（已在主键部分显示）
            if idx_name == 'PRIMARY':
                idx_type = 'PRIMARY'
            
            idx_info = {
                "name": idx_name,
                "columns": idx_cols,
                "type": idx_type,
                "is_unique": is_unique
            }
            table_meta["indexes"].append(idx_info)
            all_metadata["indexes_summary"].append({
                "table": table,
                **idx_info
            })
            
            print(f"  - {idx_name} ({idx_type}): {', '.join(idx_cols)}")
        
        all_metadata["tables"].append(table_meta)
    
    # 汇总统计
    print(f"\n{'='*80}")
    print("汇总统计")
    print(f"{'='*80}")
    print(f"总表数: {len(tables)}")
    print(f"总外键数: {len(all_metadata['foreign_keys_summary'])}")
    print(f"总索引数: {len(all_metadata['indexes_summary'])}")
    
    # 保存到 JSON
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

    output_path = os.path.join(DATA_DIR, "verified_metadata.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 元数据已保存到: {output_path}")
    
    return all_metadata

if __name__ == "__main__":
    verify_all_metadata()
