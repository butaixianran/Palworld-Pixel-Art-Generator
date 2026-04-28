"""
配置模块入口
导出全局配置管理器单例，方便其他模块直接引用。
"""

from .config_manager import ConfigManager, config_manager

__all__ = ["ConfigManager", "config_manager"]
