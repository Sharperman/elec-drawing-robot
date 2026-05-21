"""
AutoCAD 事务上下文管理器
支持 commit/rollback（通过 Undo 实现）
"""
from contextlib import contextmanager
from typing import Generator

from loguru import logger

from autocad.connection import autocad_connection


class AutoCADTransaction:
    """
    AutoCAD 事务上下文管理器
    
    AutoCAD COM 不支持真正的事务，但可通过 Undo/Redo 实现类似效果：
    - 进入事务时标记一个 Undo 组起始点
    - commit() 什么都不做（保留操作）
    - rollback() 调用 Undo 撤销到起始点
    
    用法：
        async with AutoCADTransaction() as txn:
            drawing_ops.insert_block(...)
            txn.commit()
    """

    def __init__(self, description: str = "AutoCAD Transaction") -> None:
        self.description = description
        self._committed: bool = False
        self._entered: bool = False

    def __enter__(self) -> "AutoCADTransaction":
        try:
            doc = autocad_connection.doc
            # 开始一个 Undo 组
            doc.StartUndoMark()
            self._entered = True
            logger.debug(f"Transaction started: {self.description}")
        except Exception as e:
            logger.warning(f"Failed to start undo mark: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            # 有异常时自动回滚
            logger.warning(
                f"Transaction failed with {exc_type.__name__}: {exc_val}. Rolling back..."
            )
            self._rollback()
            return False  # 不抑制异常

        if not self._committed:
            # 未显式 commit，也回滚
            logger.warning(
                f"Transaction not committed: {self.description}. Rolling back..."
            )
            self._rollback()

        return False

    def commit(self) -> None:
        """提交事务（结束 Undo 组，保留所有操作）"""
        try:
            doc = autocad_connection.doc
            doc.EndUndoMark()
            self._committed = True
            logger.debug(f"Transaction committed: {self.description}")
        except Exception as e:
            logger.warning(f"Failed to end undo mark: {e}")
            self._committed = True  # 即使失败也标记为提交

    def _rollback(self) -> None:
        """回滚事务（撤销所有操作）"""
        if not self._entered:
            return
        try:
            doc = autocad_connection.doc
            doc.EndUndoMark()  # 先关闭 Undo 组
            doc.SendCommand("UNDO 1\n")  # 撤销最近一组操作
            logger.info(f"Transaction rolled back: {self.description}")
        except Exception as e:
            logger.warning(f"Failed to rollback transaction: {e}")


@contextmanager
def autocad_transaction(description: str = "") -> Generator[AutoCADTransaction, None, None]:
    """
    事务上下文管理器（函数形式）

    Args:
        description: 事务描述，用于日志

    Usage:
        with autocad_transaction("插入变压器"):
            drawing_ops.insert_block(...)
    """
    txn = AutoCADTransaction(description=description)
    with txn:
        yield txn
