# core/logging/logger.py
import logging
import threading
from typing import Optional, Union
from core.interfaces import ILoggable
from core.configs.enums import LogLevel

# 配置底层 Python Logging (只配置一次)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
_internal_logger = logging.getLogger("System")


# class LogPolicyFactory:
#     """
#     [工厂] 生产常用的日志策略
#     """

#     @staticmethod
#     def create_default() -> LogPolicy:
#         return LogPolicy(allowed_mask=LogLevel.ALL)

#     @staticmethod
#     def create_silent() -> LogPolicy:
#         return LogPolicy(allowed_mask=LogLevel.NONE)

#     @staticmethod
#     def create_errors_only() -> LogPolicy:
#         return LogPolicy(allowed_mask=LogLevel.ERROR)

#     @staticmethod
#     def create_verbose() -> LogPolicy:
#         return LogPolicy(allowed_mask=LogLevel.ALL)

#     @staticmethod
#     def create_custom(mask: LogLevel) -> LogPolicy:
#         """创建自定义策略，例如：LogLevel.INFO | LogLevel.ERROR"""
#         return LogPolicy(allowed_mask=mask)


class SysLogger:
    """
    [系统日志核心] 静态单例类
    职责：接收日志请求 -> 获取调用源的策略 -> 决定是否打印
    """

    _lock = threading.Lock()

    @classmethod
    def critical(cls, message: str):
        """系统级致命错误，不受策略限制，强制打印"""
        _internal_logger.critical(f"[SYSTEM] {message}")

    @staticmethod
    def _get_name(source: Union[ILoggable, str]) -> str:
        if isinstance(source, ILoggable):
            return source.name
        return str(source)

    @classmethod
    def info(cls, source: Union[ILoggable, str], message: str):
        # 传递 LogLevel.INFO 枚举
        if cls._should_log(source, LogLevel.INFO):
            name = cls._get_name(source)
            _internal_logger.info(f"[{name}] {message}")

    @classmethod
    def warning(cls, source: Union[ILoggable, str], message: str):
        if cls._should_log(source, LogLevel.WARNING):
            name = cls._get_name(source)
            _internal_logger.warning(f"[{name}] {message}")

    @classmethod
    def error(cls, source: Union[ILoggable, str], message: str):
        if cls._should_log(source, LogLevel.ERROR):
            name = cls._get_name(source)
            _internal_logger.error(f"[{name}] {message}")

    @staticmethod
    def _should_log(source: Union[ILoggable, str], level: LogLevel) -> bool:
        # 情况 A: 传入的是字符串 (例如 "Main")
        # 既然它是字符串，它就没有 log_policy 属性。
        # 我们默认认为这种日志是必须要打印的 (直通)。
        if not isinstance(source, ILoggable):
            return True

        # 情况 B: 传入的是策略对象 (例如 YoloDetectionStrategy 实例)
        # 我们必须尊重该对象配置的策略 (过滤)。
        # 直接调用 Policy 的 is_allowed 方法
        return source.log_policy.is_allowed(level)
