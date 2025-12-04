-- =============================================================================
-- execution_log 表创建脚本
-- 
-- 功能：记录每次查询的执行历史
-- 数据库：PostgreSQL (chatbi_pg)
-- 
-- Author: 陈怡坚
-- Time: 2025-11-29
-- =============================================================================

-- 创建执行记录表
CREATE TABLE IF NOT EXISTS execution_log (
    id SERIAL PRIMARY KEY,
    
    -- 查询信息
    query_text TEXT NOT NULL,                    -- 用户原始问题
    rewritten_query TEXT,                        -- 改写后的问题（IntentAgent处理后）
    sql_generated TEXT,                          -- 生成的 SQL 语句
    tables_used TEXT[],                          -- 涉及的表名数组
    
    -- 执行结果
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 状态: success / error / timeout / pending
    error_message TEXT,                          -- 错误信息（如果有）
    result_row_count INT,                        -- 结果行数
    execution_time_ms INT,                       -- 执行耗时(毫秒)
    
    -- 评分与缓存
    cache_score INT,                             -- 缓存评分 (0-100)
    cache_hit BOOLEAN DEFAULT FALSE,             -- 是否命中缓存
    
    -- 会话信息
    session_id VARCHAR(64),                      -- WebSocket 会话ID
    message_id VARCHAR(64),                      -- 消息ID
    
    -- 预留用户字段（后续登录系统使用）
    user_id VARCHAR(64),                         -- 用户ID
    user_name VARCHAR(100),                      -- 用户名
    
    -- 可视化信息
    chart_type VARCHAR(50),                      -- 图表类型
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 预留扩展字段
    extra_data JSONB                             -- 额外数据（JSON格式，便于扩展）
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_execution_log_status ON execution_log(status);
CREATE INDEX IF NOT EXISTS idx_execution_log_session ON execution_log(session_id);
CREATE INDEX IF NOT EXISTS idx_execution_log_created ON execution_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_log_user ON execution_log(user_id);

-- 添加注释
COMMENT ON TABLE execution_log IS '查询执行记录表 - 记录每次用户查询的完整信息';
COMMENT ON COLUMN execution_log.query_text IS '用户原始问题';
COMMENT ON COLUMN execution_log.rewritten_query IS '改写后的问题';
COMMENT ON COLUMN execution_log.sql_generated IS '生成的SQL语句';
COMMENT ON COLUMN execution_log.tables_used IS '涉及的表名数组';
COMMENT ON COLUMN execution_log.status IS '执行状态: success/error/timeout/pending';
COMMENT ON COLUMN execution_log.cache_score IS '缓存评分(0-100)';
COMMENT ON COLUMN execution_log.cache_hit IS '是否命中缓存';
COMMENT ON COLUMN execution_log.user_id IS '预留用户ID字段';
COMMENT ON COLUMN execution_log.extra_data IS '预留扩展JSON字段';
