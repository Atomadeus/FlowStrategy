import threading
from typing import Type, TypeVar, Dict, Optional, List

from core.interfaces import IFrame
from core.ecs.components import Component

# 定义泛型 T，它必须是 Component 的子类
T = TypeVar("T", bound=Component)


class Frame(IFrame):
    """
    [ECS Entity] 纯粹的数据容器
    它不包含任何业务逻辑，也不记录执行历史（除非添加一个 HistoryComponent）。
    它只是一个携带 ID 的组件包。
    """

    def __init__(self, fid: int):
        self.frame_id = fid
        self._released = False

        # [ECS Store] Key: Component Class Type -> Value: Component Instance
        self._components: Dict[Type[Component], Component] = {}

        # 线程锁，保护组件字典的读写
        self._lock = threading.Lock()

    def add_component(self, component: Component) -> None:
        """
        添加组件 (Create/Update)
        """
        with self._lock:
            # 这里的 Key 是类对象 (例如 ImageComponent)
            # 这保证了每种类型的组件在同一个 Frame 中只能有一个实例 (Singleton Component per Entity)
            # 如果需要多个同类组件，用户应该定义一个 ListComponent 包装器
            self._components[type(component)] = component

    def get_component(self, component_type: Type[T]) -> Optional[T]:
        """
        获取组件 (Read)
        使用泛型 T，让 IDE 能推断出返回的具体类型。
        """
        # 读操作通常不需要锁（在 Python GIL 下字典读取是原子的）
        # 但为了绝对的严格性，可以在高并发写场景下加锁。
        # 这里为了性能，且考虑到 Frame 通常在 Pipeline 中是线性传递的，暂不加锁读取。
        return self._components.get(component_type)  # type: ignore

    def has_component(self, component_type: Type[Component]) -> bool:
        """
        检查组件是否存在
        """
        return component_type in self._components

    def remove_component(self, component_type: Type[Component]) -> None:
        """
        移除组件 (Delete)
        """
        with self._lock:
            if component_type in self._components:
                del self._components[component_type]

    def release(self):
        """
        资源回收
        """
        if self._released:
            return

        with self._lock:
            # 清空字典，断开对所有 Component 的引用
            # 如果 Component 内部持有非托管资源（如 C++ 指针），
            # Component 自身应实现 __del__ 或 dispose 逻辑，Frame 只负责断开引用。
            self._components.clear()
            self._released = True

    def __repr__(self):
        # 打印当前持有的所有组件类型名称，方便调试
        comp_names = [t.__name__ for t in self._components.keys()]
        return f"<Frame id={self.frame_id} components={comp_names} released={self._released}>"
