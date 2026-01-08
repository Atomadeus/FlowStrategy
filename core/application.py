# core/application.py
import sys
import signal
import threading
import time
from typing import List

from core.interfaces import IStrategy
from core.configs.enums import LogLevel, PipelineMode
from core.events.protocol import SystemEvent, SystemAlertPayload

from core.logging.logger import SysLogger
from core.events.hub import EventHub  # [DI] 这是一个普通类，不是单例
from core.runtime.executor import PipelineExecutor
from core.factories.pipeline_factory import PipelineFactory


class Application:
    """
    [组合根 Composition Root]
    系统的最高指挥官。
    职责：
    1. 拥有并管理基础设施 (EventHub, LogSystem)。
    2. 组装管线 (利用 Factory)。
    3. 管理调度器 (Executor) 的生命周期 (Start/Stop)。
    4. 监听系统级信号 (Ctrl+C, Critical Errors)。
    """

    def __init__(self):
        SysLogger.info("App", "Initializing Application Infrastructure...")

        # 1. [基础设施] 创建全局事件枢纽
        # 它是 Application 的实例属性，而非全局变量
        self.event_hub = EventHub()

        # 2. [容器] 准备执行器列表
        self._executors: List[PipelineExecutor] = []
        self._lock = threading.Lock()

        # 3. [默认执行器] 为了方便快速上手，内置一个主执行器
        # 大多数简单应用只需要这一个 executor
        self._default_executor = PipelineExecutor(
            "MainExecutor", event_hub=self.event_hub
        )
        self.register_executor(self._default_executor)

        # 4. [状态] 运行标志
        self._running = False

        # 5. [自举] 订阅系统级关键事件
        # 例如：当某个管线发出致命警报时，Application 决定是否要全部停机
        self.event_hub.subscribe(SystemEvent.SYSTEM_ALERT, self._on_system_alert)

        # 6. [系统] 接管信号处理 (Ctrl+C)
        self._setup_signal_handlers()

    # ==========================================
    # 组装 API (Assembly Facade)
    # ==========================================

    def add_pipeline(
        self,
        name: str,
        strategies: List[IStrategy],
        mode: PipelineMode = PipelineMode.LOOP,
    ) -> "Application":
        """
        [傻瓜式 API] 快速添加一条管线到默认执行器。

        Args:
            name: 管线名称 (e.g. "VisionPipe")
            strategies: 策略实例列表
            mode: 运行模式 (LOOP/SINGLE/CONDITIONAL)

        Returns:
            self: 支持链式调用 app.add_pipeline(...).add_pipeline(...)
        """
        # [DI 关键点]
        # 我们在这里将 Application 持有的 event_hub 显式传递给工厂。
        # 工厂会将它封装进闭包，最终注入到 Pipeline 内部的 EventRouter 中。
        pipeline = PipelineFactory.create_pipeline(
            name=name,
            strategies=strategies,
            event_hub=self.event_hub,  # <--- 依赖注入发生地
            mode=mode,
        )

        # 将生产好的管线挂载到默认执行器
        self._default_executor.add_pipeline(pipeline)
        return self

    def register_executor(self, executor: PipelineExecutor) -> "Application":
        """
        [专家 API] 注册自定义的 Executor (例如独立的后台线程组)。
        """
        with self._lock:
            if executor not in self._executors:
                self._executors.append(executor)
                SysLogger.info("App", f"Executor registered: {executor.name}")
        return self

    # ==========================================
    # 生命周期管理 (Lifecycle)
    # ==========================================

    def start(self, block: bool = True):
        """
        启动整个应用。

        Args:
            block: 是否阻塞主线程。通常设为 True，除非你在编写 GUI 或其他异步框架。
        """
        if self._running:
            return

        self._running = True
        SysLogger.critical(">>> APPLICATION STARTUP SEQUENCE INITIATED...")

        # 1. 广播启动信号 (通知所有模块准备就绪)
        self.event_hub.publish(SystemEvent.PIPELINE_CONTROL, "APP_START")

        # 2. 启动所有执行器 (线程启动)
        for exc in self._executors:
            exc.start()

        SysLogger.critical(">>> APPLICATION RUNNING.")

        # 3. 阻塞主线程 (防止 main 函数退出)
        if block:
            try:
                while self._running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                # 双重保险，通常 _setup_signal_handlers 会先捕获
                self.stop()

    def stop(self):
        """
        优雅停机。
        """
        if not self._running:
            return

        SysLogger.critical(">>> APPLICATION SHUTDOWN SEQUENCE INITIATED...")
        self._running = False

        # 1. 广播停止信号
        self.event_hub.publish(SystemEvent.PIPELINE_CONTROL, "APP_STOP")

        # 2. 停止所有执行器
        # 注意：这会等待线程 join，确保当前帧处理完毕
        for exc in self._executors:
            exc.stop()

        # 3. 清理基础设施
        self.event_hub.clear()

        SysLogger.critical(">>> Application stopped safely. Bye!")
        sys.exit(0)

    # ==========================================
    # 调试与工具 (Tools)
    # ==========================================

    def print_topology(self):
        """
        [可视化] 打印系统当前的拓扑结构。
        (移植自原 manager.py)
        """
        print("\n" + "=" * 70)
        print(f"{'SYSTEM TOPOLOGY REPORT':^70}")
        print("=" * 70)

        def _fmt_policy(policy) -> str:
            mask = policy.allowed_mask
            if mask == LogLevel.NONE:
                return "[🔇 SILENT]"
            if mask == LogLevel.ALL:
                return "[📢 ALL]"

            flags = []
            if mask & LogLevel.INFO:
                flags.append("I")
            if mask & LogLevel.WARNING:
                flags.append("W")
            if mask & LogLevel.ERROR:
                flags.append("E")
            return f"[{''.join(flags)}]"

        with self._lock:
            for i, exc in enumerate(self._executors):
                print(f"📦 Executor [{i}]: {exc.name}")
                print(f"   └── 🧵 Thread: {exc.thread_name}")

                for pipe in exc.pipelines:
                    # 获取 Pipeline 的日志策略
                    p_policy_str = _fmt_policy(pipe.log_policy)
                    print(f"       └── 🚀 Pipeline: {pipe.name} {p_policy_str}")

                    # 打印布局 (Strategy 链)
                    # 注意：这里直接访问 strategies 属性进行遍历
                    for strategy in pipe.strategies:
                        s_policy_str = _fmt_policy(strategy.log_policy)
                        print(
                            f"           └── 🧩 Strategy: {strategy.name} {s_policy_str}"
                        )

                print("-" * 70)
        print("=" * 70 + "\n")

    # ==========================================
    # 内部机制 (Internals)
    # ==========================================

    def _on_system_alert(self, payload: SystemAlertPayload):
        """
        处理系统级致命警报。
        来源: Executor 捕获到 PipelineCriticalError 后汇报。
        """
        # 如果是致命错误，触发应用级熔断
        if payload.level == "CRITICAL":  # 或者使用 AlertLevel 枚举比较
            SysLogger.critical(
                f"!!! SYSTEM MELTDOWN IMMINENT !!! Source: {payload.source}"
            )
            SysLogger.critical(f"Reason: {payload.message}")

            # 策略：遇到致命错误，自动停机
            # 这里也可以写重启逻辑
            self.stop()

    def _setup_signal_handlers(self):
        """挂载 OS 信号处理"""

        def handler(sig, frame):
            # [修复] 补上 source 参数 "App"
            SysLogger.warning(
                "App", "\n[INTERRUPT] Signal received (Ctrl+C). Stopping engine..."
            )
            self.stop()

        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except ValueError:
            # 如果不在主线程运行 (e.g. GUI 环境)，signal 可能会报错，忽略即可
            pass
