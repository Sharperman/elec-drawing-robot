"""
QueryDrawing Tool
查询当前图纸中的图元列表和状态
"""
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from loguru import logger


class QueryDrawingInput(BaseModel):
    """QueryDrawing 工具输入参数"""
    filter_label: Optional[str] = Field(
        None,
        description="按设备标签过滤，如 'T1' 查询变压器 T1"
    )
    filter_layer: Optional[str] = Field(
        None,
        description="按图层过滤，如 'ELEC-PROTECT'"
    )
    filter_type: Optional[str] = Field(
        None,
        description="按图元类型过滤，如 'AcDbBlockReference'"
    )
    limit: int = Field(default=20, description="返回最多条数")


class QueryDrawingTool(BaseTool):
    """
    LangChain Tool：查询当前 AutoCAD 图纸的图元状态

    可过滤图层、图元类型或设备标签，用于获取图元 Handle 和位置信息
    以便后续操作。
    """

    name: str = "query_drawing"
    description: str = (
        "查询 AutoCAD 当前图纸中的图元列表。"
        "可按设备标签、图层或图元类型过滤。"
        "返回图元的 Handle、类型、图层和坐标，用于后续连接和修改操作。"
    )
    args_schema: Type[BaseModel] = QueryDrawingInput

    def _run(
        self,
        filter_label: Optional[str] = None,
        filter_layer: Optional[str] = None,
        filter_type: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """执行查询"""
        try:
            from autocad.drawing_ops import drawing_ops
            from autocad.connection import autocad_connection

            entities = drawing_ops.get_all_entities()

            # 应用过滤
            if filter_layer:
                entities = [e for e in entities if e.get("layer", "").upper() == filter_layer.upper()]

            if filter_type:
                entities = [e for e in entities if filter_type.lower() in e.get("entity_type", "").lower()]

            total = len(entities)
            entities = entities[:limit]

            if not entities:
                msg = "当前图纸为空"
                if filter_layer or filter_type or filter_label:
                    msg = f"未找到符合条件的图元（layer={filter_layer}, type={filter_type}）"
                return msg

            lines = [f"当前图纸共 {total} 个图元（显示前 {len(entities)} 条）：\n"]
            for i, e in enumerate(entities, 1):
                x_str = f"{e['x']:.1f}" if e.get("x") is not None else "N/A"
                y_str = f"{e['y']:.1f}" if e.get("y") is not None else "N/A"
                lines.append(
                    f"{i}. Handle={e['handle']} "
                    f"类型={e['entity_type']} "
                    f"图层={e['layer']} "
                    f"位置=({x_str},{y_str})"
                )

            return "\n".join(lines)

        except ConnectionError:
            return "AutoCAD 未连接，无法查询图纸"
        except Exception as e:
            logger.error(f"QueryDrawing failed: {e}")
            return f"查询图纸失败: {e}"

    async def _arun(self, **kwargs) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
