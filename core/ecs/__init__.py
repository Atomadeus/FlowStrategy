# core/ecs/__init__.py

# 实体 (Entity)
from .frame import Frame

# 组件基类
from .components import Component

# 标准组件库 (常用)
from .std_components import (
    ImageComponent,
    ActionLogComponent,
    DetectionResultComponent,
    DetectionObject,
)

__all__ = [
    "Frame",
    "Component",
    "ImageComponent",
    "ActionLogComponent",
    "DetectionResultComponent",
    "DetectionObject",
]
