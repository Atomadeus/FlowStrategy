# core/__init__.py
"""
这是整个 core 包的门面。
为了方便上层应用（如 Application 或 main.py）调用，
可以选择暴露最核心的类，但不要暴露太多以免污染命名空间。
"""

# 暴露 Application 组合根
from .application import Application

# 暴露最常用的日志工具
from .logging import SysLogger

# 暴露常用的工厂（可选，方便快速创建）
from .factories import PipelineFactory, StrategyFactory

__all__ = ["Application", "SysLogger", "PipelineFactory", "StrategyFactory"]
