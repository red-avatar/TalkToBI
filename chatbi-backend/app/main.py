import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.health import check_mysql, check_postgres, check_neo4j, check_llm
from app.api.v1.endpoints import graph_builder, chat, ws_chat
# Phase 6: 后端管理 API (Author: CYJ, Time: 2025-11-29)
from app.api.v1 import cache, terms, vectors, logs, auth

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stdout
)
# 设置第三方库日志级别，避免过多输出
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(graph_builder.router, prefix=f"{settings.API_V1_STR}")
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}")  # V7: HTTP 对话 API
app.include_router(ws_chat.router, prefix=f"{settings.API_V1_STR}")  # V7: WebSocket 对话 API

# Phase 6: 后端管理 API (Author: CYJ, Time: 2025-11-29)
app.include_router(cache.router, prefix=f"{settings.API_V1_STR}")    # 缓存管理
app.include_router(terms.router, prefix=f"{settings.API_V1_STR}")    # 专业名词管理
app.include_router(vectors.router, prefix=f"{settings.API_V1_STR}") # 向量管理
app.include_router(logs.router, prefix=f"{settings.API_V1_STR}")     # 执行记录
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}")     # 认证管理

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify service status and dependencies.
    """
    results = {
        "mysql": await check_mysql(),
        "vector_db": await check_postgres(), # Note: current impl is sync
        "neo4j": await check_neo4j(),        # Note: current impl is sync
        "llm": await check_llm()
    }
    
    # Determine overall status
    # If any critical service fails (e.g., MySQL), status could be 'degraded'
    overall_status = "ok"
    if any(str(v).startswith("failed") for v in results.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "dependencies": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.SERVER_HOST, 
        port=settings.SERVER_PORT
    )
