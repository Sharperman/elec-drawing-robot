"""
DrawingPattern 数据模型 + JSON Schema 校验
存储从参考图纸中学习到的图纸模式
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, ValidationError
from loguru import logger

from models.session import Base


# ─── JSON 字段 Pydantic Schema ─────────────────────────────────

class TopologySchema(BaseModel):
    type: Optional[str] = Field(None, description="拓扑类型")
    voltage_levels: Optional[List[str]] = None


class DeviceSchema(BaseModel):
    type: str = Field(..., description="设备类型")
    label_pattern: Optional[str] = None
    count: Optional[int] = None


class AnnotationStyleSchema(BaseModel):
    font_height: Optional[float] = None
    prefixes: Optional[Dict[str, str]] = None
    position: Optional[str] = None


_PATTERN_SCHEMAS: Dict[str, type[BaseModel]] = {
    "topology": TopologySchema,
    "annotation_style": AnnotationStyleSchema,
}


def _validate_pattern_field(key: str, value: Any) -> Any:
    """校验 JSON 字段，失败时只记录 warning"""
    schema = _PATTERN_SCHEMAS.get(key)
    if schema is None or value is None:
        return value
    if isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    try:
        return schema(**value).model_dump()
    except (ValidationError, TypeError):
        return value


class DrawingPattern(Base):
    """
    图纸模式表

    从参考图纸中通过 LLM 学习后提取的结构化模式，
    包括拓扑结构、设备清单、布局规律、标注风格等。
    """
    __tablename__ = "drawing_patterns"

    id = Column(Integer, primary_key=True)
    # ── 基本信息 ──────────────────────────────
    name = Column(String(200), nullable=False, comment="模式名称（如'220kV双母线变电站主接线'）")
    description = Column(Text, comment="模式描述")
    source_file = Column(String(500), comment="来源图纸文件路径")
    source_type = Column(String(50), default="dwg", comment="来源类型：dwg / pdf / dxf / image")
    thumbnail_path = Column(String(500), comment="缩略图路径")

    # ── 结构化模式数据（JSON，由 LearnAgent 填充）──
    # 拓扑结构：{"type": "双母线带旁路", "voltage_levels": ["220kV","66kV"]}
    topology = Column(Text, comment="JSON - 拓扑结构")

    # 设备清单：[{"type":"断路器","label_pattern":"QF{}","typical_position":{"x":500,"y":800},"count":2}]
    devices = Column(Text, comment="JSON - 设备清单及典型位置")

    # 布局规律：["高压侧在上，低压侧在下","母线间距 800mm"]
    layout_rules = Column(Text, comment="JSON - 布局规律（人类可读规则）")

    # 标注风格：{"font_height": 3.5, "prefixes": {"breaker": "QF","transformer": "T"}, "position": "top_right"}
    annotation_style = Column(Text, comment="JSON - 标注风格")

    # 连接模式：[{"from_type":"母线","to_type":"断路器","via":"导线","layer":"ELEC-WIRE"}]
    connection_patterns = Column(Text, comment="JSON - 连接模式")

    # 图层规范：{"bus":"ELEC-BUS","wire":"ELEC-WIRE","device":"ELEC-DEVICE"}
    layer_spec = Column(Text, comment="JSON - 图层规范")

    # 制图习惯：{"title_block_position":"右下角","scale":"1:100",...}
    drawing_habits = Column(Text, comment="JSON - 制图习惯")

    # 电缆清单：[{"cable_id":"CABLE-01","type":"铜芯电缆",...}]
    cables_and_lines = Column(Text, comment="JSON - 电缆和导线清单")

    # 材料表：{"has_bom_table":true,"position":"右下角",...}
    bill_of_materials = Column(Text, comment="JSON - 材料表信息")

    # ezdxf 原始文本提取（用于 RAG 检索）
    dxf_text = Column(Text, comment="DXF 文本提取结果（用于 RAG）")

    # 视觉分析结果（JSON）
    visual_analysis = Column(Text, comment="JSON - 视觉 LLM 分析结果")

    # ── 统计字段 ──────────────────────────────
    usage_count = Column(Integer, default=0, comment="被引用次数")
    rating = Column(Integer, default=0, comment="用户评分 0-5")
    is_active = Column(Boolean, default=True, comment="是否启用")

    # ── 时间戳 ──────────────────────────────
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_pattern_active", "is_active"),
        Index("idx_pattern_created", "created_at"),
    )

    def to_dict(self) -> dict:
        """转为 dict（供 API 返回）"""
        import json

        def _parse(v: Optional[str]) -> Optional[object]:
            if v is None:
                return None
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v

        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source_file": self.source_file,
            "source_type": self.source_type,
            "thumbnail_path": self.thumbnail_path,
            "topology": _parse(self.topology),
            "devices": _parse(self.devices),
            "layout_rules": _parse(self.layout_rules),
            "annotation_style": _parse(self.annotation_style),
            "connection_patterns": _parse(self.connection_patterns),
            "layer_spec": _parse(self.layer_spec),
            "drawing_habits": _parse(self.drawing_habits),
            "cables_and_lines": _parse(self.cables_and_lines),
            "bill_of_materials": _parse(self.bill_of_materials),
            "dxf_text": self.dxf_text,
            "visual_analysis": _parse(self.visual_analysis),
            "usage_count": self.usage_count,
            "rating": self.rating,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def update_from_dict(self, d: dict) -> None:
        """从 dict 更新字段（供 API 编辑）"""
        import json

        for key in (
            "name", "description", "source_file", "source_type",
            "thumbnail_path", "is_active", "rating",
        ):
            if key in d:
                setattr(self, key, d[key])

        # JSON 字段：接受 dict 或 JSON 字符串，写入前校验
        for key in (
            "topology", "devices", "layout_rules",
            "annotation_style", "connection_patterns", "layer_spec",
            "visual_analysis", "drawing_habits", "cables_and_lines",
            "bill_of_materials",
        ):
            if key in d and d[key] is not None:
                val = d[key]
                validated = _validate_pattern_field(key, val)
                if isinstance(validated, (dict, list)):
                    setattr(self, key, json.dumps(validated, ensure_ascii=False))
                elif isinstance(val, str):
                    setattr(self, key, val)
