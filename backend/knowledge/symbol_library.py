"""
图元符号库 CRUD 操作
"""
import json

from loguru import logger
from models.symbol import Symbol
from sqlalchemy.orm import Session


class SymbolLibrary:
    """图元符号库管理类"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, symbol_id: str) -> Symbol | None:
        """通过 symbol_id 获取符号"""
        return self.db.query(Symbol).filter_by(symbol_id=symbol_id, is_active=True).first()

    def get_by_pk(self, pk: int) -> Symbol | None:
        """通过数据库主键获取符号"""
        return self.db.query(Symbol).filter_by(id=pk, is_active=True).first()

    def list_all(
        self,
        category: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Symbol], int]:
        """
        分页获取符号列表

        Args:
            category: 分类过滤
            search: 搜索关键词（匹配名称/描述/tags）
            page: 页码（从 1 开始）
            page_size: 每页数量

        Returns:
            (符号列表, 总数) 元组
        """
        query = self.db.query(Symbol).filter_by(is_active=True)

        if category:
            query = query.filter(Symbol.category == category)

        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                Symbol.name.ilike(like_pattern)
                | Symbol.name_en.ilike(like_pattern)
                | Symbol.description.ilike(like_pattern)
                | Symbol.tags.ilike(like_pattern)
            )

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    def create(
        self,
        symbol_id: str,
        name: str,
        name_en: str = "",
        category: str = "general",
        description: str = "",
        block_name: str = "",
        layer: str = "ELEC-SYMBOL",
        width: float = 1.0,
        height: float = 1.0,
        tags: list[str] | None = None,
    ) -> Symbol:
        """创建新图元符号"""
        existing = self.get_by_id(symbol_id)
        if existing:
            raise ValueError(f"Symbol '{symbol_id}' already exists")

        symbol = Symbol(
            symbol_id=symbol_id,
            name=name,
            name_en=name_en,
            category=category,
            description=description,
            block_name=block_name,
            layer=layer,
            width=width,
            height=height,
            tags=json.dumps(tags or [], ensure_ascii=False),
            is_builtin=False,
        )
        self.db.add(symbol)
        self.db.commit()
        self.db.refresh(symbol)
        logger.info(f"Symbol created: {symbol_id}")
        return symbol

    def update(
        self,
        symbol_id: str,
        **kwargs,
    ) -> Symbol | None:
        """更新图元符号属性"""
        symbol = self.get_by_id(symbol_id)
        if not symbol:
            return None

        allowed_fields = {
            "name", "name_en", "description", "block_name",
            "layer", "width", "height", "is_active",
        }
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(symbol, field, value)
            elif field == "tags" and isinstance(value, list):
                symbol.tags = json.dumps(value, ensure_ascii=False)

        self.db.commit()
        self.db.refresh(symbol)
        logger.info(f"Symbol updated: {symbol_id}")
        return symbol

    def delete(self, symbol_id: str) -> bool:
        """软删除图元符号"""
        symbol = self.get_by_id(symbol_id)
        if not symbol:
            return False
        symbol.is_active = False
        self.db.commit()
        logger.info(f"Symbol deleted (soft): {symbol_id}")
        return True

    def search_by_name(self, name: str, limit: int = 10) -> list[Symbol]:
        """通过名称模糊搜索"""
        return (
            self.db.query(Symbol)
            .filter(Symbol.is_active == True)
            .filter(
                Symbol.name.ilike(f"%{name}%")
                | Symbol.name_en.ilike(f"%{name}%")
            )
            .limit(limit)
            .all()
        )
