"""
DrawConnection Tool
连接两个图元，绘制母线或导线
"""
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from loguru import logger


class DrawConnectionInput(BaseModel):
    """DrawConnection 工具输入参数"""
    from_handle: str = Field(..., description="起始图元的 AutoCAD Handle")
    to_handle: str = Field(..., description="终止图元的 AutoCAD Handle")
    line_type: str = Field(
        default="wire",
        description="连线类型：bus=母线（粗线），wire=导线（细线），cable=电缆"
    )
    layer: Optional[str] = Field(
        None,
        description="连线图层，不填则根据 line_type 自动选择"
    )
    via_points: Optional[list[list[float]]] = Field(
        None,
        description="折线途径点列表，如 [[x1,y1],[x2,y2]]"
    )


class DrawConnectionTool(BaseTool):
    """
    LangChain Tool：连接两个图元，绘制母线/导线

    根据两个图元的 Handle 获取其位置，绘制连接线。
    支持直线和折线连接。
    """

    name: str = "draw_connection"
    description: str = (
        "在 AutoCAD 中连接两个电气图元，绘制母线或导线。"
        "需要提供两个图元的 Handle（由 insert_element 返回）。"
        "line_type 可选：bus（母线）、wire（导线）、cable（电缆）。"
    )
    args_schema: Type[BaseModel] = DrawConnectionInput

    # 连线类型与图层的映射
    _LINE_LAYER_MAP: dict[str, str] = {
        "bus": "ELEC-BUS",
        "wire": "ELEC-WIRE",
        "cable": "ELEC-CABLE",
    }

    def _run(
        self,
        from_handle: str,
        to_handle: str,
        line_type: str = "wire",
        layer: Optional[str] = None,
        via_points: Optional[list[list[float]]] = None,
    ) -> str:
        """执行连线操作"""
        try:
            from autocad.connection import autocad_connection
            from autocad.drawing_ops import drawing_ops
            from autocad.layer_manager import layer_manager
            from autocad.transaction import AutoCADTransaction

            doc = autocad_connection.doc
            target_layer = layer or self._LINE_LAYER_MAP.get(line_type, "ELEC-WIRE")

            # 确保图层存在
            layer_manager.ensure_layer(target_layer)

            # 获取起点图元的坐标
            from_entity = doc.HandleToObject(from_handle)
            to_entity = doc.HandleToObject(to_handle)

            try:
                from_pt = from_entity.InsertionPoint
                from_x, from_y = float(from_pt[0]), float(from_pt[1])
            except Exception:
                return f"错误：无法获取图元 {from_handle} 的位置"

            try:
                to_pt = to_entity.InsertionPoint
                to_x, to_y = float(to_pt[0]), float(to_pt[1])
            except Exception:
                return f"错误：无法获取图元 {to_handle} 的位置"

            # 绘制连线
            with AutoCADTransaction(f"connect_{from_handle}_{to_handle}") as txn:
                handles: list[str] = []

                if via_points:
                    # 绘制折线（通过中间点）
                    all_points = [[from_x, from_y]] + via_points + [[to_x, to_y]]
                    for i in range(len(all_points) - 1):
                        p1, p2 = all_points[i], all_points[i + 1]
                        h = drawing_ops.draw_line(
                            x1=p1[0], y1=p1[1],
                            x2=p2[0], y2=p2[1],
                            layer=target_layer,
                        )
                        handles.append(h)
                else:
                    # 直线连接
                    h = drawing_ops.draw_line(
                        x1=from_x, y1=from_y,
                        x2=to_x, y2=to_y,
                        layer=target_layer,
                    )
                    handles.append(h)

                txn.commit()

            logger.info(
                f"DrawConnection success: {from_handle} -> {to_handle} "
                f"type={line_type} layer={target_layer}"
            )
            type_names = {"bus": "母线", "wire": "导线", "cable": "电缆"}
            type_label = type_names.get(line_type, "连线")
            return (
                f"成功绘制{type_label}，"
                f"从 ({from_x:.1f},{from_y:.1f}) 到 ({to_x:.1f},{to_y:.1f})，"
                f"图层: {target_layer}，Handle(s): {', '.join(handles)}"
            )

        except ConnectionError:
            return "错误：AutoCAD 未连接，请先连接 AutoCAD"
        except Exception as e:
            logger.error(f"DrawConnection failed: {e}")
            return f"绘制连线失败: {e}"

    async def _arun(self, **kwargs) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
