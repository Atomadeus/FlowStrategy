# core/interfaces/pipeline.py
import abc
from typing import List, Dict, Tuple, Optional, Any, TypeVar, Callable

from core.configs.enums import PipelineMode, PipelineState
from core.configs.policies import EventPolicy
from core.ecs.components import Component
from core.interfaces.base import ILoggable
from core.interfaces.ecs import IStrategy
from core.interfaces.event import IEventRouter

# 定义泛型 T，用于 get_component 的智能提示
T = TypeVar("T", bound=Component)

# 前向引用类型别名 (解决依赖注入的类型提示)
RouterFactory = Callable[["IPipeline"], "IEventRouter"]


class IPipelineLayout(abc.ABC):
    """管线布局接口"""

    @property
    @abc.abstractmethod
    def index_to_name(self) -> Dict[int, str]: ...

    @property
    @abc.abstractmethod
    def name_to_index(self) -> Dict[str, List[int]]: ...

    @property
    @abc.abstractmethod
    def ordered_items(self) -> List[Tuple[int, str]]: ...


class IPipeline(ILoggable):
    """
    [World/Manager] 管线接口
    """

    # 属性
    @property
    @abc.abstractmethod
    def strategies(self) -> List[IStrategy]: ...

    @property
    @abc.abstractmethod
    def state(self) -> PipelineState: ...

    @property
    @abc.abstractmethod
    def mode(self) -> PipelineMode: ...

    @property
    @abc.abstractmethod
    def layout(self) -> IPipelineLayout: ...

    # 新增：通常 Pipeline 也需要暴露它的 router 供外部访问（如果需要）
    # @property
    # @abc.abstractmethod
    # def router(self) -> IEventRouter: ...

    @abc.abstractmethod
    def request_frame_interrupt(self):
        """
        请求中断当前帧的执行。
        通常由 EventRouter 在收到 INTERRUPT 级别的事件时调用。
        """
        ...

    # 生命周期
    @abc.abstractmethod
    def start(self): ...

    @abc.abstractmethod
    def step(self) -> bool: ...

    @abc.abstractmethod
    def trigger(self): ...

    @abc.abstractmethod
    def pause(self): ...

    @abc.abstractmethod
    def resume(self): ...

    @abc.abstractmethod
    def stop(self): ...

    @abc.abstractmethod
    def cleanup(self): ...

    # 动态编排
    @abc.abstractmethod
    def add_strategy(self, strategy: IStrategy): ...

    @abc.abstractmethod
    def insert_strategy(self, index: int, strategy: IStrategy): ...

    @abc.abstractmethod
    def remove_strategy(self, strategy: IStrategy): ...

    @abc.abstractmethod
    def remove_strategy_by_index(self, index: int): ...

    @abc.abstractmethod
    def remove_strategy_by_name(self, name: str): ...

    # 调试
    @abc.abstractmethod
    def print_layout(self): ...


class IPipelineConfig(abc.ABC):
    """管线配置接口"""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def strategies(self) -> List[IStrategy]: ...

    @property
    @abc.abstractmethod
    def mode(self) -> PipelineMode: ...

    @property
    @abc.abstractmethod
    def max_fps(self) -> int: ...

    @property
    @abc.abstractmethod
    def enable_fps_control(self) -> bool: ...

    @property
    @abc.abstractmethod
    def enable_profiling(self) -> bool: ...

    # [新增] 路由工厂配置
    @property
    @abc.abstractmethod
    def router_factory(self) -> Optional[RouterFactory]:
        """
        可选的 Router 构造工厂。
        如果不提供，Pipeline 将使用默认的 EventRouter.create_standard
        """
        ...

    # [新增] 事件策略配置字典
    @property
    @abc.abstractmethod
    def event_policies(self) -> Dict[Any, EventPolicy]:
        """静态配置的事件规则表"""
        ...


class IPipelineAware(abc.ABC):
    """策略感知管线接口"""

    @abc.abstractmethod
    def set_pipeline(self, pipeline: Any): ...


class IPipelineContext(abc.ABC):
    """管线运行时上下文接口"""

    @property
    @abc.abstractmethod
    def frame_index(self) -> int: ...

    @property
    @abc.abstractmethod
    def delta_time(self) -> float: ...

    @abc.abstractmethod
    def clear(self): ...


class IPipelineExecutor(ILoggable):
    """
    [调度器接口] 调度器负责驱动一组管线的 Step 循环。
    """

    @property
    @abc.abstractmethod
    def pipelines(self) -> List[IPipeline]: ...

    @property
    @abc.abstractmethod
    def thread_name(self) -> str: ...

    @abc.abstractmethod
    def add_pipeline(self, pipeline: IPipeline): ...

    @abc.abstractmethod
    def remove_pipeline(self, pipeline: IPipeline): ...

    @abc.abstractmethod
    def get_pipeline(self, name: str) -> Optional[IPipeline]:
        """根据名称获取管线实例"""
        ...

    @abc.abstractmethod
    def start(self): ...

    @abc.abstractmethod
    def stop(self): ...
