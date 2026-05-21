"""
数据库初始化脚本
创建数据库表并导入默认数据（图元符号库、绘图规范）
"""
import asyncio
import json
import sys
from pathlib import Path

# 添加 backend 目录到路径
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from loguru import logger


async def import_default_data() -> None:
    """
    导入默认图元符号和规范数据
    如果数据已存在则跳过（幂等操作）
    """
    from models.session import get_session_local
    from models.symbol import Symbol
    from models.standard import DrawingStandard, LayerConfig

    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        # ---- 导入默认图元符号 ----
        symbols_file = BACKEND_DIR / "knowledge" / "data" / "symbols" / "symbols.json"
        if symbols_file.exists():
            with open(symbols_file, "r", encoding="utf-8") as f:
                symbols_data = json.load(f)

            existing_count = db.query(Symbol).count()
            if existing_count == 0:
                for item in symbols_data.get("symbols", []):
                    symbol = Symbol(
                        symbol_id=item["symbol_id"],
                        name=item["name"],
                        name_en=item.get("name_en", ""),
                        category=item.get("category", "general"),
                        standard=item.get("standard", "GB/T 4728"),
                        description=item.get("description", ""),
                        block_name=item.get("block_name", ""),
                        layer=item.get("layer", "0"),
                        width=item.get("width", 1.0),
                        height=item.get("height", 1.0),
                        tags=json.dumps(item.get("tags", []), ensure_ascii=False),
                    )
                    db.add(symbol)
                db.commit()
                logger.info(f"Imported {len(symbols_data.get('symbols', []))} symbols")
            else:
                logger.info(f"Symbols already exist ({existing_count} records), skipping")
        else:
            logger.warning(f"Symbols file not found: {symbols_file}")

        # ---- 导入默认绘图规范 ----
        standards_file = BACKEND_DIR / "knowledge" / "data" / "standards" / "default_standard.json"
        if standards_file.exists():
            with open(standards_file, "r", encoding="utf-8") as f:
                standard_data = json.load(f)

            existing_std = db.query(DrawingStandard).filter_by(
                name=standard_data["name"]
            ).first()

            if existing_std is None:
                standard = DrawingStandard(
                    name=standard_data["name"],
                    description=standard_data.get("description", ""),
                    version=standard_data.get("version", "1.0"),
                    is_active=True,
                    text_style=standard_data.get("text_style", "Standard"),
                    text_height=standard_data.get("text_height", 3.5),
                    dim_style=standard_data.get("dim_style", "Standard"),
                    title_block=json.dumps(
                        standard_data.get("title_block", {}), ensure_ascii=False
                    ),
                )
                db.add(standard)
                db.flush()

                # 导入图层配置
                for layer_item in standard_data.get("layers", []):
                    layer = LayerConfig(
                        standard_id=standard.id,
                        layer_name=layer_item["layer_name"],
                        color_index=layer_item.get("color_index", 7),
                        linetype=layer_item.get("linetype", "Continuous"),
                        lineweight=layer_item.get("lineweight", 0.25),
                        description=layer_item.get("description", ""),
                    )
                    db.add(layer)

                db.commit()
                logger.info(f"Imported standard: {standard_data['name']}")
            else:
                logger.info(f"Standard '{standard_data['name']}' already exists, skipping")
        else:
            logger.warning(f"Standards file not found: {standards_file}")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to import default data: {e}")
        raise
    finally:
        db.close()


async def main() -> None:
    """主函数"""
    logger.info("=== Initializing Database ===")

    # 创建表
    from models.session import create_all_tables
    create_all_tables()

    # 导入默认数据
    await import_default_data()

    logger.info("=== Database initialization complete ===")


if __name__ == "__main__":
    asyncio.run(main())
