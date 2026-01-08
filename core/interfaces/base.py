# core/interfaces/base.py
import abc

from core.configs.policies import LogPolicy


class ILoggable(abc.ABC):
    """[接口] 可日志化对象"""

    @property
    @abc.abstractmethod
    def log_policy(self) -> LogPolicy: ...

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @abc.abstractmethod
    def set_log_policy(self, policy: LogPolicy): ...
