# core/components.py
import abc
from dataclasses import dataclass


@dataclass
class Component(abc.ABC):
    """
    [组件基类]
    所有具体的数据组件（无论是框架自带的还是用户自定义的）都必须继承此类。
    这是一个标记类，也是 ECS 系统中所有数据的根类型。
    """

    pass
