"""
绘图规范管理 CRUD
"""
from typing import Optional
import json

from loguru import logger
from sqlalchemy.orm import Session

from models.standard import DrawingStandard, LayerConfig


class StandardsManager:
    """绘图规范管理类"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self) -> Optional[DrawingStandard]:
        """获取当前激活的规范"""
        return (
            self.db.query(DrawingStandard)
            .filter_by(is_active=True)
            .first()
        )

    def get_by_id(self, standard_id: int) -> Optional[DrawingStandard]:
        """通过 ID 获取规范"""
        return self.db.query(DrawingStandard).filter_by(id=standard_id).first()

    def get_by_name(self, name: str) -> Optional[DrawingStandard]:
        """通过名称获取规范"""
        return self.db.query(DrawingStandard).filter_by(name=name).first()

    def list_all(self) -> list[DrawingStandard]:
        """获取所有规范"""
        return self.db.query(DrawingStandard).order_by(DrawingStandard.id).all()

    def create(
        self,
        name: str,
        description: str = "",
        version: str = "1.0",
        text_style: str = "Standard",
        text_height: float = 3.5,
        dim_style: str = "Standard",
        title_block: Optional[dict] = None,
    ) -> DrawingStandard:
        """创建新规范"""
        existing = self.get_by_name(name)
        if existing:
            raise ValueError(f"Standard '{name}' already exists")

        standard = DrawingStandard(
            name=name,
            description=description,
            version=version,
            text_style=text_style,
            text_height=text_height,
            dim_style=dim_style,
            title_block=json.dumps(title_block or {}, ensure_ascii=False),
            is_active=False,
        )
        self.db.add(standard)
        self.db.commit()
        self.db.refresh(standard)
        logger.info(f"Standard created: {name}")
        return standard

    def activate(self, standard_id: int) -> Optional[DrawingStandard]:
        """激活指定规范（取消其他规范的激活状态）"""
        # 取消所有规范的激活状态
        self.db.query(DrawingStandard).update({"is_active": False})

        standard = self.get_by_id(standard_id)
        if not standard:
            return None

        standard.is_active = True
        self.db.commit()
        self.db.refresh(standard)
        logger.info(f"Standard activated: {standard.name}")
        return standard

    def update(self, standard_id: int, **kwargs) -> Optional[DrawingStandard]:
        """更新规范属性"""
        standard = self.get_by_id(standard_id)
        if not standard:
            return None

        allowed = {"name", "description", "version", "text_style", "text_height", "dim_style"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(standard, field, value)
            elif field == "title_block" and isinstance(value, dict):
                standard.title_block = json.dumps(value, ensure_ascii=False)

        self.db.commit()
        self.db.refresh(standard)
        return standard

    def delete(self, standard_id: int) -> bool:
        """删除规范（如为激活规范则拒绝删除）"""
        standard = self.get_by_id(standard_id)
        if not standard:
            return False
        if standard.is_active:
            raise ValueError("Cannot delete the active standard")
        self.db.delete(standard)
        self.db.commit()
        return True

    def add_layer(
        self,
        standard_id: int,
        layer_name: str,
        color_index: int = 7,
        linetype: str = "Continuous",
        lineweight: float = 0.25,
        description: str = "",
    ) -> LayerConfig:
        """向规范添加图层配置"""
        layer = LayerConfig(
            standard_id=standard_id,
            layer_name=layer_name,
            color_index=color_index,
            linetype=linetype,
            lineweight=lineweight,
            description=description,
        )
        self.db.add(layer)
        self.db.commit()
        self.db.refresh(layer)
        return layer

    def get_active_context(self) -> dict:
        """
        获取当前激活规范的上下文信息（供 Agent 使用）

        Returns:
            包含规范信息的字典
        """
        standard = self.get_active()
        if not standard:
            return {
                "name": "未配置规范",
                "text_height": 3.5,
                "layers": [],
            }

        return {
            "name": standard.name,
            "version": standard.version,
            "text_style": standard.text_style,
            "text_height": standard.text_height,
            "dim_style": standard.dim_style,
            "layers": [
                {
                    "layer_name": layer.layer_name,
                    "color_index": layer.color_index,
                    "linetype": layer.linetype,
                    "lineweight": layer.lineweight,
                    "description": layer.description,
                }
                for layer in standard.layers
            ],
        }
