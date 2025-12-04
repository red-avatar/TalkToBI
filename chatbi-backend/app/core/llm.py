"""
功能：LLM 工厂类 (Infrastructure Layer)
说明：
    1. 单例模式管理 LLM 实例，避免重复连接。
    2. 统一封装 DashScope (通义千问) 和 OpenAI 接口。
    3. 提供 get_llm() 方法，支持动态调整 temperature (如 SQL生成用 0, 闲聊用 0.7)。
作者：CYJ
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
import logging
import httpx
import os

logger = logging.getLogger(__name__)
settings = get_settings()

class LLMFactory:
    _instance = None
    _llm_cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMFactory, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_llm(cls, temperature: float = 0.0, streaming: bool = True) -> ChatOpenAI:
        """
        获取 LLM 实例 (支持缓存)
        
        Args:
            temperature: 随机度 (0.0=精准/SQL生成, 0.7=创意/闲聊)
            streaming: 是否流式输出
        """
        cache_key = f"{temperature}_{streaming}"
        if cache_key in cls._llm_cache:
            return cls._llm_cache[cache_key]

        logger.info(f"Initializing LLM with provider: {settings.LLM_PROVIDER}, temp={temperature}")
        
        # Create HTTP Client with SSL Verification DISABLED
        # This fixes [SSL: CERTIFICATE_VERIFY_FAILED] on Windows/Proxy envs
        http_client = httpx.Client(verify=False)

        if settings.LLM_PROVIDER == "kimi":
            # Kimi (Moonshot AI) 配置
            # Author: CYJ
            api_key = settings.LLM_KEY
            model_name = settings.LLM_MODEL
            base_url = settings.LLM_BASE_URL
            if not api_key:
                raise ValueError("LLM_KEY is not set in .env")
            
            llm = ChatOpenAI(
                model_name=model_name,  # e.g. "kimi-k2-0905-preview"
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=temperature,
                streaming=streaming,
                max_retries=2,
                http_client=http_client
            )
            logger.info(f"Using Kimi model: {model_name}")
        
        elif settings.LLM_PROVIDER == "dashscope":
            # 使用 ChatOpenAI 适配 DashScope
            # DashScope 兼容 OpenAI 协议: base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            if not settings.DASHSCOPE_API_KEY:
                raise ValueError("DASHSCOPE_API_KEY is not set in .env")
            
            llm = ChatOpenAI(
                model_name=settings.DASHSCOPE_CHAT_MODEL,  # e.g. "qwen-plus"
                openai_api_key=settings.DASHSCOPE_API_KEY,
                openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
                temperature=temperature,
                streaming=streaming,
                max_retries=2,
                http_client=http_client
            )
        
        elif settings.LLM_PROVIDER == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not set in .env")
                
            llm = ChatOpenAI(
                model_name="gpt-4o", # 或其他模型
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                temperature=temperature,
                streaming=streaming,
                http_client=http_client
            )
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")

        cls._llm_cache[cache_key] = llm
        return llm

# 全局便捷调用
def get_llm(temperature: float = 0.0, streaming: bool = True) -> ChatOpenAI:
    """
    获取 LLM 实例
    
    Args:
        temperature: 随机度 (0.0=精准/SQL生成, 0.7=创意/闲聊)
        streaming: 是否流式输出（默认True，支持打字机效果）
    
    流式调用示例:
        llm = get_llm(streaming=True)
        async for chunk in llm.astream(messages):
            print(chunk.content)
    """
    return LLMFactory.get_llm(temperature=temperature, streaming=streaming)
