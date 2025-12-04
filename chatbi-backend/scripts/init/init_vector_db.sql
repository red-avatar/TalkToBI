-- ============================================
-- ChatBI 向量数据库初始化
-- 
-- 使用方式：
-- psql -U postgres -d chatbi_pg -f init_vector_db.sql
--
-- 前置要求：
-- 1. PostgreSQL 14+
-- 2. 已安装 pgvector 扩展
--
-- Author: CYJ
-- Time: 2025-12
-- ============================================

-- 创建数据库（如果不存在）
-- 注意：需要先以 postgres 用户连接执行
-- CREATE DATABASE chatbi_pg;

-- 连接到数据库后执行以下内容
-- \c chatbi_pg

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- Schema 向量表
-- 用途: 存储表/列的语义向量，支持相似度检索
-- ============================================
DROP TABLE IF EXISTS schema_embeddings;
CREATE TABLE schema_embeddings (
    id SERIAL PRIMARY KEY,
    object_type VARCHAR(50) NOT NULL,           -- 对象类型: 'table' 或 'column'
    object_name VARCHAR(255) NOT NULL,          -- 对象名称: 如 'orders' 或 'orders.total_amount'
    original_description TEXT,                   -- 原始描述（来自数据库注释）
    enriched_description TEXT,                   -- 增强描述（LLM 生成的语义扩展）
    metadata_json JSONB,                         -- 元数据 JSON（表结构、字段类型等）
    embedding vector(1024),                      -- 向量嵌入（DashScope text-embedding-v3 维度）
    keywords_ts TSVECTOR                         -- 全文搜索向量（用于混合检索）
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_object_type 
    ON schema_embeddings(object_type);

CREATE INDEX IF NOT EXISTS idx_schema_embeddings_object_name 
    ON schema_embeddings(object_name);

-- 向量索引（IVFFlat，适合中等规模数据）
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_vector 
    ON schema_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_schema_embeddings_keywords_ts 
    ON schema_embeddings USING gin(keywords_ts);

-- ============================================
-- 业务术语向量表（可选）
-- 用途: 存储业务专业术语的向量
-- ============================================
DROP TABLE IF EXISTS term_embeddings;
CREATE TABLE term_embeddings (
    id SERIAL PRIMARY KEY,
    term_name VARCHAR(255) NOT NULL,             -- 术语名称
    term_type VARCHAR(50),                       -- 术语类型: 指标/维度/业务概念
    description TEXT,                            -- 术语描述
    synonyms TEXT[],                             -- 同义词数组
    embedding vector(1024),                      -- 向量嵌入
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_term_embeddings_name 
    ON term_embeddings(term_name);

CREATE INDEX IF NOT EXISTS idx_term_embeddings_vector 
    ON term_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- ============================================
-- 验证安装
-- ============================================
SELECT 'pgvector extension enabled' AS status 
WHERE EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector');

SELECT 'schema_embeddings table created' AS status 
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_embeddings');

SELECT 'term_embeddings table created' AS status 
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'term_embeddings');
