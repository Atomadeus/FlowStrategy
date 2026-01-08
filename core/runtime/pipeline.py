# core/runtime/pipeline.py
import time
import threading
from typing import List, Dict, Tuple, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
import weakref


from core.configs.enums import PipelineState, PipelineMode
from core.configs.policies import LogPolicy
from core.configs.settings import PipelineConfig
from core.exceptions import StrategyExecutionError
from core.interfaces.ecs import IStrategy
from core.interfaces.pipeline import IPipeline, IPipelineAware
from core.logging.logger import SysLogger
from core.runtime.context import PipelineContext
from core.runtime.layout import PipelineLayout

# 注意：不再直接导入 EventRouter 或 EventHub，只依赖接口或 Factory
# 这样 Pipeline 类就彻底不知道 EventHub 的存在了 (解耦)


class Pipeline(IPipeline):
    def __init__(self, config: PipelineConfig):
        # 1. 绑定配置
        self.config = config
        self._name = config.name
        self._mode = config.mode

        # 2. [DI 核心修正] 初始化 EventRouter
        # Pipeline 不应该知道 EventHub 的存在，它只知道 Config 里有个工厂能造出 Router
        if not config.router_factory:
            raise ValueError(
                f"Pipeline '{self._name}' config is missing 'router_factory'. "
                "Please use PipelineFactory to create pipelines."
            )

        # 这里调用闭包工厂。
        # 闭包内部已经捕获了 event_hub，所以这里只需要传 pipeline (self) 即可。
        # 使用 weakref.proxy 是为了防止 Router 反向持有 Pipeline 造成循环引用导致内存泄漏。
        # 如果 Router 也持有 Pipeline 的强引用，两者的引用计数永远不会归零，导致内存泄漏（即调用 del pipeline 后对象依然驻留内存）
        self.event_router = config.router_factory(weakref.proxy(self))

        # 3. [修复 B] 应用事件策略 (EventPolicies)
        for event_type, policy in config.event_policies.items():
            self.event_router.set_event_policy(event_type, policy)

        # 4. 初始化上下文
        self.context = PipelineContext()

        # 5. 内部状态管理
        self._lock = threading.RLock()  # 保护写操作 (add/remove/state_change)
        self._state = PipelineState.IDLE
        self._trigger_event = threading.Event()  # 条件模式的触发器 (非阻塞 Event)
        self._frame_interrupted = False  # 帧内中断标志

        # 6. 日志策略 (默认跟随配置或默认值)
        self._log_policy = LogPolicy.default()

        # 7. 初始化策略链
        self._strategies: List[IStrategy] = []
        for s in config.strategies:
            self.add_strategy(s)  # 复用 add 方法进行绑定

    # --- [属性访问] ---
    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> PipelineState:
        """对外暴露当前状态"""
        return self._state

    @property
    def mode(self) -> PipelineMode:
        return self._mode

    @property
    def strategies(self) -> List[IStrategy]:
        return self._strategies

    @property
    def log_policy(self) -> LogPolicy:
        return self._log_policy

    # --- [生命周期控制] ---

    def start(self):
        """将管线置为运行状态"""
        with self._lock:
            if self._state == PipelineState.TERMINATED:
                SysLogger.error(self, "Cannot restart a TERMINATED pipeline.")
                return

            # 如果是条件模式，启动时先清除触发器，等待外部信号
            if self._mode == PipelineMode.CONDITIONAL:
                self._trigger_event.clear()

            self._state = PipelineState.RUNNING
            SysLogger.info(self, f"Pipeline started in {self._mode.name} mode.")
            SysLogger.info(self, f"Pipeline state set to {self._state.name} state.")

    def trigger(self):
        """[新增] 触发条件执行"""
        if self._mode == PipelineMode.CONDITIONAL:
            self._trigger_event.set()
            # 可以在这里打印 debug 日志，但如果触发频繁则不建议

    def pause(self):
        """暂停管线"""
        with self._lock:
            if self._state == PipelineState.RUNNING:
                self._state = PipelineState.PAUSED
                SysLogger.info(self, "Pipeline PAUSED.")

    def resume(self):
        """恢复管线"""
        with self._lock:
            if self._state == PipelineState.PAUSED:
                self._state = PipelineState.RUNNING
                SysLogger.info(self, "Pipeline RESUMED.")

    def stop(self):
        """终止管线并清理资源"""
        with self._lock:
            if self._state != PipelineState.TERMINATED:
                self._state = PipelineState.TERMINATED
                SysLogger.warning(self, "Pipeline TERMINATED. Cleaning up...")
                self.cleanup()

    def request_frame_interrupt(self):
        """允许 EventRouter 或 Strategy 请求中断当前帧"""
        self._frame_interrupted = True

    # --- [核心执行逻辑] ---

    def step(self) -> bool:
        """
        :return: True if work was done, False if skipped.
        """

        # 1. 基础状态检查
        if self._state != PipelineState.RUNNING:
            return False

        # 2. 模式检查 (Mode Logic)
        if self._mode == PipelineMode.CONDITIONAL:
            # 非阻塞检查：如果没有触发，直接跳过
            if not self._trigger_event.is_set():
                return False
            # 如果触发了，清除标记，准备执行
            self._trigger_event.clear()

        # [时间点 A] 帧周期开始 (Frame Start)
        loop_start_time = time.perf_counter()
        # 计算 Delta Time (用于业务逻辑)
        # 这是“两个时间点A之间的间隔”
        dt = loop_start_time - self._last_time
        # 防止极端情况下时间倒流或过大
        if dt < 0:
            dt = 0
        self._last_time = loop_start_time  # 更新锚点

        # 注入 Context (给策略用)
        self.context._delta_time = dt
        self.context._frame_index += 1

        # 3. 执行策略链
        current_data = (
            None  # 初始数据为 None，由第一个 Strategy (Source) 负责产生 Frame
        )
        self._frame_interrupted = False  # 重置中断标记
        did_work = False

        try:
            # 必须使用副本进行迭代 (CoW 安全)
            current_chain = self._strategies

            for strategy in current_chain:
                # 再次检查终止状态 熔断检查点 1：Pipeline 状态
                if self._state == PipelineState.TERMINATED:
                    if current_data and hasattr(current_data, "release"):
                        current_data.release()
                    return True  # 算作“做了工作”但在中途停止

                # [核心修复] 熔断检查点 2: 帧内中断信号
                # 如果上一个策略发出了 INTERRUPT 信号，或者 Router 处理事件时触发了中断
                # 立即停止当前帧的后续逻辑
                if self._frame_interrupted:
                    if self.config.enable_profiling:
                        SysLogger.warning(
                            self,
                            f"Frame {self.context.frame_index} interrupted logic flow.",
                        )
                    break

                try:
                    # Execute: None -> Frame (First Strategy)
                    # Execute: Frame -> Frame (Next Strategies)
                    success, current_data = strategy.execute(current_data)

                    # 业务逻辑上的失败 (返回 False)，通常也意味着链条中止
                    if not success:
                        if current_data and hasattr(current_data, "release"):
                            current_data.release()
                        break

                    did_work = True  # 标记为有效执行

                except StrategyExecutionError as se:
                    SysLogger.error(self, f"Strategy Error [{strategy.name}]: {se}")
                    if current_data and hasattr(current_data, "release"):
                        current_data.release()
                    break
                except Exception as e:
                    SysLogger.error(self, f"Unexpected Error [{strategy.name}]: {e}")
                    if current_data and hasattr(current_data, "release"):
                        current_data.release()
                    break
        except Exception as e:
            SysLogger.critical(f"Pipeline Loop Critical Error: {e}")
            return False

        finally:
            # 4. 帧尾处理
            # 即使中断了，也要处理积压的事件 (Process Deferred)
            self.event_router.process_deferred()

            # 再次检查中断（防止在 process_deferred 中触发了新的中断逻辑，虽然对本帧无影响了，但状态需一致）
            if self._frame_interrupted:
                pass  # 可以做一些额外的清理工作

            # 资源释放 (鸭子类型检查)
            if current_data and hasattr(current_data, "release"):
                current_data.release()

            # 5. 帧率控制 (Pacing)
            # [时间点 B] 帧处理结束 (Processing End)
            loop_end_time = time.perf_counter()
            # 计算执行耗时 (Execution Duration)
            # 这是“时间点B - 时间点A”
            execution_duration = loop_end_time - loop_start_time
            # [核心功能] 性能分析与帧率控制
            self._handle_frame_pacing(execution_duration)

        # SINGLE 模式的特殊处理：执行完一次后自动终止
        if self._mode == PipelineMode.SINGLE:
            self.stop()  # 这会将状态改为 TERMINATED，Executor 下一轮会将其移除

        return did_work

    def _handle_frame_pacing(self, duration: float):
        """
        [辅助方法] 处理帧率控制和性能告警
        """
        # 1. 记录到 Context 供 UI 显示 (e.g. "Render Time: 4.2ms")
        # 假设 Context 里加了这个字段，或者通过 Protocol 发送 stats
        # self.context.last_execution_duration = duration

        # 2. 性能告警 (例如: 目标是 60FPS -> 16.6ms)
        target_interval = 1.0 / self.config.max_fps
        if duration > target_interval:
            if self.config.enable_profiling:
                SysLogger.warning(
                    self,
                    f"Frame Drop! Cost: {duration*1000:.2f}ms > {target_interval*1000:.2f}ms",
                )

        # 3. 帧率锁定 (Sleep)
        # 如果处理太快 (比如 2ms)，需要睡 14ms 等待下一个周期
        # 注意：这里仅仅是简单的 sleep，高精度 Loop 需要更复杂的 while spin
        remaining = target_interval - duration
        if self.config.enable_fps_control and remaining > 0:
            time.sleep(remaining)

    # --- [动态编排 (CoW 写操作)] ---

    def add_strategy(self, strategy: IStrategy):
        with self._lock:
            self._bind_pipeline_context(strategy)
            new_chain = list(self._strategies)  # Copy
            new_chain.append(strategy)  # Modify
            self._strategies = new_chain  # Replace
            SysLogger.info(self, f"Strategy added: {strategy.name}")

    def insert_strategy(self, index: int, strategy: IStrategy):
        with self._lock:
            self._bind_pipeline_context(strategy)
            new_chain = list(self._strategies)
            new_chain.insert(index, strategy)
            self._strategies = new_chain
            SysLogger.info(self, f"Strategy inserted at {index}: {strategy.name}")

    def remove_strategy(self, strategy: IStrategy):
        """
        [新增] 动态移除策略 (CoW 实现)
        """
        with self._lock:
            if strategy not in self._strategies:
                SysLogger.warning(
                    self, f"Cannot remove strategy {strategy.name}: Not found."
                )
                return

            new_chain = list(self._strategies)  # Copy
            new_chain.remove(strategy)  # Modify
            self._strategies = new_chain  # Replace

            # 移除后可能需要清理该策略的资源
            try:
                strategy.cleanup()
            except Exception as e:
                SysLogger.error(self, f"Error cleaning up removed strategy: {e}")

            SysLogger.info(self, f"Strategy removed: {strategy.name}")

    def remove_strategy_by_name(self, name: str):
        """
        [新增] 根据名称移除策略 (方便远程控制)
        """
        with self._lock:
            target = next((s for s in self._strategies if s.name == name), None)
            if target:
                self.remove_strategy(target)  # 复用逻辑
            else:
                SysLogger.warning(
                    self, f"Cannot remove strategy '{name}': Name not found."
                )

    def remove_strategy_by_index(self, index: int):
        """[接口实现] 根据索引移除策略"""
        with self._lock:
            if 0 <= index < len(self._strategies):
                target = self._strategies[index]
                self.remove_strategy(target)  # 复用逻辑
            else:
                SysLogger.warning(
                    self, f"Cannot remove strategy at index {index}: Out of bounds."
                )

    # --- [生命周期 & 辅助] ---

    def _bind_pipeline_context(self, strategy: IStrategy):
        if isinstance(strategy, IPipelineAware):
            strategy.set_pipeline(self)
        strategy.set_log_policy(self.log_policy)

    def set_log_policy(self, policy: LogPolicy):
        self._log_policy = policy
        with self._lock:
            for s in self._strategies:
                s.set_log_policy(policy)

    def cleanup(self):
        """
        [接口实现] 公有的清理方法
        原 _cleanup 重命名而来，满足 IPipeline 接口要求
        清理所有策略
        """
        # 注意：这里不需要 CoW，因为是销毁过程
        for s in self._strategies:
            try:
                s.cleanup()
            except Exception as e:
                SysLogger.warning(self, f"Cleanup error in {s.name}: {e}")
        self._strategies.clear()

        # 清理上下文
        self.context.clear()
        SysLogger.info(self, "Pipeline resources cleaned up.")

    @property
    def layout(self) -> PipelineLayout:
        # (保持原有的实现)
        idx_map: Dict[int, str] = {}
        name_map: Dict[str, List[int]] = defaultdict(list)
        ordered: List[Tuple[int, str]] = []
        with self._lock:  # 读取时加锁是安全的，或者像 step 一样获取引用
            current = self._strategies
            for idx, strategy in enumerate(current):
                s_name = strategy.name
                idx_map[idx] = s_name
                name_map[s_name].append(idx)
                ordered.append((idx, s_name))
        return PipelineLayout(idx_map, dict(name_map), ordered)

    def print_layout(self):
        """
        [接口实现] 打印当前布局
        优化点：
        1. 使用 SysLogger 替代 print，保持日志系统统一。
        2. 使用字符串拼接，原子性输出，防止多线程打印交错。
        3. 增强视觉效果 (Tree Style)。
        """
        layout = self.layout  # 获取快照 (Thread-Safe)

        # 1. 构建头部
        lines = []
        lines.append(f"\n{'='*40}")
        lines.append(f" 🚀 Pipeline Layout: {self.name}")
        lines.append(f"{'='*40}")

        # 2. 构建内容 (Tree Style)
        count = len(layout.ordered_items)
        if count == 0:
            lines.append("   (Empty Pipeline)")
        else:
            for i, (idx, name) in enumerate(layout.ordered_items):
                is_last = i == count - 1
                prefix = "   └──" if is_last else "   ├──"
                lines.append(f"{prefix} [{idx}] {name}")

        lines.append(f"{'-'*40}\n")

        # 3. 原子性输出 (作为一条 INFO 日志)
        # 这样无论多少个线程同时打印，每个 Pipeline 的布局都会完整显示在一起
        full_message = "\n".join(lines)
        SysLogger.info(self, full_message)
