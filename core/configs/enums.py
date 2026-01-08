# core/enums.py
"""
定位：存放系统通用的、静态的基础数据类型和常量。
"""

from enum import IntFlag, IntEnum, Enum, auto


class LogLevel(IntFlag):
    """
    [枚举] 日志级别 (支持位运算组合)
    使用 IntFlag 而不是 IntEnum，是为了支持 LogLevel.INFO | LogLevel.ERROR 这种写法
    """

    NONE = 0
    INFO = auto()  # 1
    WARNING = auto()  # 2
    ERROR = auto()  # 4

    # 预定义组合
    ALL = INFO | WARNING | ERROR  # 7 (开启所有)
    ERRORS_ONLY = ERROR  # 4
    NO_WARNINGS = INFO | ERROR


class EventRule(IntEnum):
    """
    [枚举] 事件处理的基本规则
    (原 EventPolicy)
    """

    NORMAL = 0  # 默认：记录日志 + 执行分发
    SILENT = 1  # 静音：不记日志 + 执行分发 (原 muted)
    DROP = 2  # 丢弃：不记日志 + 不分发 (原 ignored)


class PipelineState(IntEnum):
    """
    [状态机] 管线生命周期状态
    """

    IDLE = 0  # 初始化完成，尚未启动
    RUNNING = 1  # 正在运行 (处理数据)
    PAUSED = 2  # 暂停 (不处理数据，但保留上下文)
    TERMINATED = 3  # 已终止 (资源已释放，不可恢复)


class PipelineMode(IntEnum):
    """
    [模式] 管线运行模式
    """

    SINGLE = 0  # 单次运行：执行一次 step 后自动 TERMINATED
    LOOP = 1  # 循环运行：无限执行 step，直到被手动 Stop
    CONDITIONAL = 2  # 条件触发：平时空转/等待，收到 trigger 信号后执行一次 step


# 信号优先级
class EventPriority(IntEnum):
    DEFERRED = 10  # 默认：帧末处理 (数据同步)
    IMMEDIATE = 20  # 立即执行：逻辑跳转 (状态切换)
    INTERRUPT = 30  # 立即执行 + 中断当前帧 (停止/暂停)
    CRITICAL = 40  # 异常抛出 (严重错误)
