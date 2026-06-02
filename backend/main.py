"""
FastAPI 应用入口
注册所有路由、CORS、lifespan 事件、健康检查
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logger import setup_logger
from models.session import create_all_tables
from api.middleware import register_exception_handlers
from api.routes import chat, recognition, autocad, standards, symbols, feedback

# 初始化日志（最先执行）
logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理：
    - startup：初始化数据库表、预加载模型、连接 AutoCAD
    - shutdown：释放资源
    """
    logger.info("=== ElecDrawingRobot Backend Starting ===")
    logger.info(f"Environment: PORT={settings.PORT}, DB={settings.DB_PATH}")

    # 1. 创建数据库表
    create_all_tables()
    logger.info("Database tables initialized")

    # 2. 预热向量数据库
    try:
        from knowledge.vector_store import vector_store
        await vector_store.initialize()
        logger.info("Vector store initialized")
    except Exception as e:
        logger.warning(f"Vector store initialization failed (non-fatal): {e}")

    # 3. 导入默认数据（图元符号库 + 规范）
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_dir = str(_Path(__file__).parent.parent / "scripts")
        if _scripts_dir not in _sys.path:
            _sys.path.insert(0, _scripts_dir)
        from init_db import import_default_data
        await import_default_data()
        logger.info("Default data imported")
    except Exception as e:
        logger.warning(f"Default data import failed (non-fatal): {e}")

    # 4. 预热 YOLOv8 检测器（懒加载，此处只触发线程预热）
    try:
        from recognition.detector import detector
        detector.warmup()
        logger.info("YOLOv8 detector warmed up")
    except Exception as e:
        logger.warning(f"Detector warmup failed (non-fatal): {e}")

    logger.info("=== Application startup complete ===")

    yield

    # ---- shutdown ----
    logger.info("=== ElecDrawingRobot Backend Shutting Down ===")
    try:
        from autocad.connection import autocad_connection
        autocad_connection.disconnect()
        logger.info("AutoCAD connection closed")
    except Exception as e:
        logger.warning(f"AutoCAD disconnect failed: {e}")


# ============================================================
# 应用实例
# ============================================================

app = FastAPI(
    title="电气图纸绘制机器人 API",
    description="AI 驱动的电气图纸自动绘制系统后端",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ============================================================
# CORS 中间件
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 全局异常处理 + 请求日志
# ============================================================

register_exception_handlers(app)

# ============================================================
# 路由注册
# ============================================================

app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(recognition.router, prefix="/api/recognize", tags=["Recognition"])
app.include_router(autocad.router, prefix="/api/autocad", tags=["AutoCAD"])
app.include_router(standards.router, prefix="/api/standards", tags=["Standards"])
app.include_router(symbols.router, prefix="/api/symbols", tags=["Symbols"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])


# ============================================================
# 健康检查端点
# ============================================================

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """健康检查：前端 Electron 主进程用于判断后端是否就绪"""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/", tags=["Health"])
async def root() -> dict:
    """根路径"""
    return {"message": "ElecDrawingRobot API is running", "docs": "/docs"}


# ============================================================
# 直接运行入口
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )
