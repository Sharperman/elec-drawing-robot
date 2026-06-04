"""
AddAnnotation Tool
添加文字标注和尺寸标注
"""
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from loguru import logger


class AddAnnotationInput(BaseModel):
    """AddAnnotation 工具输入参数"""
    handle: Optional[str] = Field(
        None,
        description="目标图元 Handle（如提供，标注自动定位到图元旁边）"
    )
    label: str = Field(..., description="设备编号或标注文字，如 T1、QF1、10kV/0.4kV")
    params: Optional[str] = Field(None, description="设备参数文字，如 1000kVA、630A")
    x: Optional[float] = Field(None, description="标注 X 坐标（不提供 handle 时必填）")
    y: Optional[float] = Field(None, description="标注 Y 坐标（不提供 handle 时必填）")
    position: str = Field(
        default="bottom",
        description="标注位置相对图元：bottom/top/left/right"
    )
    text_height: float = Field(default=3.5, description="文字高度（mm）")
    annotation_type: str = Field(
        default="text",
        description="标注类型：text=文字，dim=尺寸标注，leader=引线标注"
    )


class AddAnnotationTool(BaseTool):
    """
    LangChain Tool：添加文字标注和尺寸标注

    支持三种标注类型：
    - text：普通文字标注（设备编号、参数）
    - dim：线性尺寸标注
    - leader：带引线的注释
    """

    # CanvasState 注入（由 DrawAgent 在构建工具时设置）
    canvas_state: object = Field(default=None, exclude=True)

    name: str = "add_annotation"
    description: str = (
        "向 AutoCAD 图纸中添加文字标注、尺寸标注或引线注释。"
        "可以通过图元 Handle 自动定位，也可以直接指定坐标。"
        "常用于添加设备编号（如 T1）和技术参数（如 10kV/0.4kV）。"
    )
    args_schema: Type[BaseModel] = AddAnnotationInput

    # 位置偏移量（相对于图元插入点，mm）
    _POSITION_OFFSETS: dict[str, tuple[float, float]] = {
        "bottom": (0.0, -6.0),
        "top": (0.0, 8.0),
        "left": (-8.0, 0.0),
        "right": (8.0, 0.0),
    }

    def _run(
        self,
        handle: Optional[str] = None,
        label: str = "",
        params: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        position: str = "bottom",
        text_height: float = 3.5,
        annotation_type: str = "text",
    ) -> str:
        """执行标注操作"""
        import pythoncom
        pythoncom.CoInitialize()

        try:
            import win32com.client
            from config import settings
            from autocad.annotation_ops import annotation_ops

            # 在当前线程获取 COM dispatch（不用心跳线程的 doc）
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument

            # 确定标注坐标
            if handle:
                try:
                    entity = doc.HandleToObject(handle)
                    base_x, base_y = _get_entity_center(entity)
                except Exception:
                    base_x, base_y = x or 0.0, y or 0.0

                offset = self._POSITION_OFFSETS.get(position, (0.0, -6.0))
                ann_x = base_x + offset[0]
                ann_y = base_y + offset[1]
            elif x is not None and y is not None:
                ann_x, ann_y = x, y
            else:
                return "错误：必须提供 handle 或坐标 (x, y)"

            handles: list[str] = []

            if annotation_type == "text":
                # 标注设备编号
                h = annotation_ops.add_text(
                    text=label,
                    x=ann_x,
                    y=ann_y,
                    height=text_height,
                    layer="ELEC-TEXT",
                )
                handles.append(h)

                # 标注参数（另起一行）
                if params:
                    h2 = annotation_ops.add_text(
                        text=params,
                        x=ann_x,
                        y=ann_y - text_height * 1.5,
                        height=text_height * 0.8,
                        layer="ELEC-TEXT",
                    )
                    handles.append(h2)

            elif annotation_type == "leader" and params:
                h = annotation_ops.add_leader(
                    start_x=ann_x,
                    start_y=ann_y,
                    end_x=ann_x + 10,
                    end_y=ann_y + 5,
                    text=f"{label}: {params}",
                    text_height=text_height,
                )
                handles.append(h)

            label_text = label + (f" / {params}" if params else "")

            # ── 更新 CanvasState ──────────────────────────────
            if self.canvas_state is not None:
                for h in handles:
                    self.canvas_state.record_annotation(
                        handle=h,
                        text=label_text,
                        x=ann_x, y=ann_y,
                        target_handle=handle,  # 标注关联到目标图元
                        height=text_height,
                        annotation_type=annotation_type,
                    )

            logger.info(f"AddAnnotation success: '{label_text}' at ({ann_x:.1f},{ann_y:.1f})")
            return (
                f"成功添加标注「{label_text}」于坐标 ({ann_x:.1f}, {ann_y:.1f})，"
                f"Handle(s): {', '.join(handles)}"
            )

        except ConnectionError:
            return "错误：AutoCAD 未连接"
        except Exception as e:
            logger.error(f"AddAnnotation failed: {e}")
            return f"添加标注失败: {e}"

    async def _arun(self, **kwargs) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))


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
