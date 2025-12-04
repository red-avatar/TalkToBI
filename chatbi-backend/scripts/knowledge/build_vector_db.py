"""
功能：混合向量构建脚�?(Hybrid Vector Builder)
说明：读�?enriched_schema.json，将增强后的描述转换�?Embedding �?Keywords，存入新�?schema_embeddings 表�?
作者：CYJ
时间�?025-11-22
"""
import json
import os
import sys
import logging
import time
from sqlalchemy import text
from tqdm import tqdm

# Add project root to sys.path (chatbi-backend root)
current_dir = os.path.dirname(os.path.abspath(__file__)) # chatbi-backend/scripts/phase2_knowledge_base
scripts_dir = os.path.dirname(current_dir) # chatbi-backend/scripts
backend_root = os.path.dirname(scripts_dir) # chatbi-backend
sys.path.insert(0, backend_root)

# Manually load .env
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path)

from app.modules.vector.store import VectorStore
from app.core.config import get_settings

# Try imports
try:
    import dashscope
    from dashscope import TextEmbedding
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_hybrid_vector")
settings = get_settings()

def get_embedding(text: str) -> list:
    """Get embedding using configured provider."""
    text = text.replace("\n", " ").strip()
    
    try:
        if settings.LLM_PROVIDER == "dashscope":
             # Use LangChain OpenAIEmbeddings to support verify=False
            from langchain_openai import OpenAIEmbeddings
            import httpx
            
            http_client = httpx.Client(verify=False)
            
            embeddings = OpenAIEmbeddings(
                model=settings.DASHSCOPE_EMBEDDING_MODEL,
                openai_api_key=settings.DASHSCOPE_API_KEY,
                openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                http_client=http_client,
                check_embedding_ctx_length=False 
            )
            return embeddings.embed_query(text)
            
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return [0.0] * 1024
        
    return [0.0] * 1024

def build_hybrid_store():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(base_dir, "data", "enriched_schema.json")
    
    if not os.path.exists(input_path):
        logger.error(f"Enriched schema not found at {input_path}. Run enhance_schema.py first.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Output path for local build
    output_path = os.path.join(base_dir, "data", "vectors_with_embeddings.json")
    
    logger.info("Step 1: Building Local Vector Data...")
    
    items_to_add = []
    
    for table in tqdm(data['tables'], desc="Generating Embeddings"):
        # --- Table Level ---
        t_enrich = table.get('enrichment', {})
        
        # Construct Enriched Description
        # Format: "Table users (用户�?. Meaning: ... Synonyms: ... Questions: ..."
        t_desc_text = f"Table {table['name']} ({table['comment']}). "
        t_desc_text += f"Business Meaning: {t_enrich.get('business_meaning', '')} "
        t_desc_text += f"Synonyms: {', '.join(t_enrich.get('synonyms', []))} "
        t_desc_text += f"Common Questions: {', '.join(t_enrich.get('common_questions', []))}"
        
        items_to_add.append({
            "object_type": "table",
            "object_name": table['name'],
            "original_description": f"Table {table['name']}: {table['comment']}",
            "enriched_description": t_desc_text,
            "metadata_json": json.dumps({"comment": table['comment']}),
            "embedding": get_embedding(t_desc_text)
        })
        
        # --- Column Level ---
        for col in table['columns']:
            c_enrich = col.get('enrichment', {})
            
            c_desc_text = f"Column {col['name']} in table {table['name']} ({col['comment']}). "
            c_desc_text += f"Business Meaning: {c_enrich.get('business_meaning', '')} "
            c_desc_text += f"Synonyms: {', '.join(c_enrich.get('synonyms', []))} "
            
            # Add sample values to text for better matching
            if col.get('sample_values'):
                c_desc_text += f"Samples: {', '.join([str(v) for v in col['sample_values']])} "
                
            items_to_add.append({
                "object_type": "column",
                "object_name": f"{table['name']}.{col['name']}",
                "original_description": f"Column {col['name']}: {col['comment']}",
                "enriched_description": c_desc_text,
                "metadata_json": json.dumps({
                    "table": table['name'],
                    "type": col['data_type'],
                    "comment": col['comment'],
                    "sample_values": col.get('sample_values')
                }),
                "embedding": get_embedding(c_desc_text)
            })
            
            time.sleep(0.02) # Rate limit

    # Save Local JSON
    logger.info(f"Saving {len(items_to_add)} items to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items_to_add, f, ensure_ascii=False, indent=2)
        
    logger.info("Step 1 Complete: Local data ready.")
    
    # Step 2: Bulk Insert
    bulk_insert_to_pg(output_path)

def bulk_insert_to_pg(json_path):
    logger.info("Step 2: Bulk Inserting into PostgreSQL...")
    
    store = VectorStore()
    
    # 1. Apply Schema Update (DDL)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ddl_path = os.path.join(base_dir, "data", "schema_update_v2.sql")
    
    with store.engine.connect() as conn:
        # Optional: Run DDL if needed (commented out since user said table is ready)
        # if os.path.exists(ddl_path): ...
        
        logger.info("Truncating table...")
        conn.execute(text("TRUNCATE TABLE schema_embeddings"))
        conn.commit()
        
        logger.info("Loading JSON...")
        with open(json_path, 'r', encoding='utf-8') as f:
            items = json.load(f)
            
        logger.info(f"Inserting {len(items)} records...")
        
        # Use bulk insert via SQLAlchemy parameters
        # We need to handle the tsvector conversion in SQL
        sql = text("""
            INSERT INTO schema_embeddings 
            (object_type, object_name, original_description, enriched_description, metadata_json, embedding, keywords_ts)
            VALUES 
            (:object_type, :object_name, :original_description, :enriched_description, :metadata_json, :embedding,
             setweight(to_tsvector('simple', :object_name), 'A') || 
             setweight(to_tsvector('simple', :enriched_description), 'B') ||
             setweight(to_tsvector('simple', :original_description), 'C')
            )
        """)
        
        # Chunking for safety (e.g. 100 at a time)
        chunk_size = 100
        for i in tqdm(range(0, len(items), chunk_size), desc="Bulk Inserting"):
            chunk = items[i:i + chunk_size]
            conn.execute(sql, chunk)
            conn.commit()
            
    logger.info("Step 2 Complete: Database Populated!")

if __name__ == "__main__":
    build_hybrid_store()
