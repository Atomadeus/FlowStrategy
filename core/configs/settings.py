from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from core.configs.enums import PipelineMode
from core.configs.policies import EventPolicy
from core.interfaces.ecs import IStrategy
from core.interfaces.pipeline import RouterFactory, IPipelineConfig


@dataclass(frozen=True)
class PipelineConfig(IPipelineConfig):
    """
    [配置聚合] 静态配置，一旦创建不可修改。
    """

    _name: str
    _strategies: List[IStrategy]
    _mode: PipelineMode = PipelineMode.LOOP
    _max_fps: int = 60  # 用于计算最大帧率间隔
    _enable_fps_control: bool = False  # 是否开启帧率控制
    _enable_profiling: bool = False  # 是否开启性能监控（日志警告）

    # 2. 这里直接使用 RouterFactory 类型别名
    # 这样代码更易读，而且明确了：自定义 Router 时，你有机会拿到 Pipeline 实例
    _router_factory: Optional[RouterFactory] = field(default=None)

    @property
    def router_factory(self):
        return self._router_factory

    # [优化] 使用字典配置特定事件的规则
    # 例如: { BallDetectedEvent: EventRule.SILENT }
    _event_policies: Dict[Any, EventPolicy] = field(default_factory=dict)

    @property
    def event_policies(self):
        return self._event_policies

    @property
    def name(self):
        return self._name

    @property
    def strategies(self):
        return self._strategies

    @property
    def mode(self):
        return self._mode

    @property
    def max_fps(self):
        return self._max_fps

    @property
    def enable_fps_control(self):
        return self._enable_fps_control

    @property
    def enable_profiling(self):
        return self._enable_profiling
