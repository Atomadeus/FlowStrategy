# core/events/router.py
import functools
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Type
from collections import defaultdict, deque


from core.configs.enums import LogLevel, EventPriority
from core.configs.policies import LogLevel, LogPolicy, EventPolicy
from core.interfaces.base import ILoggable
from core.interfaces.event import EventType, IEventHub, IEventRouter
from core.interfaces.pipeline import IPipeline
from core.logging.logger import SysLogger

# ==========================================
#    局部事件路由器 (EventRouter)
#    定位：管线组件，处理高频数据流
# ==========================================


# --- 追踪装饰器 ---
def trace_publish(func):
    """[探针1] 追踪投递动作 (入口)"""

    @functools.wraps(func)
    def wrapper(
        self, event_type, data=None, sender=None, priority=EventPriority.DEFERRED
    ):
        # 1. 获取事件策略对象 (默认为 Normal)
        event_policy: EventPolicy = self._event_policies.get(
            event_type, EventPolicy.normal()
        )

        # 2. 如果规则是 DROP，装饰器里不需要做任何事，直接放行给 publish 去拦截
        # 或者为了日志彻底干净，这里也可以判断 return
        if event_policy.is_dropped:
            return  # 直接丢弃，不执行 func

        # 3. 如果是静音模式，直接执行 func，跳过后续的日志逻辑
        if event_policy.is_mute:
            return func(self, event_type, data, sender, priority)

        # --- 以下是正常的日志逻辑 (Normal 模式) ---

        # 智能日志策略检查 (双闸门机制)
        # 规则: Router 必须开启 INFO，且 事件策略(EventPolicy) 必须为 NORMAL (除非是高优先级信号)
        # 不需要再检查 data 内部有没有 log_policy 了，因为 data 已经是纯数据了
        should_log = self.log_policy.is_allowed(LogLevel.INFO)
        is_high_priority = priority >= EventPriority.INTERRUPT

        if should_log or is_high_priority:
            sender_name = (
                sender.name
                if isinstance(sender, ILoggable)
                else str(sender or "External")
            )

            # 获取事件名：处理 Type 和 Enum/str 的不同情况
            if isinstance(event_type, type):
                event_name = event_type.__name__
            else:
                event_name = str(event_type)

            # 2. 构造日志内容：图标
            icon_map = {
                EventPriority.DEFERRED: "📫",
                EventPriority.IMMEDIATE: "⚡",
                EventPriority.INTERRUPT: "🚨",
                EventPriority.CRITICAL: "💥",
            }
            icon = icon_map.get(priority, "❓")

            SysLogger.info(
                self,
                f"{icon} [PUB] {event_name} from {sender_name} (Priority: {priority.name})",
            )

        return func(self, event_type, data, sender, priority)

    return wrapper


def trace_dispatch(func):
    """[探针2] 追踪分发动作 (出口)"""

    @functools.wraps(func)
    def wrapper(self, event_type, data):
        # 仅当 Router 允许 INFO 时才打印分发细节，减少噪音
        if self.log_policy.is_allowed(LogLevel.INFO):
            subscribers = self._subscribers.get(event_type, [])
            if not subscribers:
                SysLogger.warning(
                    self, f"⚠️ [NO_SUB] {event_type.__name__} has no subscribers!"
                )
            else:
                SysLogger.info(
                    self,
                    f"⚙️ [DISPATCH] {event_type.__name__} -> {len(subscribers)} handlers",
                )

        return func(self, event_type, data)

    return wrapper


# --- EventRouter 实现 ---


