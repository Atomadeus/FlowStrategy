# core/configs/__init__.py

# 基础枚举
from .enums import (
    LogLevel,
    EventRule,
    PipelineState,
    PipelineMode,
    EventPriority,
)

# 静态配置 (原 structs.py 中的 PipelineConfig)
from .settings import PipelineConfig

# 策略值对象
from .policies import (
    LogPolicy,
    EventPolicy,
)

__all__ = [
    "LogLevel",
    "EventRule",
    "PipelineState",
    "PipelineMode",
    "EventPriority",
    "PipelineConfig",
    "LogPolicy",
    "EventPolicy",
]
