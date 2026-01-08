from dataclasses import dataclass

from core.configs.enums import LogLevel, EventRule

# ==========================================
# 日志相关数据结构
# ==========================================


@dataclass(frozen=True)
class LogPolicy:
    """
    [LogPolicy] 日志策略值对象
    原 ILogPolicy 接口与其实现合并，直接作为一个不可变的数据对象使用。
    """

    allowed_mask: LogLevel

    def is_allowed(self, level: LogLevel) -> bool:
        """检查特定级别是否允许通过"""
        if self.allowed_mask == LogLevel.ALL:
            return True
        if self.allowed_mask == LogLevel.NONE:
            return False
        # 使用位运算检查掩码
        return bool(self.allowed_mask & level)

    @classmethod
    def default(cls) -> "LogPolicy":
        return cls(allowed_mask=LogLevel.ALL)

    @classmethod
    def silent(cls) -> "LogPolicy":
        return cls(allowed_mask=LogLevel.NONE)

    @classmethod
    def infos_only(cls) -> "LogPolicy":
        return cls(allowed_mask=LogLevel.INFO)

    @classmethod
    def warnings_only(cls) -> "LogPolicy":
        return cls(allowed_mask=LogLevel.WARNING)

    @classmethod
    def errors_only(cls) -> "LogPolicy":
        return cls(allowed_mask=LogLevel.ERROR)


@dataclass(frozen=True)
class EventPolicy:
    """
    [EventPolicy] 事件策略值对象
    包装了底层的 EventRule，提供语义化的工厂方法。
    """

    rule: EventRule

    # --- 辅助判断方法 (类似 LogPolicy.is_allowed) ---

    @property
    def is_mute(self) -> bool:
        return self.rule == EventRule.SILENT or self.rule == EventRule.DROP

    @property
    def is_dropped(self) -> bool:
        return self.rule == EventRule.DROP

    # --- 工厂方法 (Factory Methods) ---

    @classmethod
    def normal(cls) -> "EventPolicy":
        """标准模式：记录日志且分发"""
        return cls(rule=EventRule.NORMAL)

    @classmethod
    def silent(cls) -> "EventPolicy":
        """静音模式：仅分发，不写日志 (适合高频事件如 MouseMove)"""
        return cls(rule=EventRule.SILENT)

    @classmethod
    def drop(cls) -> "EventPolicy":
        """丢弃模式：完全忽略 (适合禁用某些功能)"""
        return cls(rule=EventRule.DROP)
