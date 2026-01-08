# core/interfaces/event.py
import abc
from enum import Enum
from typing import Any, Type, Union, Callable

from core.configs.enums import EventPriority
from core.configs.policies import EventPolicy
from core.interfaces.base import ILoggable

# [新增] 定义事件主题类型
# 允许三种形式作为“频道名”：
# 1. str: "SystemAlert" (不推荐，容易拼错，但为了兼容性保留)
# 2. Enum: EventType.PIPELINE_CONTROL (推荐用于全局控制)
# 3. Type: BallDetectedEvent (推荐用于携带复杂数据的局部事件)
EventType = Union[str, Enum, Type[Any]]


class IEventHub(ILoggable):
    """
    [接口] 全局事件枢纽
    """

    @abc.abstractmethod
    def subscribe(self, event_type: Any, callback: Callable): ...

    @abc.abstractmethod
    def publish(self, event_type: Any, data: Any = None): ...

    @abc.abstractmethod
    def clear(self): ...


class IEventRouter(ILoggable):
    """
    [接口] 事件路由器契约，
    Pipeline 只依赖这个接口，而不依赖具体实现。
    """

    @abc.abstractmethod
    def set_pipeline(self, pipeline: Any):
        """
        注入所属 Pipeline (通常在工厂创建或初始化时调用)，
        用于依赖注入后的延迟绑定 (Setter Injection)。
        """
        ...

    @abc.abstractmethod
    def set_log_policy(self, policy): ...

    @abc.abstractmethod
    def set_event_policy(self, event_type: Type, policy: EventPolicy):
        """设置事件处理规则"""
        ...

    @abc.abstractmethod
    def subscribe(self, event_type: Type, callback: Callable): ...

    @abc.abstractmethod
    def publish(
        self,
        event_type: Type,
        data: Any = None,
        sender: Any = None,
        priority: EventPriority = EventPriority.DEFERRED,
    ): ...

    @abc.abstractmethod
    def process_deferred(self): ...
