from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv
import os

# Explicitly load .env from project root if not loaded
# Author: CYJ (Fixed: 2025-11-29)
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(base_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)  # override=True 确保加载到环境变量
else:
    load_dotenv()

class Settings(BaseSettings):
    """
    ChatBI 全局配置
    
    配置优先级: 环境变量 > .env 文件 > 默认值
    
    Author: CYJ
    """
    
    # ===========================================
    # 项目基础配置
    # ===========================================
    PROJECT_NAME: str = "ChatBI Backend"    # 项目名称，用于 API 文档标题
    VERSION: str = "0.1.0"                  # 版本号
    API_V1_STR: str = "/api/v1"             # API 版本前缀
    
    # ===========================================
    # 服务器配置
    # ===========================================
    SERVER_HOST: str = "0.0.0.0"            # 监听地址，0.0.0.0 表示所有网卡
    SERVER_PORT: int = 8000                 # 监听端口
    
    # ===========================================
    # MySQL 数据库配置
    # 用途: 存储业务数据，BI 查询的数据源
    # ===========================================
    MYSQL_HOST: str = "localhost"           # MySQL 主机地址
    MYSQL_PORT: int = 3306                  # MySQL 端口
    MYSQL_USER: str = "root"                # MySQL 用户名
    MYSQL_PASSWORD: str = ""                # MySQL 密码
    MYSQL_DB: str = "chatbi"                # 数据库名
    
    # ===========================================
    # 系统数据库配置 (MySQL)
    # 用途: 存储用户、登录日志等系统数据
    # Author: CYJ
    # Time: 2025-12-03
    # ===========================================
    SYS_DB_HOST: str = "localhost"          # 系统数据库主机
    SYS_DB_PORT: int = 3306                 # 系统数据库端口
    SYS_DB_USER: str = "root"               # 系统数据库用户名
    SYS_DB_PASSWORD: str = ""               # 系统数据库密码
    SYS_DB_NAME: str = "chatbi_sys"         # 系统数据库名
    
    # ===========================================
    # PostgreSQL 向量数据库配置 (pgvector)
    # 用途: 存储 Schema 嵌入向量，支持语义检索
    # ===========================================
    VECTOR_DB_HOST: str = "localhost"       # PostgreSQL 主机地址
    VECTOR_DB_PORT: int = 5432              # PostgreSQL 端口
    VECTOR_DB_USER: str = "postgres"        # PostgreSQL 用户名
    VECTOR_DB_PASSWORD: str = ""            # PostgreSQL 密码
    VECTOR_DB_NAME: str = "chatbi_pg"       # 数据库名
    
    # ===========================================
    # Neo4j 图数据库配置
    # 用途: 存储知识图谱，表与表关系、业务概念等
    # ===========================================
    NEO4J_URI: str = "bolt://localhost:7687"  # Neo4j 连接 URI
    NEO4J_USER: str = "neo4j"               # Neo4j 用户名
    NEO4J_PASSWORD: str = ""                # Neo4j 密码
    
    # ===========================================
    # LLM 大模型配置
    # ===========================================
    LLM_PROVIDER: str = "kimi"              # LLM 提供商: 'dashscope' | 'openai' | 'kimi'
    
    # Kimi (Moonshot AI) 配置
    # Author: CYJ
    # Time: 2025-11-28
    LLM_KEY: str = ""                       # Kimi API Key
    LLM_MODEL: str = "kimi-k2-0905-preview" # Kimi 模型名称
    LLM_BASE_URL: str = "https://api.moonshot.cn/v1"  # Kimi API 基址
    
    # ===========================================
    # Embedding 向量模型配置（独立于 LLM）
    # Author: CYJ
    # Time: 2025-11-28
    # ===========================================
    EMBEDDING_PROVIDER: str = "dashscope"   # 向量模型提供商: 'dashscope' | 'openai' | 'jina'
    
    # 阿里云通义千问配置 (DashScope)
    DASHSCOPE_API_KEY: str = ""             # API Key，从阿里云控制台获取
    DASHSCOPE_CHAT_MODEL: str = "qwen-plus" # 对话模型: qwen-turbo/qwen-plus/qwen-max
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v4"  # 向量模型（推荐 v4）
    
    # OpenAI 配置（备用）
    OPENAI_API_KEY: str = ""                # OpenAI API Key
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"  # API 基址址，可改为代理
    
    # ===========================================
    # WebSocket / 对话配置
    # Author: CYJ
    # Time: 2025-11-26
    # ===========================================
    
    # 会话管理
    CHAT_SESSION_EXPIRE_SECONDS: int = 3600     # 会话过期时间(秒)，超时无活动则清理
    CHAT_STORAGE_TYPE: str = "memory"           # 会话存储类型: 'memory' | 'redis'
    
    # 消息限制
    CHAT_MESSAGE_MAX_LENGTH: int = 500          # 单条消息最大长度(字符)
    CHAT_MAX_CONCURRENT_REQUESTS: int = 10      # 每个用户最大并发请求数
    
    # WebSocket 连接配置
    # V3: 禁用自动 ping，避免 LLM 调用期间超时断开
    # 设为 0 表示禁用自动 ping，连接会一直保持直到有数据传输或手动关闭
    WS_PING_INTERVAL: int = 0                   # ping 发送间隔(秒)，0=禁用自动ping
    WS_PING_TIMEOUT: int = 0                    # 等待 pong 超时(秒)，0=不超时
    WS_CLOSE_TIMEOUT: int = 10                  # 关闭连接超时(秒)
    
    # 应用层心跳（上层逻辑，非 WebSocket 协议层）
    WS_HEARTBEAT_INTERVAL: int = 30             # 心跳间隔(秒)，客户端发 ping 的频率
    WS_HEARTBEAT_TIMEOUT: int = 90              # 心跳超时(秒)，无响应则重连
    
    # ===========================================
    # 连接与限流配置
    # Author: CYJ
    # Time: 2025-12-03
    # ===========================================
    WS_MAX_CONNECTIONS: int = 5                  # WebSocket 最大连接数
    LLM_MAX_CONCURRENT_CALLS: int = 10           # LLM 最大并发调用数
    
    # ===========================================
    # LLM 温度配置
    # Author: CYJ
    # Time: 2025-11-28
    # ===========================================
    # 精确任务（意图识别、SQL生成、分析等）使用低温度
    LLM_TEMPERATURE_PRECISE: float = 0.0
    # 创意任务（闲聊、文案生成等）使用较高温度
    LLM_TEMPERATURE_CREATIVE: float = 0.7
    # 查询扩展等中等创意任务
    LLM_TEMPERATURE_BALANCED: float = 0.3
    # 响应生成（解释查询结果等）使用中等温度
    LLM_TEMPERATURE_RESPONSE: float = 0.5
    
    # ===========================================
    # 检索配置 (Retrieval)
    # Author: CYJ
    # Time: 2025-11-28
    # ===========================================
    # 向量检索相似度阈值
    RETRIEVAL_HIGH_THRESHOLD: float = 0.55      # 高精度模式
    RETRIEVAL_MEDIUM_THRESHOLD: float = 0.50    # 中等精度
    RETRIEVAL_LOW_THRESHOLD: float = 0.45       # 低精度回退
    # 混合检索向量权重
    RETRIEVAL_VECTOR_WEIGHT: float = 0.4
    # 默认返回结果数
    RETRIEVAL_DEFAULT_TOP_K: int = 10
    
    # ===========================================
    # 缓存配置 (Cache)
    # Author: CYJ
    # Time: 2025-11-28
    # ===========================================
    # 缓存评分阈值（分数 >= 该值才保存到缓存）
    CACHE_SCORE_THRESHOLD: int = 80
    
    # ===========================================
    # 调试模式
    # Author: CYJ
    # Time: 2025-11-26
    # ===========================================
    # 开发环境设为 true，生产环境设为 false
    # 调试模式下会返回: SQL语句、完整查询结果、中间状态等
    DEBUG_MODE: bool = True
    
    class Config:
        # 禁用 pydantic 的 env_file，依赖上方 load_dotenv 加载的环境变量
        # Author: CYJ
        # Time: 2025-11-29
        env_file = None
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
