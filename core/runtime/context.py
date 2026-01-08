# core/runtime/context.py
from dataclasses import dataclass, field
from typing import Dict, Any, Type, TypeVar

from core.interfaces.pipeline import IPipelineContext

# 定义泛型 T
T = TypeVar("T")


@dataclass
class PipelineContext(IPipelineContext):
    """
    [上下文聚合] 运行时数据容器。
    升级为支持类型安全的黑板模式。
    """

    _frame_index: int = 0
    _delta_time: float = 0.0
    # 共享黑板：用于 Strategy 之间传递非流式数据 (如: "is_ball_visible")
    # [核心修改] Key 改为 Type，不再是 str
    _data_store: Dict[Type, Any] = field(default_factory=dict)

    # --- 基础属性 ---
    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def delta_time(self) -> float:
        return self._delta_time

    # --- 类型安全的访问接口 ---

    def get_data(self, data_type: Type[T]) -> T:
        """
        [读] 获取指定类型的上下文数据。
        如果不存在，自动创建一个默认实例（前提是该 dataclass 无参构造或全默认值）
        """
        if data_type not in self._data_store:
            # 自动懒加载：如果请求的数据不存在，就创建一个新的
            self._data_store[data_type] = data_type()
        return self._data_store[data_type]

    def set_data(self, data_obj: Any):
        """[写] 存入数据对象"""
        self._data_store[type(data_obj)] = data_obj

    def has_data(self, data_type: Type) -> bool:
        return data_type in self._data_store

    def clear(self):
        self._frame_index = 0
        self._delta_time = 0.0
        self._data_store.clear()
