# core/runtime/executor.py
import threading
import time
from typing import List, Optional

from core.configs.enums import PipelineState
from core.configs.policies import LogPolicy
from core.exceptions import PipelineCriticalError  # 捕获自定义异常
from core.events.protocol import SystemEvent, SystemAlertPayload, AlertLevel, ErrorCode
from core.interfaces import EventType, IPipelineExecutor, IPipeline, IEventHub
from core.logging.logger import SysLogger


class PipelineExecutor(IPipelineExecutor):
    """
    [调度器] 负责驱动一组管线的 Step 循环。
    """

    def __init__(self, name: str, event_hub: Optional[IEventHub] = None):
        # 基础属性
        self._name = name
        # 依赖注入
        self._event_hub = event_hub  # [DI] 注入总线，用于汇报状态
        self._pipelines: List[IPipeline] = []

        # 状态管理
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_name = "Pending..."
        self._lock = threading.Lock()

        # 默认日志策略
        self._log_policy = LogPolicy.default()

    # --- 接口实现 ---

    @property
    def name(self) -> str:
        return self._name

    @property
    def pipelines(self) -> List[IPipeline]:
        return self._pipelines

    @property
    def thread_name(self) -> str:
        return self._thread_name

    @property
    def log_policy(self) -> LogPolicy:
        return self._log_policy

    def set_log_policy(self, policy: LogPolicy):
        self._log_policy = policy

    def add_pipeline(self, pipeline: IPipeline):
        with self._lock:
            self._pipelines.append(pipeline)
            SysLogger.info(self, f"Pipeline attached: {pipeline.name}")

    def remove_pipeline(self, pipeline: IPipeline):
        with self._lock:
            if pipeline in self._pipelines:
                self._pipelines.remove(pipeline)
                SysLogger.info(self, f"Pipeline detached: {pipeline.name}")
            else:
                SysLogger.warning(
                    self, f"Cannot remove pipeline {pipeline.name}: Not found."
                )

    def get_pipeline(self, name: str) -> Optional[IPipeline]:
        with self._lock:
            for p in self._pipelines:
                if p.name == name:
                    return p
        return None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name=f"Thread-{self.name}")
        self._thread.start()
        SysLogger.info(self, f"Executor thread {self.name} started.")

    def stop(self):
        if not self._running:
            return

        self._running = False
        if self._thread:
            # 这里的 join 可能会阻塞，通常由 Application 控制超时
            self._thread.join(timeout=2.0)
            SysLogger.info(self, f"Executor thread {self.name} stopped.")

    # --- 核心循环 ---

    def _loop(self):
        """
        [智能调度循环]
        """
        self._thread_name = threading.current_thread().name

        # 广播启动事件
        if self._event_hub:
            # 这里可以用 EventType.PIPELINE_CONTROL，也可以自定义扩展
            pass

        while self._running:
            # 标记本轮是否有管线实际进行了工作
            any_work_done = False

            # 使用副本进行迭代，因为我们可能在迭代中移除死掉的管线
            # 或者使用索引倒序遍历
            # 使用快照避免锁竞争过大
            with self._lock:
                # 浅拷贝一份列表用于遍历
                current_pipelines = list(self._pipelines)

            pipelines_to_remove = []

            for pipe in current_pipelines:
                # 1. 检查状态，清理已终止管线
                if pipe.state == PipelineState.TERMINATED:
                    pipelines_to_remove.append(pipe)
                    continue

                # 2. 执行 Step，并获取反馈
                try:
                    # step() 现在返回 bool
                    did_work = pipe.step()
                    if did_work:
                        any_work_done = True

                # [核心修正] 捕获致命错误，执行熔断
                except PipelineCriticalError as ce:
                    SysLogger.critical(f"CRITICAL ERROR in {pipe.name}: {ce}")
                    # 汇报给全局总线
                    self._report_critical_error(pipe, str(ce))
                    # 策略：遇到致命错误，通常停止该管线，甚至停止整个 Executor
                    # [解释] pipe.stop() 不需要参数，它内部会处理状态切换
                    pipe.stop()

                except Exception as e:
                    # 普通未知错误，记录但不崩溃
                    SysLogger.error(self, f"Unhandled Error in {pipe.name}: {e}")

            # 3. 清理已死亡的管线 (Garbage Collection)
            if pipelines_to_remove:
                with self._lock:
                    for p in pipelines_to_remove:
                        if p in self._pipelines:
                            self._pipelines.remove(p)
                            SysLogger.warning(
                                self, f"Pipeline detached (Terminated): {p.name}"
                            )

            # 4. 智能休眠策略 (Adaptive Sleep)
            if not any_work_done:
                # 如果所有管线都在 Idle/Pause/Wait Trigger，休眠 10ms 省电
                time.sleep(0.01)  # 10ms
            else:
                # 如果有管线在忙，全速运行或微小让步 (防止 CPU 100% 占用)
                # 对于高帧率应用，建议不休眠或只 sleep(0)
                # time.sleep(0.0001)
                pass

    def _report_critical_error(self, pipe, msg):
        """向 Application 汇报致命错误"""
        if self._event_hub:
            payload = SystemAlertPayload(
                level=AlertLevel.CRITICAL,
                error_code=ErrorCode.GENERIC_ERROR,
                source=f"{self.name}/{pipe.name}",
                message=msg,
            )
            self._event_hub.publish(SystemEvent.SYSTEM_ALERT, payload)
