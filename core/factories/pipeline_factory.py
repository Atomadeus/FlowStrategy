# core/factories/pipeline_factory.py
from typing import List

from core.configs.enums import PipelineMode
from core.configs.policies import LogPolicy
from core.configs.settings import PipelineConfig
from core.event_system import EventRouter
from core.interfaces import IStrategy, IPipeline, IEventHub
from core.runtime.pipeline import Pipeline
from core.runtime.executor import PipelineExecutor


class PipelineFactory:

    # 默认的日志打印策略 (可以动态修改)
    _default_log_policy: LogPolicy = LogPolicy.default()

    @classmethod
    def set_global_log_policy(cls, policy: LogPolicy):
        """允许用户调整工厂的生产标准"""
        cls._default_log_policy = policy

    @staticmethod
    def create_pipeline(
        name: str,
        strategies: List[IStrategy],
        event_hub: IEventHub,  # <--- [关键] 接收 Application 传来的 Hub
        mode: PipelineMode = PipelineMode.LOOP,
    ) -> IPipeline:
        # 1. 定义一个“闭包工厂”，它捕获了外面的 event_hub 变量
        def scoped_router_factory(pipeline_ref) -> EventRouter:
            # 这里创建 Router 时，把捕获的 event_hub 塞进去
            return EventRouter(pipeline_ref, event_hub)

        # 2. 创建配置，将闭包工厂存入配置
        # 注意：这里假设 PipelineConfig 构造函数接收 router_factory
        config = PipelineConfig(
            _name=name,
            _strategies=strategies,
            _mode=mode,
            _router_factory=scoped_router_factory,  # <--- 注入闭包
        )

        # 3. 创建 Pipeline
        pipeline = Pipeline(config)

        # 应用默认日志策略
        # 确保新生产的管线遵守工厂设定的标准
        pipeline.set_log_policy(PipelineFactory._default_log_policy)
        # Pipeline.set_log_policy 内部通常会递归设置 strategies，
        # 但为了保险，也可以在这里显式设置（取决于 Pipeline 实现）
        # for s in strategies:
        #     s.set_log_policy(PipelineFactory._default_log_policy)

        return pipeline

    @staticmethod
    def create_executor(
        name: str, pipelines: List[IPipeline], event_hub: IEventHub
    ) -> PipelineExecutor:
        """
        创建并注册 Executor
        """
        # [核心修正] 将 event_hub 注入给 Executor，赋予其报警能力
        executor = PipelineExecutor(name, event_hub=event_hub)
        for p in pipelines:
            executor.add_pipeline(p)

        # [修复] 移除 PipelineManager.register_executor(executor)
        # 工厂只负责生产，注册的职责移交给 Application.add_pipeline 或 main 函数

        return executor  # 仅返回只读引用或无需返回，看具体需求
