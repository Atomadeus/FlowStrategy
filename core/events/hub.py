# core/events/hub.py
import threading
from typing import List, Dict, Any, Callable

from core.configs.policies import LogPolicy
from core.interfaces.event import EventType, IEventHub
from core.logging.logger import SysLogger


# ==========================================
#    全局事件枢纽 (EventHub)
#    定位：基础设施，由 Application 实例化并注入
# ==========================================


class EventHub(IEventHub):
    """
    [实现] 全局事件枢纽，负责跨管线、跨系统的控制信号分发。
    注意：这里不再使用单例模式。它的生命周期由 Application 托管。
    """

    def __init__(self):
        self._lock = threading.Lock()
        # 订阅表：Key 是 EventTopic (str/Enum/Class), Value 是回调列表
        self._subscribers: Dict[EventType, List[Callable]] = {}

        # 初始化默认日志策略
        self._log_policy = LogPolicy.default()

        # [优化] 现在可以使用 self 作为日志源了
        SysLogger.info(self, "EventHub initialized.")

    @property
    def name(self) -> str:
        return "EventHub"

    @property
    def log_policy(self) -> LogPolicy:
        return self._log_policy

    def set_log_policy(self, policy: LogPolicy):
        self._log_policy = policy

    # 使用 EventTopic 替换 Any
    def subscribe(self, event_type: EventType, callback: Callable):
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def publish(self, event_type: EventType, data: Any = None):
        """
        广播消息。
        注意：为了性能，这里没有复杂的日志策略，通常用于低频控制信号。
        """
        # 1. 抓取快照，避免锁内执行回调
        # list() 创建副本，防止回调中修改订阅列表导致报错
        with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        # 2. 执行回调 (无锁)
        for cb in callbacks:
            try:
                cb(data)
            except Exception as e:
                SysLogger.error("EventHub", f"Dispatch Error [{event_type}]: {e}")

    def clear(self):
        with self._lock:
            self._subscribers.clear()
