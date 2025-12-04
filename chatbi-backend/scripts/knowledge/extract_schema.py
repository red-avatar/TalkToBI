"""
功能：全�?Schema 提取脚本
说明：连接配置的 MySQL 数据库，提取所有表、字段的详细物理元数据，并保存为 JSON 文件�?
作者：CYJ
时间�?025-11-20
"""
import json
import os
import sys
import logging

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.modules.schema.loader import SchemaLoader
# Ensure logging is configured to show info
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("extract_schema")

def extract_and_save():
    try:
        logger.info("Initializing SchemaLoader...")
        loader = SchemaLoader()
        logger.info(f"Connected to database: {loader.engine.url.database}")
        
        logger.info("Starting full schema extraction...")
        table_schemas = loader.extract_full_schema()
        logger.info(f"Successfully extracted {len(table_schemas)} tables.")
        
        # Convert Pydantic models to dict
        data = {
            "database_name": loader.engine.url.database,
            "tables": [t.model_dump() for t in table_schemas]
        }
        
        # Save to scripts/data/ directory
        output_dir = os.path.join(os.path.dirname(__file__), "data")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        output_path = os.path.join(output_dir, "full_schema.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Full schema saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR: Failed to extract schema: {e}")
        sys.exit(1)

if __name__ == "__main__":
    extract_and_save()
