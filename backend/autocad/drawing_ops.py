"""
AutoCAD 图元绘图操作
insert_block, delete_entity, move_entity, get_all_entities
"""
from typing import Any, Optional

from loguru import logger

from autocad.connection import autocad_connection
from autocad.retry import retry_on_com_error


def _get_com_objects():
    """
    在当前线程获取 AutoCAD COM 对象（避免跨线程 STA 冲突）
    
    每次调用都通过 GetActiveObject 重新获取 dispatch，
    确保 COM 对象属于当前线程的 STA apartment。
    """
    import pythoncom
    pythoncom.CoInitialize()
    import win32com.client  # type: ignore
    from config import settings

    acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
    doc = acad.ActiveDocument
    model_space = doc.ModelSpace
    return acad, doc, model_space


class DrawingOps:
    """AutoCAD 绘图操作类"""

    @retry_on_com_error
    def insert_block(
        self,
        block_name: str,
        x: float,
        y: float,
        z: float = 0.0,
        x_scale: float = 1.0,
        y_scale: float = 1.0,
        rotation: float = 0.0,
        layer: str = "0",
        attributes: Optional[dict[str, str]] = None,
    ) -> str:
        """
        在 ModelSpace 中插入图块

        Args:
            block_name: AutoCAD 图块名称（需预先定义）
            x: 插入点 X 坐标（AutoCAD 图纸坐标，单位 mm）
            y: 插入点 Y 坐标
            z: 插入点 Z 坐标（默认 0，平面图）
            x_scale: X 方向缩放比例
            y_scale: Y 方向缩放比例
            rotation: 旋转角度（弧度）
            layer: 图块所在图层
            attributes: 图块属性字典 {属性标记: 属性值}

        Returns:
            插入图元的 Handle（AutoCAD 唯一标识符）

        Raises:
            ConnectionError: AutoCAD 未连接
            RuntimeError: 图块不存在或插入失败
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore

            from config import settings
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            model_space = doc.ModelSpace

            # 构建插入点
            insertion_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x, y, z],
            )

            # 插入图块参照
            block_ref = model_space.InsertBlock(
                insertion_point,
                block_name,
                x_scale,
                y_scale,
                1.0,   # z_scale
                rotation,
            )

            # 设置图层
            block_ref.Layer = layer

            # 设置属性（如果有）
            if attributes and block_ref.HasAttributes:
                attribs = block_ref.GetAttributes()
                for attrib in attribs:
                    tag = attrib.TagString.upper()
                    if tag in attributes:
                        attrib.TextString = str(attributes[tag])

            # 保存修改
            doc.Regen(0)  # 0 = acActiveViewport

            handle = block_ref.Handle
            logger.info(
                f"Block inserted: {block_name} at ({x:.2f}, {y:.2f}) "
                f"layer={layer} handle={handle}"
            )
            return handle

        except Exception as e:
            logger.error(f"insert_block failed: block={block_name} error={e}")
            raise RuntimeError(f"插入图块失败: {e}") from e

    @retry_on_com_error
    def delete_entity(self, handle: str) -> bool:
        """
        通过 Handle 删除图元

        Args:
            handle: AutoCAD 图元 Handle

        Returns:
            是否删除成功
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from config import settings
            import win32com.client  # type: ignore
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            entity = doc.HandleToObject(handle)
            entity.Delete()
            logger.info(f"Entity deleted: handle={handle}")
            return True
        except Exception as e:
            logger.error(f"delete_entity failed: handle={handle} error={e}")
            return False

    @retry_on_com_error
    def move_entity(
        self,
        handle: str,
        from_x: float,
        from_y: float,
        to_x: float,
        to_y: float,
        from_z: float = 0.0,
        to_z: float = 0.0,
    ) -> bool:
        """
        移动图元

        Args:
            handle: 图元 Handle
            from_x: 移动基点 X（通常为图元当前位置）
            from_y: 移动基点 Y
            to_x: 目标位置 X
            to_y: 目标位置 Y
            from_z: 移动基点 Z
            to_z: 目标位置 Z

        Returns:
            是否移动成功
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore
            from config import settings

            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            entity = doc.HandleToObject(handle)

            from_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [from_x, from_y, from_z],
            )
            to_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [to_x, to_y, to_z],
            )

            entity.Move(from_point, to_point)
            logger.info(
                f"Entity moved: handle={handle} "
                f"from=({from_x:.2f},{from_y:.2f}) "
                f"to=({to_x:.2f},{to_y:.2f})"
            )
            return True
        except Exception as e:
            logger.error(f"move_entity failed: handle={handle} error={e}")
            return False

    @retry_on_com_error
    def get_all_entities(self) -> list[dict[str, Any]]:
        """
        获取 ModelSpace 中所有图元信息

        Returns:
            图元信息字典列表，每个字典包含 handle/type/layer/position
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from config import settings
            import win32com.client  # type: ignore
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            model_space = acad.ActiveDocument.ModelSpace
            entities: list[dict] = []

            for i in range(model_space.Count):
                entity = model_space.Item(i)
                try:
                    info: dict[str, Any] = {
                        "handle": entity.Handle,
                        "entity_type": entity.EntityName,
                        "layer": entity.Layer,
                        "visible": entity.Visible,
                    }
                    # 尝试获取位置信息
                    try:
                        pt = entity.InsertionPoint
                        info["x"] = round(pt[0], 3)
                        info["y"] = round(pt[1], 3)
                    except Exception:
                        info["x"] = None
                        info["y"] = None

                    entities.append(info)
                except Exception as inner_e:
                    logger.debug(f"Skipping entity {i}: {inner_e}")
                    continue

            logger.debug(f"Found {len(entities)} entities in ModelSpace")
            return entities

        except Exception as e:
            logger.error(f"get_all_entities failed: {e}")
            return []

    @retry_on_com_error
    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        layer: str = "ELEC-WIRE",
        z1: float = 0.0,
        z2: float = 0.0,
    ) -> str:
        """
        绘制直线（用于连接图元）

        Args:
            x1, y1: 起点坐标
            x2, y2: 终点坐标
            layer: 图层名
            z1, z2: 起终点 Z 坐标

        Returns:
            线段图元 Handle
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore
            from config import settings

            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            model_space = doc.ModelSpace

            start_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x1, y1, z1],
            )
            end_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x2, y2, z2],
            )

            line = model_space.AddLine(start_point, end_point)
            line.Layer = layer
            doc.Regen(0)

            logger.info(
                f"Line drawn: ({x1:.2f},{y1:.2f}) -> ({x2:.2f},{y2:.2f}) layer={layer}"
            )
            return line.Handle

        except Exception as e:
            logger.error(f"draw_line failed: {e}")
            raise RuntimeError(f"绘制连线失败: {e}") from e

    @retry_on_com_error
    def create_simple_symbol(
        self,
        symbol_type: str,
        x: float,
        y: float,
        label: str = "",
        layer: str = "ELEC-SYMBOL",
        rotation: float = 0.0,
    ) -> str:
        """
        当图块不存在时，用基础图元（圆/矩形/线+文字）绘制简易电气符号

        Args:
            symbol_type: 符号类型 ID（如 CB_3P, TR_2W 等）
            x, y: 插入位置
            label: 设备编号（如 QF1）
            layer: 图层
            rotation: 旋转角度

        Returns:
            主图元的 Handle
        """
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        from config import settings

        acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
        doc = acad.ActiveDocument
        ms = doc.ModelSpace

        handle = ""
        w, h = 10.0, 10.0  # 默认符号尺寸

        try:
            if symbol_type in ("CB_3P", "FUSE"):
                # 断路器/熔断器：矩形 + 中间斜线
                pts = [(x-w/2, y-h/2), (x+w/2, y-h/2), (x+w/2, y+h/2), (x-w/2, y+h/2)]
                poly_pts = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                    [v for pt in pts for v in pt]
                )
                poly = ms.AddLightWeightPolyline(poly_pts)
                poly.Closed = True
                poly.Layer = layer
                # 斜线
                ms.AddLine(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-w/2, y+h/2, 0]),
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x+w/2, y-h/2, 0])
                ).Layer = layer
                handle = poly.Handle

            elif symbol_type in ("DS_3P", "KM"):
                # 隔离开关/接触器：矩形 + 顶部短线（断开表示）
                pts = [(x-w/2, y-h/2), (x+w/2, y-h/2), (x+w/2, y+h/2), (x-w/2, y+h/2)]
                poly_pts = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                    [v for pt in pts for v in pt]
                )
                poly = ms.AddLightWeightPolyline(poly_pts)
                poly.Closed = True
                poly.Layer = layer
                # 断开标记（顶部开口线）
                ms.AddLine(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-w/2, y+h/2, 0]),
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-w/4, y+h/2+3, 0])
                ).Layer = layer
                handle = poly.Handle

            elif symbol_type in ("TR_2W",):
                # 双绕组变压器：两个圆
                c1 = ms.AddCircle(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y+4, 0]),
                    6
                )
                c1.Layer = layer
                c2 = ms.AddCircle(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y-4, 0]),
                    6
                )
                c2.Layer = layer
                handle = c1.Handle

            elif symbol_type in ("BUS_3P", "WIRE", "CABLE"):
                # 母线/导线：水平粗线
                line = ms.AddLine(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-w, y, 0]),
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x+w, y, 0])
                )
                line.Layer = layer
                line.Lineweight = 30  # 粗线
                handle = line.Handle

            elif symbol_type in ("GND",):
                # 接地符号：三条水平线
                y_offsets = [y, y-2.5, y-5]
                widths = [8, 6, 4]
                for yo, wi in zip(y_offsets, widths):
                    line = ms.AddLine(
                        win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-wi/2, yo, 0]),
                        win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x+wi/2, yo, 0])
                    )
                    line.Layer = layer
                # 竖线
                ms.AddLine(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y+5, 0]),
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y, 0])
                ).Layer = layer
                handle = f"GND-{x:.0f}-{y:.0f}"

            elif symbol_type in ("CT", "VT"):
                # 互感器：圆形 + 内部标记
                c = ms.AddCircle(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y, 0]),
                    6
                )
                c.Layer = layer
                handle = c.Handle

            elif symbol_type in ("LA",):
                # 避雷器：矩形 + 箭头
                pts = [(x-w/2, y-h/2), (x+w/2, y-h/2), (x+w/2, y+h/2), (x-w/2, y+h/2)]
                poly_pts = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                    [v for pt in pts for v in pt]
                )
                poly = ms.AddLightWeightPolyline(poly_pts)
                poly.Closed = True
                poly.Layer = layer
                # 箭头
                ms.AddLine(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y+h/2, 0]),
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y+h/2+4, 0])
                ).Layer = layer
                handle = poly.Handle

            elif symbol_type in ("MOTOR", "GEN"):
                # 电动机/发电机：圆 + M/G
                c = ms.AddCircle(
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x, y, 0]),
                    7
                )
                c.Layer = layer
                letter = "M" if symbol_type == "MOTOR" else "G"
                txt = ms.AddText(letter,
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-2.5, y-2, 0]),
                    4
                )
                txt.Layer = layer
                handle = c.Handle

            elif symbol_type in ("BAT",):
                # 蓄电池：两个矩形（长短表示正负极）
                for i, (ox, ow, oh) in enumerate([(x-2, 2, 8), (x+2, 1.5, 6)]):
                    pts = [(ox-ow/2, y-oh/2), (ox+ow/2, y-oh/2), (ox+ow/2, y+oh/2), (ox-ow/2, y+oh/2)]
                    poly_pts = win32com.client.VARIANT(
                        win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                        [v for pt in pts for v in pt]
                    )
                    poly = ms.AddLightWeightPolyline(poly_pts)
                    poly.Closed = True
                    poly.Layer = layer
                    if i == 0:
                        handle = poly.Handle

            elif symbol_type in ("SWGR",):
                # 开关柜：大矩形 + 内部虚线
                w, h = 15, 20
                pts = [(x-w/2, y-h/2), (x+w/2, y-h/2), (x+w/2, y+h/2), (x-w/2, y+h/2)]
                poly_pts = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                    [v for pt in pts for v in pt]
                )
                poly = ms.AddLightWeightPolyline(poly_pts)
                poly.Closed = True
                poly.Layer = layer
                handle = poly.Handle

            else:
                # 默认：矩形 + 文字标签
                pts = [(x-w/2, y-h/2), (x+w/2, y-h/2), (x+w/2, y+h/2), (x-w/2, y+h/2)]
                poly_pts = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                    [v for pt in pts for v in pt]
                )
                poly = ms.AddLightWeightPolyline(poly_pts)
                poly.Closed = True
                poly.Layer = layer
                handle = poly.Handle

            # 添加设备编号
            if label:
                txt = ms.AddText(label,
                    win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [x-4, y-h/2-4, 0]),
                    3.5
                )
                txt.Layer = "ELEC-TEXT"

            doc.Regen(0)
            logger.info(f"Simple symbol created: {symbol_type} at ({x},{y}) label={label}")
            return handle or f"{symbol_type}-{x:.0f}-{y:.0f}"

        except Exception as e:
            logger.error(f"create_simple_symbol failed: {e}")
            raise RuntimeError(f"创建简易符号失败: {e}") from e


# 全局单例
drawing_ops = DrawingOps()
