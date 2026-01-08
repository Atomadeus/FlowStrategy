# core/interfaces/ecs.py
import abc
from typing import List, Tuple, Optional, Type, TypeVar

from core.interfaces.base import ILoggable
from core.ecs.components import Component

T = TypeVar("T", bound=Component)


class IFrame(abc.ABC):
    """
    [Entity] 帧实体接口
    彻底移除 OOP 风格的 'strategy_results'。
    现在 Frame 只是一个持有 Component 的容器。
    """

    frame_id: int = 0

    @abc.abstractmethod
    def add_component(self, component: Component) -> None:
        """
        添加或更新组件。
        ECS 哲学：数据即状态。策略执行的结果应封装为 Component 存入。
        """
        ...

    @abc.abstractmethod
    def get_component(self, component_type: Type[T]) -> Optional[T]:
        """
        获取指定类型的组件。
        """
        ...

    @abc.abstractmethod
    def has_component(self, component_type: Type[Component]) -> bool:
        """
        检查是否包含某类组件。
        """
        ...

    @abc.abstractmethod
    def remove_component(self, component_type: Type[Component]) -> None:
        """
        移除组件。
        """
        ...

    @abc.abstractmethod
    def release(self):
        """
        释放资源 (清空所有组件引用)。
        """
        ...


class IStrategy(ILoggable):
    """
    [System] 策略/系统接口
    """

    @abc.abstractmethod
    def __init__(self, name: str, **kwargs): ...

    @property
    def required_components(self) -> List[Type[Component]]:
        """
        [ECS 特性] 声明此策略运行所需的组件类型列表。
        Pipeline 或 Executor 可以利用此信息进行前置检查或跳过执行。
        默认为空列表（表示无强制依赖）。
        """
        return []

    @abc.abstractmethod
    def execute(self, frame: Optional[IFrame]) -> Tuple[bool, Optional[IFrame]]:
        """
        执行逻辑。
        :return: (is_success, frame)
                 如果返回 False，通常意味着该 Frame 被丢弃或处理失败。
        """
        ...

    @abc.abstractmethod
    def cleanup(self): ...
