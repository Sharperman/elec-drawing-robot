"""
电气图元符号 ORM 模型
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.session import Base


class Symbol(Base):
    """
    电气图元符号库
    遵循 GB/T 4728 标准的符号定义
    """
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
        comment="符号唯一标识，如 CB_3P（三相断路器）"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="符号中文名称"
    )
    name_en: Mapped[str] = mapped_column(
        String(100), nullable=False, default="",
        comment="符号英文名称"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general", index=True,
        comment="分类：protection/switch/transformer/line/measurement/grounding/source/load/signal"
    )
    standard: Mapped[str] = mapped_column(
        String(50), nullable=False, default="GB/T 4728",
        comment="所属标准"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="符号描述，用于 RAG 检索"
    )
    block_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="",
        comment="AutoCAD 图块名称"
    )
    layer: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ELEC-SYMBOL",
        comment="默认插入图层"
    )
    width: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="符号宽度（单位：mm）"
    )
    height: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="符号高度（单位：mm）"
    )
    insertion_point: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="0,0",
        comment="插入基点坐标，如 '0,0'"
    )
    tags: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="标签列表（JSON 字符串），用于搜索"
    )
    svg_data: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="SVG 矢量预览图"
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="是否为内置符号"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Symbol symbol_id={self.symbol_id!r} name={self.name!r}>"
