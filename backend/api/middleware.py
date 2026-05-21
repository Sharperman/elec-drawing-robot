"""
全局中间件
- 请求日志记录
- 全局异常处理
- CORS（在 main.py 已配置，此处补充异常处理）
"""
import time
import traceback
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from utils.error_codes import ErrorCode, get_error_message


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器"""

    @app.middleware("http")
    async def request_logger(request: Request, call_next: Callable):
        """请求/响应日志中间件"""
        start = time.perf_counter()
        response = None

        try:
            response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(
                f"{request.method} {request.url.path} "
                f"-> {response.status_code} "
                f"({elapsed:.1f}ms)"
            )
            return response
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"{request.method} {request.url.path} "
                f"-> ERROR ({elapsed:.1f}ms): {exc}"
            )
            raise

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """处理值验证错误"""
        logger.warning(f"ValueError: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "code": ErrorCode.VALIDATION_ERROR,
                "message": str(exc),
                "data": None,
            },
        )

    @app.exception_handler(ConnectionError)
    async def connection_error_handler(request: Request, exc: ConnectionError):
        """处理 AutoCAD 连接错误"""
        logger.warning(f"ConnectionError: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "code": ErrorCode.AUTOCAD_NOT_CONNECTED,
                "message": get_error_message(ErrorCode.AUTOCAD_NOT_CONNECTED),
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        tb = traceback.format_exc()
        logger.error(f"Unhandled exception: {exc}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.UNKNOWN_ERROR,
                "message": get_error_message(ErrorCode.UNKNOWN_ERROR),
                "data": {"detail": str(exc)[:500]},
            },
        )
