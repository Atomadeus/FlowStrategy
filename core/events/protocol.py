# core/protocol.py
"""
通信的归宿
定位：存放动态流转的数据契约（Contract）。它定义的是“A 发给 B 的信长什么样”。
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


# --- 事件类型定义 ---
class SystemEvent(str, Enum):
    """
    [枚举] 全局事件主题定义
    继承 str 使得 SystemEvent.PIPELINE_CONTROL == "PIPELINE_CONTROL" 成立，
    可以直接作为 EventBus 的 key 使用，无需 .value
    """

    PIPELINE_CONTROL = "PIPELINE_CONTROL"  # 管线控制 (Stop/Pause)
    SYSTEM_ALERT = "SYSTEM_ALERT"  # 系统警报 (Error/Warning)
    FRAME_PROCESSED = "FRAME_PROCESSED"  # 帧处理完成通知


# --- 错误码枚举 ---
class ErrorCode(str, Enum):
    """
    [枚举] 标准化错误码
    使用字符串值方便序列化和日志阅读
    """

    # 通用类
    GENERIC_ERROR = "GENERIC_ERROR"
    INIT_FAILED = "INIT_FAILED"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"

    # 资源/硬件类
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DEVICE_OPEN_FAILED = "DEVICE_OPEN_FAILED"
    VIDEO_SIGNAL_LOSS = "VIDEO_SIGNAL_LOSS"  # 视频信号丢失 (黑屏/断流)

    # 性能类
    PERFORMANCE_DEGRADED = "PERFORMANCE_DEGRADED"  # 帧率过低
    MEMORY_WARNING = "MEMORY_WARNING"

    # AI 模型类
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    INFERENCE_ERROR = "INFERENCE_ERROR"


# --- 警报级别枚举 ---
class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# --- 载荷契约 (Dataclasses) ---
@dataclass
class SystemAlertPayload:
    """
    [v3.0 标准] 系统警报载荷
    """

    level: AlertLevel
    error_code: ErrorCode  # <--- [核心修改] 强制使用枚举
    source: str  # 发出警报的组件名称 (e.g. "OBSCapture_0")
    message: str  # 人类可读的消息
    details: Dict[str, Any] = field(default_factory=dict)  # 附带现场数据

    def to_dict(self):
        """序列化辅助"""
        return {
            "level": self.level.value,
            "error_code": self.error_code.value,
            "source": self.source,
            "message": self.message,
            "details": self.details,
        }


class PipelineControlCommand(Enum):
    """
    [枚举] 定义所有支持的控制指令
    """

    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    RESTART = "RESTART"


@dataclass
class PipelineControlPayload:
    """
    [数据类] 标准化的控制信号载荷
    """

    command: PipelineControlCommand  # 强制使用枚举，杜绝魔法字符串
    target_pipeline_name: str  # 目标管线名称，或者 "ALL"
    reason: str = "Unknown"  # 原因描述
    extra_data: dict = field(default_factory=dict)  # 预留扩展字段

    def to_dict(self):
        """方便序列化（如果EventBus需要JSON格式）"""
        return {
            "command": self.command.value,
            "target_pipeline_name": self.target_pipeline_name,
            "reason": self.reason,
            "extra_data": self.extra_data,
        }
