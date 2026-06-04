"""
ModifyElement Tool
修改已有图元的属性、位置或图层
"""
from typing import Any, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from loguru import logger


class ModifyElementInput(BaseModel):
    """ModifyElement 工具输入参数"""
    handle: Optional[str] = Field(
        None,
        description="目标图元 Handle（修改具体图元时必填）"
    )
    target_type: Optional[str] = Field(
        None,
        description="目标类型：entity=图元，layer=图层"
    )
    target_name: Optional[str] = Field(
        None,
        description="目标名称（target_type=layer 时填图层名）"
    )
    properties: dict[str, Any] = Field(
        ...,
        description=(
            "要修改的属性字典。\n"
            "图元属性：layer（图层）、x/y（位置）、rotation（旋转）、scale（缩放）\n"
            "图层属性：color_index（颜色）、linetype（线型）、lineweight（线宽）"
        )
    )


class ModifyElementTool(BaseTool):
    """
    LangChain Tool：修改已有图元的属性/位置/图层

    支持修改：
    - 图元的图层、位置、旋转角度、缩放
    - 图层的颜色、线型、线宽
    """

    # CanvasState 注入（由 DrawAgent 在构建工具时设置）
    canvas_state: object = Field(default=None, exclude=True)

    name: str = "modify_element"
    description: str = (
        "修改 AutoCAD 图纸中已有图元的属性或位置。"
        "通过 handle 指定要修改的图元，或通过 target_type='layer' 修改图层属性。"
        "properties 字典中指定要修改的属性和新值。"
    )
    args_schema: Type[BaseModel] = ModifyElementInput

    def _run(
        self,
        properties: dict[str, Any],
        handle: Optional[str] = None,
        target_type: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> str:
        """执行修改操作"""
        import pythoncom
        pythoncom.CoInitialize()

        try:
            import win32com.client
            from config import settings
            from autocad.layer_manager import layer_manager
            from autocad.drawing_ops import drawing_ops

            # 在当前线程获取 COM dispatch
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument

            changed_items: list[str] = []

            if target_type == "layer" and target_name:
                # 修改图层属性
                if "color_index" in properties:
                    layer_manager.set_layer_color(target_name, int(properties["color_index"]))
                    changed_items.append(f"颜色={properties['color_index']}")

                if "linetype" in properties:
                    layer_manager.set_layer_linetype(target_name, str(properties["linetype"]))
                    changed_items.append(f"线型={properties['linetype']}")

                if "lineweight" in properties:
                    from autocad.layer_manager import LINEWEIGHT_MAP
                    lw = float(properties["lineweight"])
                    try:
                        layer = doc.Layers.Item(target_name)
                        layer.Lineweight = LINEWEIGHT_MAP.get(lw, -3)
                    except Exception:
                        pass
                    changed_items.append(f"线宽={lw}mm")

                result = f"图层 {target_name} 已修改: {', '.join(changed_items)}"
                logger.info(result)
                return result

            elif handle:
                # 修改图元属性
                entity = doc.HandleToObject(handle)

                if "layer" in properties:
                    entity.Layer = str(properties["layer"])
                    changed_items.append(f"图层={properties['layer']}")

                if "x" in properties or "y" in properties:
                    try:
                        # 用 GetBoundingBox 计算中心（兼容 Polyline 等无 InsertionPoint 的实体）
                        current_pt = _get_entity_center(entity)
                        current_x, current_y = current_pt[0], current_pt[1]
                        new_x = float(properties.get("x", current_x))
                        new_y = float(properties.get("y", current_y))
                        drawing_ops.move_entity(
                            handle=handle,
                            from_x=current_x,
                            from_y=current_y,
                            to_x=new_x,
                            to_y=new_y,
                        )
                        changed_items.append(f"位置=({new_x:.1f},{new_y:.1f})")
                    except Exception as e:
                        logger.warning(f"Failed to move entity: {e}")

                if "rotation" in properties:
                    try:
                        entity.Rotation = float(properties["rotation"])
                        changed_items.append(f"旋转={properties['rotation']}rad")
                    except Exception as e:
                        logger.warning(f"Failed to set rotation: {e}")

                if "scale" in properties:
                    try:
                        s = float(properties["scale"])
                        entity.XScaleFactor = s
                        entity.YScaleFactor = s
                        changed_items.append(f"缩放={s}")
                    except Exception as e:
                        logger.warning(f"Failed to set scale: {e}")

                result = f"图元 {handle} 已修改: {', '.join(changed_items) if changed_items else '无变更'}"

                # ── 同步 CanvasState ──────────────────────────
                if self.canvas_state is not None and changed_items:
                    cs_updates = {}
                    if "x" in properties or "y" in properties:
                        cs_updates["x"] = float(properties.get("x", 0))
                        cs_updates["y"] = float(properties.get("y", 0))
                    if "layer" in properties:
                        cs_updates["layer"] = str(properties["layer"])
                    if "rotation" in properties:
                        cs_updates["rotation"] = float(properties["rotation"])
                    if "scale" in properties:
                        cs_updates["scale"] = float(properties["scale"])
                    if cs_updates:
                        self.canvas_state.record_update_device(handle, **cs_updates)

                logger.info(result)
                return result

            else:
                return "错误：必须提供 handle（修改图元）或 target_type+target_name（修改图层）"

        except ConnectionError:
            return "错误：AutoCAD 未连接"
        except Exception as e:
            logger.error(f"ModifyElement failed: {e}")
            return f"修改图元失败: {e}"

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