class EventRouter(IEventRouter):
    def __init__(self, pipeline: IPipeline, event_hub: IEventHub):
        self._pipeline = pipeline  # 弱引用代理，避免循环引用
        self._event_hub = event_hub  # <--- 持有注入的实例

        self._subscribers: Dict[type, List[Callable]] = defaultdict(list)
        self._deferred_queue = deque()

        # [核心修复] 初始化策略字典
        self._event_policies: Dict[type, EventPolicy] = {}

        self._log_policy = LogPolicy.default()

    # --- 工厂方法 ---
    @classmethod
    def create_standard_router(
        cls, pipeline: IPipeline, event_hub: IEventHub
    ) -> "EventRouter":
        """
        标准工厂：返回一个配置好的默认 Router
        符合 RouterFactory = Callable[["IPipeline"], IEventRouter] 签名
        """
        router = cls(pipeline, event_hub)
        # 你甚至可以在这里做一些默认的预设
        # router.set_log_policy(LogPolicy.default())
        return router

    @property
    def name(self) -> str:
        # 显示层级: "PipelineName.Router"
        return f"{self._pipeline.name}.Router"

    @property
    def log_policy(self) -> LogPolicy:
        return self._log_policy

    def set_pipeline(self, pipeline: Any):
        """支持 Setter 注入，防止循环引用"""
        self._pipeline = pipeline

    def set_log_policy(self, policy: LogPolicy):
        self._log_policy = policy

    def set_event_policy(self, event_type: Type, policy: EventPolicy):
        """[核心修复] 实现接口要求的策略设置方法"""
        self._event_policies[event_type] = policy

    def subscribe(self, event_type: type, callback: Callable):
        self._subscribers[event_type].append(callback)

    def publish_global(self, event_type: Type, data=None):
        """
        桥接到注入的 EventHub
        """
        if self._event_hub:
            self._event_hub.publish(event_type, data)

    @trace_publish
    def publish(
        self,
        event_type: EventType,
        data: Any = None,
        sender: Any = None,
        priority: EventPriority = EventPriority.DEFERRED,
    ):

        # A. 致命错误
        if priority == EventPriority.CRITICAL:
            # [优化] 抛出具有语义的自定义异常，方便 Executor 捕获并执行重启逻辑
            error_msg = f"CRITICAL Signal: {event_type} from {sender or 'Unknown'}"
            raise Exception(error_msg)

        # B. 立即执行 (IMMEDIATE / INTERRUPT)
        if priority >= EventPriority.IMMEDIATE:
            self._dispatch_now(event_type, data)

            # [必需机制] 熔断当前帧
            # 只有 INTERRUPT 才会打断 Pipeline
            if priority == EventPriority.INTERRUPT:
                if self._pipeline:
                    self._pipeline.request_frame_interrupt()
                else:
                    # 防御性编程：如果 Pipeline 还没注入，打印警告
                    SysLogger.warning(
                        self, "Interrupt requested but Pipeline is not bound!"
                    )

        # C. 延迟执行 (DEFERRED)
        else:
            self._deferred_queue.append((event_type, data))

    @trace_dispatch
    def _dispatch_now(self, event_type, data):
        """实际执行回调"""
        # 使用副本列表进行迭代，防止回调中有人取消订阅导致 RuntimeError
        # subscribers = list(self._subscribers[event_type])
        # 但通常 append 操作不会影响 list 迭代器，如果是 remove 则需要注意
        # 暂时保持原样，如果涉及动态取消订阅，建议这里加 list()
        for callback in self._subscribers[event_type]:
            try:
                callback(data)
            except Exception as e:
                SysLogger.error(self, f"Handler Error in {event_type.__name__}: {e}")

    def process_deferred(self):
        """[帧同步点] 处理等待队列"""
        if self._deferred_queue:
            # 仅在有数据时打印 Flush 日志
            if self.log_policy.is_allowed(LogLevel.INFO):
                SysLogger.info(self, "⏳ [FLUSH] Processing deferred event queue...")

            # 使用 temp buffer 防止处理过程中产生新事件导致死循环
            count = len(self._deferred_queue)
            for _ in range(count):
                etype, data = self._deferred_queue.popleft()
                self._dispatch_now(etype, data)

    def mute_log_for(self, event_type: Type):
        """[便利方法] 快速静音某事件"""
        self.set_event_policy(event_type, EventPolicy.silent())
