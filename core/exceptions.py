from typing import Optional


class FlowError(Exception):
    """基础异常类"""

    pass


class StrategyExecutionError(FlowError):
    """
    策略执行期间发生的错误
    """

    def __init__(
        self,
        message: str,
        strategy_name: str,
        original_error: Optional[Exception] = None,  # [关键修复] 必须要有这个参数
    ):
        # 构造详细的错误信息
        full_msg = f"[{strategy_name}] {message}"
        if original_error:
            full_msg += (
                f" | Caused by: {type(original_error).__name__}: {original_error}"
            )

        super().__init__(full_msg)

        self.strategy_name = strategy_name
        self.original_error = original_error


class PipelineConfigError(FlowError):
    """管线配置错误"""

    pass


class ResourceError(FlowError):
    """资源（如摄像头、内存）错误"""

    pass


# [新增] 致命错误定义
class PipelineCriticalError(FlowError):
    """
    [致命错误] 当发生不可恢复的错误时抛出。
    Executor 捕获此错误后会触发熔断机制 (Stop Pipeline)。
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error
