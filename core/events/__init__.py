# core/events/__init__.py

# 基础设施实现
from .hub import EventHub
from .router import EventRouter

# 通信协议 (Protocol)
# 注意：为了方便，通常也把 SystemEvent 等协议定义直接暴露在这里
from .protocol import (
    SystemEvent,
    SystemAlertPayload,
    PipelineControlCommand,
    PipelineControlPayload,
    ErrorCode,
    AlertLevel,
)

__all__ = [
    "EventHub",
    "EventRouter",
    "SystemEvent",
    "SystemAlertPayload",
    "PipelineControlCommand",
    "PipelineControlPayload",
    "ErrorCode",
    "AlertLevel",
]
