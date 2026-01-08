# core/factories/frame_factory.py
import threading

from core.ecs.frame import Frame


class FrameFactory:
    """
    [单例工厂] 负责 Frame 的生产与回收
    ECS 角色: Entity Spawner
    """

    _id_counter = 0
    _lock = threading.Lock()

    @staticmethod
    # [优化] 明确 context 类型为接口
    def create() -> Frame:
        with FrameFactory._lock:
            FrameFactory._id_counter += 1
            fid = FrameFactory._id_counter
        # 思考题：_id_counter 溢出问题？
        # Python 的 int 是动态精度的，只要内存够，理论上不会溢出。
        # 如果是长期运行的服务器，达到百亿级可能需要重置逻辑，但在本地运行通常不需要。
        return Frame(fid)
