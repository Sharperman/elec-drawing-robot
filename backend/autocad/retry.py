"""
AutoCAD COM 操作重试装饰器
指数退避，最多重试 3 次
"""
from collections.abc import Callable
import functools
import time
from typing import Any, TypeVar

from loguru import logger

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_com_error(
    func: F = None,
    *,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    reraise: bool = True,
) -> F:
    """
    AutoCAD COM 操作重试装饰器

    在 COM 操作出现 pywintypes.com_error 或 ConnectionError 时自动重试，
    使用指数退避策略。

    Args:
        func: 被装饰的函数
        max_retries: 最大重试次数（默认 3）
        initial_delay: 初始等待时间（秒，默认 0.5）
        backoff_factor: 退避倍数（默认 2.0）
        reraise: 重试耗尽后是否重新抛出异常（默认 True）

    Example:
        @retry_on_com_error
        def insert_block(self, ...):
            ...

        @retry_on_com_error(max_retries=5, initial_delay=1.0)
        def get_entities(self):
            ...
    """
    # 支持 @retry_on_com_error 和 @retry_on_com_error(max_retries=5) 两种调用方式
    if func is None:
        return functools.partial(
            retry_on_com_error,
            max_retries=max_retries,
            initial_delay=initial_delay,
            backoff_factor=backoff_factor,
            reraise=reraise,
        )  # type: ignore

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from config import settings
        actual_max_retries = max_retries or settings.AUTOCAD_MAX_RETRY
        delay = initial_delay
        last_exception: Exception = RuntimeError("Unknown error")

        for attempt in range(1, actual_max_retries + 1):
            try:
                return func(*args, **kwargs)
            except ConnectionError as e:
                # AutoCAD 未连接，不重试
                logger.error(f"AutoCAD not connected in {func.__name__}: {e}")
                raise
            except Exception as e:
                last_exception = e
                # 判断是否为 COM 错误
                error_name = type(e).__name__
                is_com_error = (
                    "com_error" in error_name.lower()
                    or "COMError" in error_name
                    or "pywintypes" in str(type(e).__module__)
                )

                if not is_com_error:
                    # 非 COM 错误直接抛出
                    raise

                if attempt < actual_max_retries:
                    logger.warning(
                        f"COM error in {func.__name__} "
                        f"(attempt {attempt}/{actual_max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(
                        f"COM error in {func.__name__} "
                        f"exhausted {actual_max_retries} retries: {e}"
                    )

        if reraise:
            raise RuntimeError(
                f"AutoCAD COM 操作失败（{func.__name__}），"
                f"重试 {actual_max_retries} 次后仍失败: {last_exception}"
            ) from last_exception
        return None

    return wrapper  # type: ignore
