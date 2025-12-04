-- 启用 pg_trgm 扩展用于模糊匹配（可选，但推荐）
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 重新设计 schema_embeddings 表
-- 注意：我们将使用 Alembic 或手动执行此脚本进行迁移
-- 如果表已存在，建议先备份数据（如果数据重要），但在开发阶段可以直接重建

DROP TABLE IF EXISTS schema_embeddings;

CREATE TABLE schema_embeddings (
    id SERIAL PRIMARY KEY,
    
    -- 基础元数据
    object_type VARCHAR(50) NOT NULL, -- 'table' 或 'column'
    object_name VARCHAR(255) NOT NULL, -- 'orders' 或 'orders.total_amount'
    
    -- 原始描述 (从 comment 读取)
    original_description TEXT,
    
    -- LLM 增强后的富文本描述 (用于生成 Embedding)
    -- 格式: "Business Meaning: ... Synonyms: ... Common Questions: ..."
    enriched_description TEXT,
    
    -- 结构化元数据 (JSONB)
    -- 包含: data_type, sample_values, is_primary_key, etc.
    metadata_json JSONB,
    
    -- 向量字段 (1536 维，适配 text-embedding-v3)
    -- 如果使用的是 dashscope text-embedding-v3，通常是 1024 维，请根据实际模型调整
    -- 当前代码使用的是 1024 维 (Vector(1024) in store.py)
    embedding vector(1024),
    
    -- 关键词索引字段 (PostgreSQL Full Text Search)
    -- 将 object_name, original_description, enriched_description 组合索引
    keywords_ts tsvector,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引以加速检索

-- 1. 向量索引 (HNSW - 推荐用于生产环境，IVFFlat 用于开发环境)
-- 需要根据数据量选择。数据量小 (<10k) 时，全表扫描也很快，但为了规范，我们建立 HNSW
CREATE INDEX ON schema_embeddings USING hnsw (embedding vector_cosine_ops);

-- 2. 全文检索索引 (GIN)
CREATE INDEX idx_schema_keywords ON schema_embeddings USING GIN (keywords_ts);

-- 3. 基础字段索引
CREATE INDEX idx_object_name ON schema_embeddings(object_name);
CREATE INDEX idx_object_type ON schema_embeddings(object_type);
