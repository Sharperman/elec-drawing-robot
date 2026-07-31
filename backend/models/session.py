"""
SQLAlchemy 数据库会话管理
"""
from collections.abc import Generator
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _get_db_url() -> str:
    """延迟获取数据库 URL（避免循环导入）"""
    from config import settings
    if settings.DB_PATH == ":memory:":
        return "sqlite:///:memory:"
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


def _create_engine():
    """创建 SQLAlchemy Engine"""
    from config import settings
    db_url = _get_db_url()
    if settings.DB_PATH == ":memory:":
        # 内存数据库使用默认 SingletonThreadPool，不支持 pool_size/max_overflow
        engine = create_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
        )
    else:
        engine = create_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,  # SQLite 多线程支持
                "timeout": 30,
            },
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )

    # 启用 WAL 模式（提升 SQLite 并发性能）
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


# 全局 Engine 和 SessionLocal（懒加载）
_engine = None
_SessionLocal = None


def get_engine():
    """获取数据库引擎（单例）"""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_local():
    """获取 SessionLocal 工厂（单例）"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _SessionLocal


def create_all_tables() -> None:
    """创建所有数据库表（如不存在则创建）"""
    # 导入所有模型以注册到 Base.metadata
    from models.drawing_pattern import DrawingPattern  # noqa: F401
    from models.drawing_session import ChatMessage, DrawingSession  # noqa: F401
    from models.feedback import LearnedRule, UserFeedback  # noqa: F401
    from models.llm_provider import LLMProvider  # noqa: F401
    from models.standard import DrawingStandard, LayerConfig  # noqa: F401
    from models.symbol import Symbol  # noqa: F401

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database tables created/verified: {list(Base.metadata.tables.keys())}")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入：获取数据库会话

    Yields:
        SQLAlchemy Session 对象
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
