"""
功能：专业名词服务 (Term Service)
说明：
    负责加载和管理业务专业名词，将内部术语翻译为标准表达。
    在 IntentAgent 中注入到提示词，帮助 LLM 理解业务术语。

使用方式：
    term_service = get_term_service()
    prompt_section = term_service.get_terms_prompt()

Author: ChatBI Team
Time: 2025-11-28
"""

import json
import os
import logging
from typing import Dict, List, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class TermService:
    """
    专业名词服务
    
    功能：
    1. 从配置文件加载专业名词
    2. 生成用于提示词的名词列表
    3. 支持热重载（可选）
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化专业名词服务
        
        Args:
            config_path: 配置文件路径，默认为 config/business_terms.json
        """
        if config_path is None:
            # 获取项目根目录
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "business_terms.json")
        
        self.config_path = config_path
        self._terms: Dict[str, dict] = {}
        self._loaded = False
        
        # 初始化时加载
        self._load_terms()
    
    def _load_terms(self) -> None:
        """从配置文件加载专业名词"""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"[TermService] 配置文件不存在: {self.config_path}")
                self._terms = {}
                self._loaded = True
                return
            
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._terms = data.get("terms", {})
            self._loaded = True
            logger.info(f"[TermService] 加载了 {len(self._terms)} 个专业名词")
            
        except json.JSONDecodeError as e:
            logger.error(f"[TermService] 配置文件格式错误: {e}")
            self._terms = {}
            self._loaded = True
        except Exception as e:
            logger.error(f"[TermService] 加载配置文件失败: {e}")
            self._terms = {}
            self._loaded = True
    
    def reload(self) -> None:
        """重新加载配置文件（热重载）"""
        logger.info("[TermService] 重新加载专业名词配置...")
        self._load_terms()
    
    def get_terms(self) -> Dict[str, dict]:
        """
        获取所有专业名词
        
        Returns:
            Dict[str, dict]: 专业名词字典
        """
        return self._terms
    
    def get_term(self, name: str) -> Optional[dict]:
        """
        获取单个专业名词的定义
        
        Args:
            name: 名词名称
            
        Returns:
            名词定义或 None
        """
        return self._terms.get(name)
    
    def get_terms_prompt(self) -> str:
        """
        生成用于 IntentAgent 提示词的名词列表
        
        Returns:
            格式化的名词列表字符串，可直接注入到提示词中
        """
        if not self._terms:
            return ""
        
        lines = ["### 公司专业术语（请在理解用户问题时参考）"]
        
        for term_name, term_info in self._terms.items():
            meaning = term_info.get("meaning", "")
            sql_hint = term_info.get("sql_hint", "")
            
            line = f"- **{term_name}**: {meaning}"
            if sql_hint:
                line += f"（SQL提示: {sql_hint}）"
            lines.append(line)
        
        return "\n".join(lines)
    
    def get_terms_for_display(self) -> List[dict]:
        """
        获取用于前端展示的名词列表
        
        Returns:
            List[dict]: 名词列表，包含 name, meaning, sql_hint, examples
        """
        result = []
        for name, info in self._terms.items():
            result.append({
                "name": name,
                "meaning": info.get("meaning", ""),
                "sql_hint": info.get("sql_hint", ""),
                "examples": info.get("examples", [])
            })
        return result
    
    @property
    def count(self) -> int:
        """获取专业名词数量"""
        return len(self._terms)
    
    # ========== 以下为管理接口新增方法 (Author: CYJ, Time: 2025-11-29) ==========
    
    def _save_terms(self) -> bool:
        """
        保存专业名词到文件
        
        Author: CYJ
        Time: 2025-11-29
        """
        try:
            data = {"terms": self._terms}
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[TermService] 保存成功: {len(self._terms)} 个名词")
            return True
        except Exception as e:
            logger.error(f"[TermService] 保存失败: {e}")
            return False
    
    def add_term(
        self,
        name: str,
        meaning: str,
        sql_hint: Optional[str] = None,
        examples: Optional[List[str]] = None
    ) -> bool:
        """
        添加专业名词
        
        Args:
            name: 名词名称
            meaning: 含义解释
            sql_hint: SQL提示
            examples: 示例列表
            
        Returns:
            是否添加成功
            
        Author: CYJ
        Time: 2025-11-29
        """
        if name in self._terms:
            logger.warning(f"[TermService] 名词已存在: {name}")
            return False
        
        self._terms[name] = {
            "meaning": meaning,
            "sql_hint": sql_hint or "",
            "examples": examples or []
        }
        
        return self._save_terms()
    
    def update_term(
        self,
        name: str,
        meaning: Optional[str] = None,
        sql_hint: Optional[str] = None,
        examples: Optional[List[str]] = None
    ) -> bool:
        """
        更新专业名词
        
        Author: CYJ
        Time: 2025-11-29
        """
        if name not in self._terms:
            logger.warning(f"[TermService] 名词不存在: {name}")
            return False
        
        if meaning is not None:
            self._terms[name]["meaning"] = meaning
        if sql_hint is not None:
            self._terms[name]["sql_hint"] = sql_hint
        if examples is not None:
            self._terms[name]["examples"] = examples
        
        return self._save_terms()
    
    def delete_term(self, name: str) -> bool:
        """
        删除专业名词
        
        Author: CYJ
        Time: 2025-11-29
        """
        if name not in self._terms:
            logger.warning(f"[TermService] 名词不存在: {name}")
            return False
        
        del self._terms[name]
        return self._save_terms()
    
    def get_terms_list(self) -> List[dict]:
        """
        获取名词列表（API用）
        
        Returns:
            包含 name, meaning, sql_hint, examples 的字典列表
            
        Author: CYJ
        Time: 2025-11-29
        """
        result = []
        for name, info in self._terms.items():
            result.append({
                "name": name,
                "meaning": info.get("meaning", ""),
                "sql_hint": info.get("sql_hint", ""),
                "examples": info.get("examples", [])
            })
        return result


# 单例模式
_term_service_instance: Optional[TermService] = None


def get_term_service() -> TermService:
    """
    获取 TermService 单例
    
    Returns:
        TermService 实例
    """
    global _term_service_instance
    if _term_service_instance is None:
        _term_service_instance = TermService()
    return _term_service_instance
