# core/factories/strategy_factory.py
import threading
from collections import defaultdict
from typing import Type, Dict, TypeVar, Optional, Any

from core.interfaces import IStrategy

# 定义泛型 T，必须是 IStrategy 的子类
T = TypeVar("T", bound=IStrategy)


class StrategyFactory:
    """
    [纯静态工厂] 负责策略的 1.自动命名 2.依赖注入 3.实例化
    """

    _counters: Dict[str, int] = defaultdict(int)
    _lock = threading.Lock()

    @staticmethod
    def create(strategy_cls: Type[T], custom_name: Optional[str] = None, **kwargs) -> T:
        """
        通用的策略创建方法。
        :param strategy_cls: 具体的策略类
        :param custom_name: (可选) 指定名称
        :param kwargs: 传递给策略 __init__ 的参数
        """
        final_name = custom_name

        # --- 1. 自动命名逻辑 ---
        if not final_name:
            class_name = strategy_cls.__name__
            with StrategyFactory._lock:
                idx = StrategyFactory._counters[class_name]
                StrategyFactory._counters[class_name] += 1
            final_name = f"{class_name}_{idx}"

        # --- 2. 实例化与注入 ---
        try:
            # [关键点]：工厂强制将 'name' 参数注入到构造函数中
            # 这要求所有具体策略的 __init__ 方法必须接收 name 参数
            instance = strategy_cls(name=final_name, **kwargs)
            return instance

        except TypeError as e:
            if "unexpected keyword argument 'name'" in str(e):
                raise TypeError(
                    f"Factory Error: The strategy class '{strategy_cls.__name__}' must accept a 'name' parameter in its __init__ method.\n"
                    f"Original Error: {e}"
                )
            raise e
