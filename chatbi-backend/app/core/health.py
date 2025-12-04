import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from neo4j import GraphDatabase
import httpx
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

async def check_mysql() -> str:
    """Check connection to MySQL database."""
    try:
        # Use aiomysql for async connection
        user = settings.MYSQL_USER
        pwd = settings.MYSQL_PASSWORD
        host = settings.MYSQL_HOST
        port = settings.MYSQL_PORT
        dbname = settings.MYSQL_DB
        url = "mysql+aiomysql://{}:{}@{}:{}/{}".format(user, pwd, host, port, dbname)
        engine = create_async_engine(url, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return "connected"
    except Exception as e:
        logger.error(f"MySQL check failed: {e}")
        return f"failed: {str(e)}"

async def check_postgres() -> str:
    """Check connection to PostgreSQL (Vector DB)."""
    try:
        # Assuming aiopg or asyncpg is installed, or stick to standard sync check if needed.
        # Requirements lists psycopg2-binary, but not asyncpg.
        # Let's use sync connection for simplicity or verify if we strictly need async.
        # Since requirements.txt has 'sqlalchemy' and 'psycopg2-binary', standard sync engine is safer unless 'asyncpg' is added.
        # Wait, requirements has `aiomysql` but not `asyncpg`.
        # For safety in this async endpoint, we should probably use run_in_threadpool for sync drivers or just add asyncpg.
        # Given Phase 1 context, let's try standard sync sqlalchemy for now inside a try/except block, 
        # but to not block the loop, we should ideally use async.
        # For now, let's use a simple socket check or lightweight connection.
        
        # Simplified: Construct URL for SQLAlchemy (Sync)
        from sqlalchemy import create_engine
        # url construction
        url = "postgresql://{}:{}@{}:{}/{}".format(
            settings.VECTOR_DB_USER,
            settings.VECTOR_DB_PASSWORD,
            settings.VECTOR_DB_HOST,
            settings.VECTOR_DB_PORT,
            settings.VECTOR_DB_NAME
        )
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception as e:
        logger.error(f"PostgreSQL check failed: {e}")
        return f"failed: {str(e)}"

async def check_neo4j() -> str:
    """Check connection to Neo4j."""
    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        # Verify connectivity
        driver.verify_connectivity()
        driver.close()
        return "connected"
    except Exception as e:
        logger.error(f"Neo4j check failed: {e}")
        return f"failed: {str(e)}"

async def check_llm() -> str:
    """Check connection to LLM provider."""
    try:
        # 根据 LLM_PROVIDER 选择对应的 key 和 base_url
        provider = settings.LLM_PROVIDER.lower()
        
        if provider == "kimi":
            api_key = settings.LLM_KEY
            base_url = settings.LLM_BASE_URL
        elif provider == "dashscope":
            api_key = settings.DASHSCOPE_API_KEY
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        else:  # openai or others
            api_key = settings.OPENAI_API_KEY
            base_url = settings.OPENAI_BASE_URL
        
        if not api_key:
            return f"skipped (no key for {provider})"
            
        async with httpx.AsyncClient() as client:
            url = f"{base_url}/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            response = await client.get(url, headers=headers, timeout=5.0)
            if response.status_code in [200, 401, 403]:
                return f"reachable ({provider})"
            return f"unreachable (status {response.status_code})"
    except Exception as e:
        logger.error(f"LLM check failed: {e}")
        return f"failed: {str(e)}"
