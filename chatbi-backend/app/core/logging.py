"""
ChatBI 统一日志配置

使用方式:
    from app.core.logging import setup_logging
    setup_logging(debug=False)

Author: CYJ
"""
import logging
import sys
from typing import Optional

def setup_logging(
    debug: bool = False,
    log_format: Optional[str] = None,
    date_format: Optional[str] = None
) -> None:
    """
    配置全局日志
    
    Args:
        debug: 是否开启调试模式（DEBUG 级别）
        log_format: 自定义日志格式（可选）
        date_format: 自定义日期格式（可选）
        
    Author: CYJ
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # 默认格式：带时间戳、级别、模块名
    default_format = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    default_date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=level,
        format=log_format or default_format,
        datefmt=date_format or default_date_format,
        stream=sys.stdout,
        force=True  # Python 3.8+，强制重新配置
    )
    
    # 降低第三方库的日志级别，避免过多输出
    noisy_loggers = [
        "httpx",
        "httpcore",
        "urllib3",
        "langchain",
        "langchain_core",
        "langchain_community",
        "websockets",
        "neo4j",
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # 设置 root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    logging.info(f"日志已配置: level={'DEBUG' if debug else 'INFO'}")

def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger
    
    这是一个便捷函数，等同于 logging.getLogger(name)
    
    Args:
        name: logger 名称，通常使用 __name__
        
    Returns:
        Logger 实例
        
    Author: CYJ
    """
    return logging.getLogger(name)
