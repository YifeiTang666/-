"""
金融研报生成系统
模块化架构，统一接口
"""

from .config import Config
from .collector import DataCollector
from .generator import ReportGenerator

__version__ = "2.0.0"
__all__ = ["Config", "DataCollector", "ReportGenerator"]

