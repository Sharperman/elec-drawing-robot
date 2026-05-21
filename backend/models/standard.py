"""
绘图规范和图层配置 ORM 模型
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Float, Boolean, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.session import Base


class DrawingStandard(Base):
    """绘图规范（国标、行标、企标等）"""
    __tablename__ = "drawing_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False,
        comment="规范名称，如'国标GB/T 4728-2018'"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="规范描述"
    )
    version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0",
        comment="版本号"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否为当前激活规范"
    )
    # 文字样式
    text_style: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Standard",
        comment="AutoCAD 文字样式名"
    )
    text_height: Mapped[float] = mapped_column(
        Float, nullable=False, default=3.5,
        comment="默认文字高度（mm）"
    )
    # 标注样式
    dim_style: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Standard",
        comment="AutoCAD 标注样式名"
    )
    # 图框配置（JSON）
    title_block: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}",
        comment="图框配置（JSON 字符串）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow, server_default=func.now()
    )

    # 关联
    layers: Mapped[list["LayerConfig"]] = relationship(
        "LayerConfig",
        back_populates="standard",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DrawingStandard id={self.id} name={self.name!r} active={self.is_active}>"


class LayerConfig(Base):
    """图层配置（属于某个绘图规范）"""
    __tablename__ = "layer_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drawing_standards.id"), nullable=False, index=True
    )
    layer_name: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="图层名称，如 ELEC-POWER"
    )
    color_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7,
        comment="AutoCAD 颜色索引（1-255），7=白色"
    )
    linetype: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Continuous",
        comment="线型，如 Continuous/DASHED/CENTER"
    )
    lineweight: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.25,
        comment="线宽（mm）"
    )
    description: Mapped[str] = mapped_column(
        String(200), nullable=False, default="",
        comment="图层用途描述"
    )

    # 关联
    standard: Mapped[DrawingStandard] = relationship(
        "DrawingStandard", back_populates="layers"
    )

    def __repr__(self) -> str:
        return f"<LayerConfig layer={self.layer_name!r} color={self.color_index}>"
