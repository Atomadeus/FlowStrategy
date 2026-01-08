# core/std_components.py
from dataclasses import dataclass, field
from typing import List, Dict, Any
import numpy as np
from core.ecs.components import Component

# --- 基础数据组件 ---


@dataclass
class ImageComponent(Component):
    """
    [标准组件] 承载图像数据
    """

    image: np.ndarray  # 图像矩阵 (H, W, C)
    device_index: int = 0  # 采集设备索引
    timestamp: float = 0.0  # 采集时间戳
    frame_index: int = 0  # 来源的帧序号


@dataclass
class ActionLogComponent(Component):
    """
    [标准组件] 通用操作日志
    替代 v2.5 的 add_result 用于调试或记录策略的简要行为
    """

    # Key: 策略名称, Value: 操作详情
    logs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def log(self, strategy_name: str, data: Dict[str, Any]):
        self.logs[strategy_name] = data


# --- 业务数据组件 ---


@dataclass
class DetectionObject:
    """
    [辅助数据类] 单个检测对象详情
    注意：这不是 Component，而是 Component 内部的数据结构
    """

    label: str
    conf: float
    box: List[float]  # [x1, y1, x2, y2]


@dataclass
class DetectionResultComponent(Component):
    """
    [标准组件] 承载 AI 检测结果 (YOLO / RT-DETR 等)
    """

    model_name: str
    count: int
    boxes: np.ndarray  # float32 [N, 4]
    scores: np.ndarray  # float32 [N]
    class_ids: np.ndarray  # int [N]
    class_names: Dict[int, str]

    # 结构化对象列表 (方便上层业务直接遍历使用)
    objects: List[DetectionObject] = field(default_factory=list)
