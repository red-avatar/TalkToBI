-- ============================================================================
-- ChatBI 智能缓存表结构
-- 功能：存储成功执行的查询及其 SQL，用于精确匹配缓存
-- 数据库：chatbi_pg (PostgreSQL with pgvector)
-- 
-- 执行方式：
--   psql -h localhost -U postgres -d chatbi_pg -f create_query_cache.sql
--
-- Author: ChatBI Team
-- Time: 2025-11-28
-- ============================================================================

-- 创建查询缓存表
CREATE TABLE IF NOT EXISTS query_cache (
    id SERIAL PRIMARY KEY,
    
    -- 查询标识
    query_hash VARCHAR(64) NOT NULL UNIQUE,    -- SHA256(原始问题)，用于精确匹配
    
    -- 查询内容
    original_query TEXT NOT NULL,               -- 用户原始问题
    rewritten_query TEXT,                       -- IntentAgent 改写后的问题
    
    -- SQL 相关
    sql TEXT NOT NULL,                          -- 生成的 SQL 语句
    tables_used TEXT[],                         -- 使用的表名列表
    
    -- 缓存质量
    cache_score INT NOT NULL DEFAULT 0,         -- 缓存评分 (0-100)
    hit_count INT NOT NULL DEFAULT 0,           -- 命中次数
    
    -- 状态管理
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active/deprecated/invalid
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_query_cache_hash ON query_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_query_cache_status ON query_cache(status);
CREATE INDEX IF NOT EXISTS idx_query_cache_score ON query_cache(cache_score DESC);
CREATE INDEX IF NOT EXISTS idx_query_cache_hit_count ON query_cache(hit_count DESC);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_query_cache_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_query_cache_updated ON query_cache;
CREATE TRIGGER trigger_query_cache_updated
    BEFORE UPDATE ON query_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_query_cache_timestamp();

-- 添加注释
COMMENT ON TABLE query_cache IS '查询缓存表：存储成功执行的查询及其 SQL';
COMMENT ON COLUMN query_cache.query_hash IS 'SHA256(原始问题)，用于精确匹配';
COMMENT ON COLUMN query_cache.cache_score IS '缓存评分：SQL成功+30, 非空+20, ResultValidator+20, CompletenessValidator+20, PathValidator+10';
COMMENT ON COLUMN query_cache.status IS '状态：active=可用, deprecated=已弃用, invalid=已失效';

-- 验证表创建
SELECT 'query_cache table created successfully' AS result;
