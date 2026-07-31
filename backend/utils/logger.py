"""
日志配置
使用 loguru 进行日志管理，支持文件轮转、彩色控制台输出
"""
from pathlib import Path
import sys

from loguru import logger


def setup_logger() -> logger.__class__:
    """
    初始化 loguru logger

    Returns:
        配置完成的 logger 实例
    """
    # 避免重复配置
    logger.remove()

    # 延迟导入，避免循环依赖
    from config import settings

    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 控制台输出（彩色，仅显示 INFO 及以上）
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        enqueue=True,
    )

    # 文件输出（全量日志，按大小轮转）
    logger.add(
        log_dir / "app.log",
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    # 错误专用日志文件
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}\n{exception}"
        ),
        rotation="5 MB",
        retention="60 days",
        compression="zip",
        enqueue=True,
        encoding="utf-8",
    )

    logger.info(f"Logger initialized. Log directory: {log_dir}")
    return logger
