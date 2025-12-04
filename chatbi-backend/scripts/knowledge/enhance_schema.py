"""
功能：Schema 语义增强脚本
说明：调�?LLM �?Schema 进行扩写，生成同义词、业务含义和常见问题，存�?enriched_schema.json�?
作者：CYJ
时间�?025-11-22
"""
import json
import os
import sys
import logging
import time
from tqdm import tqdm
from typing import Dict, Any

# Add project root to sys.path (chatbi-backend root)
current_dir = os.path.dirname(os.path.abspath(__file__)) # chatbi-backend/scripts/phase2_knowledge_base
scripts_dir = os.path.dirname(current_dir) # chatbi-backend/scripts
backend_root = os.path.dirname(scripts_dir) # chatbi-backend
sys.path.insert(0, backend_root)

# Manually load .env
from dotenv import load_dotenv
dotenv_path = os.path.join(backend_root, '.env')
load_dotenv(dotenv_path)

from app.core.config import get_settings
from app.core.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhance_vector")

# 定义增强内容的输出结�?
class EnrichedContent(BaseModel):
    synonyms: list[str] = Field(description="List of 3-5 synonyms or aliases for this table/column in Chinese.")
    business_meaning: str = Field(description="A brief explanation of what this data represents in business context.")
    common_questions: list[str] = Field(description="3 example natural language questions that would query this data.")

ENHANCE_PROMPT = """You are a Data Dictionary Expert for an E-commerce BI system.
Your task is to enhance the semantic description of a database schema item (Table or Column) to improve vector retrieval accuracy.

### Schema Item:
Type: {type}
Name: {name}
Original Comment: {comment}
Context (Parent Table): {context}

### Task:
1. **Synonyms**: Provide 3-5 synonyms or related terms (e.g. "orders" -> "sales", "transactions", "deal").
2. **Business Meaning**: Explain what this data represents in a business context (e.g. "The total revenue after discounts").
3. **Common Questions**: List 3 user questions that would likely involve this field.

### Output Format:
JSON object matching the following schema. ONLY return JSON.
"""

class SchemaEnhancer:
    def __init__(self):
        self.llm = get_llm(temperature=0.3) # Slight creativity allowed
        self.parser = JsonOutputParser(pydantic_object=EnrichedContent)
        self.prompt = ChatPromptTemplate.from_template(ENHANCE_PROMPT)
        self.chain = self.prompt | self.llm | self.parser
        
        # Paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_path = os.path.join(self.base_dir, "data", "full_schema.json")
        self.output_path = os.path.join(self.base_dir, "data", "enriched_schema.json")
        self.checkpoint_path = os.path.join(self.base_dir, "data", "enhancement_checkpoint.json")

    def load_schema(self):
        if not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Schema file not found: {self.input_path}")
        with open(self.input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_checkpoint(self):
        if os.path.exists(self.output_path):
            with open(self.output_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"database_name": "chatbi", "tables": []}

    def save_result(self, data):
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def enhance_item(self, item_type, name, comment, context=""):
        try:
            response = self.chain.invoke({
                "type": item_type,
                "name": name,
                "comment": comment,
                "context": context
            })
            return response
        except Exception as e:
            logger.error(f"Failed to enhance {name}: {e}")
            # Fallback
            return {
                "synonyms": [],
                "business_meaning": comment or "",
                "common_questions": []
            }

    def run(self):
        raw_schema = self.load_schema()
        enriched_schema = self.load_checkpoint()
        
        # Helper to check if already processed
        processed_tables = {t['name'] for t in enriched_schema['tables']}
        
        total_tables = len(raw_schema['tables'])
        logger.info(f"Starting Schema Enhancement for {total_tables} tables...")

        for i, table in enumerate(tqdm(raw_schema['tables'], desc="Processing Tables")):
            table_name = table['name']
            
            # If table already exists in output (and fully processed), we might skip or update
            # For simplicity, we check if table name is in processed list. 
            # To be more robust, we should check column counts too.
            if table_name in processed_tables:
                logger.info(f"Skipping table {table_name} (already processed)")
                continue

            logger.info(f"Enhancing Table: {table_name}")
            
            # 1. Enhance Table Level
            table_enrichment = self.enhance_item(
                "Table", table_name, table['comment'], ""
            )
            
            new_table = table.copy()
            new_table['enrichment'] = table_enrichment
            new_table['columns'] = []

            # 2. Enhance Columns
            for col in tqdm(table['columns'], desc=f"Cols in {table_name}", leave=False):
                col_name = col['name']
                # logger.info(f"  Enhancing Column: {col_name}")
                
                col_enrichment = self.enhance_item(
                    "Column", col_name, col['comment'], f"Parent Table: {table_name} ({table['comment']})"
                )
                
                new_col = col.copy()
                new_col['enrichment'] = col_enrichment
                new_table['columns'].append(new_col)
                
                # Rate limit
                time.sleep(0.2)

            # Append to result and save immediately (Checkpointing)
            enriched_schema['tables'].append(new_table)
            self.save_result(enriched_schema)
            processed_tables.add(table_name)
            
        logger.info("Schema Enhancement Complete!")
        logger.info(f"Saved to {self.output_path}")

if __name__ == "__main__":
    enhancer = SchemaEnhancer()
    enhancer.run()
