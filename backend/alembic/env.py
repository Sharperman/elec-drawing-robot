"""
Alembic 迁移环境配置
自动读取项目 config.py 中的数据库 URL 和所有 ORM 模型
"""
from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# 添加 backend 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from models.session import Base

# Alembic Config 对象
config = context.config

# 从项目配置读取数据库 URL（而非 alembic.ini）
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.DB_PATH}")

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 所有 ORM 模型的 MetaData（供 autogenerate 使用）
import models.drawing_pattern  # noqa: F401
import models.drawing_session  # noqa: F401
import models.feedback  # noqa: F401
import models.knowledge_document  # noqa: F401
import models.llm_provider  # noqa: F401
import models.standard  # noqa: F401
import models.symbol  # noqa: F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
