"""
配置管理模块 - 统一管理所有配置
"""

import os
from dataclasses import dataclass
from dotenv import (
    load_dotenv,
)  # 用来：从 .env 文件加载环境变量到 os.environ，让你能用 os.getenv() 读取。
from typing import Optional
import re

# 加载环境变量（支持从项目根目录和当前目录查找.env文件）
env_paths = [
    os.path.join(os.path.dirname(__file__), "..", ".env"),  # 项目根目录
    os.path.join(os.path.dirname(__file__), ".env"),  # 当前目录
    ".env",  # 当前工作目录
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        break
else:
    # 如果找不到.env文件，尝试从默认位置加载
    load_dotenv()


def _get_env(key: str, default: str = "") -> str:
    """
    获取环境变量，自动去除引号

    Args:
        key: 环境变量键名
        default: 默认值

    Returns:
        处理后的环境变量值
    """
    value = os.getenv(key, default)  # 从环境变量中取值，如没取到返回 default
    if value:
        # 去除首尾的引号（单引号或双引号）
        value = value.strip().strip('"').strip("'")
    return value


@dataclass
class LLMConfig:
    """LLM配置"""

    api_key: str = "sk-d6f43c8f94fc4c3ebf8e765494d25fba"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-reasoner"
    temperature: float = 0.7
    max_tokens: int = 16384

    def __post_init__(self):
        """初始化后处理，确保配置有效"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 未设置，请在.env文件中配置")

        # 去除可能的引号
        self.api_key = self.api_key.strip('"').strip("'")
        self.base_url = self.base_url.strip('"').strip("'")
        self.model = self.model.strip('"').strip("'")

        # 验证base_url格式
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"无效的 OPENAI_BASE_URL: {self.base_url}")


@dataclass
class Config:
    """系统配置"""

    # LLM配置
    llm: LLMConfig

    # 目标公司配置
    target_company: str = "商汤科技"
    target_company_code: str = "00020"
    target_company_market: str = "HK"

    # 目录配置
    data_dir: str = "./data"
    financial_dir: str = "./data/financial"
    company_dir: str = "./data/company"
    industry_dir: str = "./data/industry"
    output_dir: str = "./outputs"

    # 搜索引擎配置
    search_engine: str = "sogou"

    # 分析配置
    max_analysis_rounds: int = 20
    search_delay: int = 20  # 搜索延迟（秒）
    max_retries: int = 3  # 最大重试次数

    @classmethod
    def from_env(
        cls,
        target_company: str = "商汤科技",
        target_company_code: str = "00020",
        target_company_market: str = "HK",
    ) -> "Config":
        """
        从环境变量创建配置

        Args:
            target_company: 目标公司名称
            target_company_code: 股票代码
            target_company_market: 市场类型 (HK/A)

        Returns:
            Config对象

        Raises:
            ValueError: 如果必需的环境变量未设置
        """
        # 读取LLM配置（优先使用环境变量，如果没有则使用默认值）
        # 默认配置：DeepSeek API
        api_key = _get_env("OPENAI_API_KEY", "sk-d6f43c8f94fc4c3ebf8e765494d25fba")
        base_url = _get_env("OPENAI_BASE_URL", "https://api.deepseek.com")
        model = _get_env("OPENAI_MODEL", "deepseek-reasoner")
        temperature = float(_get_env("OPENAI_TEMPERATURE", "0.7"))
        max_tokens = int(_get_env("OPENAI_MAX_TOKENS", "16384"))

        # 创建LLM配置
        llm_config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 创建系统配置
        config = cls(
            llm=llm_config,
            target_company=target_company,
            target_company_code=target_company_code,
            target_company_market=target_company_market,
            search_engine=_get_env("SEARCH_ENGINE", "sogou"),
        )

        # 创建必要的目录
        for dir_path in [
            config.financial_dir,
            config.company_dir,
            config.industry_dir,
            config.output_dir,
        ]:
            os.makedirs(dir_path, exist_ok=True)

        # 打印配置信息（隐藏敏感信息）
        print(f"✅ 配置加载成功")
        print(f"   LLM模型: {config.llm.model}")
        print(f"   API地址: {config.llm.base_url}")
        print(
            f"   API密钥: {'*' * 20}...{config.llm.api_key[-4:] if len(config.llm.api_key) > 4 else '****'}"
        )
        print(
            f"   目标公司: {config.target_company} ({config.target_company_market}:{config.target_company_code})"
        )
        print(f"   搜索引擎: {config.search_engine}")

        return config
