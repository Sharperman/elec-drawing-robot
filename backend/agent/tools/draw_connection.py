"""
DrawConnection Tool
连接两个图元，绘制母线或导线
"""
import json
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
    via_points: Optional[str] = Field(
        None,
        description="折线途径点列表，JSON 字符串如 [[x1,y1],[x2,y2]]"
    )


class DrawConnectionTool(BaseTool):
    """
    LangChain Tool：连接两个图元，绘制母线/导线

    根据两个图元的 Handle 获取其位置，绘制连接线。
    支持直线和折线连接。
    """

    # CanvasState 注入（由 DrawAgent 在构建工具时设置）
    canvas_state: object = Field(default=None, exclude=True)

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
        via_points: Optional[str] = None,
    ) -> str:
        """执行连线操作"""
        import pythoncom
        pythoncom.CoInitialize()

        try:
            import win32com.client
            from config import settings

            # 在当前线程获取 COM dispatch（不用心跳线程的 doc，避免跨线程 HandleToObject 失败）
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            ms = doc.ModelSpace

            target_layer = layer or self._LINE_LAYER_MAP.get(line_type, "ELEC-WIRE")

            # 在当前 COM 会话中确保图层存在
            _ensure_layer_in_session(doc, target_layer)

            # 解析 via_points
            parsed_via: list[list[float]] = []
            if via_points:
                try:
                    parsed_via = json.loads(via_points)
                    if not isinstance(parsed_via, list):
                        parsed_via = []
                except (json.JSONDecodeError, TypeError):
                    return f"错误：via_points 格式无效，应为 JSON 数组如 [[x1,y1],[x2,y2]]，收到: {via_points}"

            # 获取起点图元的坐标
            try:
                from_entity = doc.HandleToObject(from_handle)
                from_x, from_y = _get_entity_center(from_entity)
            except Exception as e:
                return f"错误：无法获取图元 {from_handle} 的位置: {e}"

            try:
                to_entity = doc.HandleToObject(to_handle)
                to_x, to_y = _get_entity_center(to_entity)
            except Exception as e:
                return f"错误：无法获取图元 {to_handle} 的位置: {e}"

            # 绘制连线（不用 AutoCADTransaction，避免跨线程 Undo 标记问题）
            import win32com.client as wc
            handles: list[str] = []

            if parsed_via:
                all_points = [[from_x, from_y]] + parsed_via + [[to_x, to_y]]
                for i in range(len(all_points) - 1):
                    p1, p2 = all_points[i], all_points[i + 1]
                    h = _draw_line_segment(ms, p1[0], p1[1], p2[0], p2[1], target_layer)
                    handles.append(h)
            else:
                h = _draw_line_segment(ms, from_x, from_y, to_x, to_y, target_layer)
                handles.append(h)

            logger.info(
                f"DrawConnection success: {from_handle} -> {to_handle} "
                f"type={line_type} layer={target_layer}"
            )

            # ── 更新 CanvasState ──────────────────────────────
            if self.canvas_state is not None:
                self.canvas_state.record_connection(
                    from_handle=from_handle,
                    to_handle=to_handle,
                    line_type=line_type,
                    layer=target_layer,
                    via_points=parsed_via if parsed_via else None,
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


def _ensure_layer_in_session(doc, layer_name: str) -> None:
    """在当前 COM 会话中确保图层存在"""
    layers = doc.Layers
    for i in range(layers.Count):
        if layers.Item(i).Name.upper() == layer_name.upper():
            return
    try:
        new_layer = layers.Add(layer_name)
        new_layer.Color = 7
    except Exception as e:
        logger.warning(f"Failed to create layer {layer_name}: {e}")


def _get_entity_center(entity) -> tuple[float, float]:
    """获取 AutoCAD 实体的中心坐标，兼容 BlockRef(InsertionPoint) 和 Polyline(GetBoundingBox)"""
    try:
        pt = entity.InsertionPoint
        return float(pt[0]), float(pt[1])
    except Exception:
        pass
    try:
        min_pt = entity.GetBoundingBox(None, None)[0]
        max_pt = entity.GetBoundingBox(None, None)[1]
        return (float(min_pt[0]) + float(max_pt[0])) / 2, (float(min_pt[1]) + float(max_pt[1])) / 2
    except Exception:
        pass
    raise RuntimeError(f"Cannot get position for {entity.ObjectName}")


def _draw_line_segment(ms, x1: float, y1: float, x2: float, y2: float, layer: str) -> str:
    """在当前 COM 会话中绘制一条直线段，返回 Handle"""
    import pythoncom
    import win32com.client

    p1 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x1, y1, 0.0])
    p2 = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [x2, y2, 0.0])
    line = ms.AddLine(p1, p2)
    line.Layer = layer
    return line.Handle
