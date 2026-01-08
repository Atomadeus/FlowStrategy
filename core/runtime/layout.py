# core/runtime/layout.py
from dataclasses import dataclass
from typing import List, Tuple, Dict

from core.interfaces import (
    IPipelineLayout,
)


@dataclass
class PipelineLayout(IPipelineLayout):
    """
    管线结构映射表，用于调试、UI显示或序列化。
    """

    _index_to_name: Dict[int, str]
    _name_to_index: Dict[str, List[int]]
    _ordered_items: List[Tuple[int, str]]

    @property
    def index_to_name(self):
        return self._index_to_name

    @property
    def name_to_index(self):
        return self._name_to_index

    @property
    def ordered_items(self):
        return self._ordered_items
