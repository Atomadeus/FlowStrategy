# core/interfaces/__init__.py

# 基础接口
from .base import ILoggable

# ECS 核心接口
from .ecs import (
    IFrame,
    IStrategy,
    # 如果有定义泛型 T 或 Component 标记接口，也可以在这里导出
)

# 管线相关接口
from .pipeline import (
    IPipeline,
    IPipelineConfig,
    IPipelineContext,
    IPipelineLayout,
    IPipelineAware,
    IPipelineExecutor,
    RouterFactory,  # 类型别名
)

# 事件系统接口
from .event import (
    IEventHub,
    IEventRouter,
    EventType,  # 类型别名
)

__all__ = [
    "ILoggable",
    "IFrame",
    "IStrategy",
    "IPipeline",
    "IPipelineConfig",
    "IPipelineContext",
    "IPipelineLayout",
    "IPipelineAware",
    "IPipelineExecutor",
    "RouterFactory",
    "IEventHub",
    "IEventRouter",
    "EventType",
]
