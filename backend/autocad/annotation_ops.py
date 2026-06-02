"""
AutoCAD 文字标注和尺寸标注操作
"""
from loguru import logger

from autocad.connection import autocad_connection
from autocad.retry import retry_on_com_error


class AnnotationOps:
    """AutoCAD 标注操作类"""

    @retry_on_com_error
    def add_text(
        self,
        text: str,
        x: float,
        y: float,
        height: float = 3.5,
        layer: str = "ELEC-TEXT",
        rotation: float = 0.0,
        z: float = 0.0,
    ) -> str:
        """
        添加单行文字标注

        Args:
            text: 文字内容
            x: 插入点 X 坐标
            y: 插入点 Y 坐标
            height: 文字高度（mm）
            layer: 所在图层
            rotation: 旋转角度（弧度），0=水平
            z: Z 坐标（平面图为 0）

        Returns:
            文字图元 Handle
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore
            from config import settings

            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            model_space = doc.ModelSpace

            insertion_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x, y, z],
            )

            # 使用 AddText（单行文字），高度作为构造参数直接传入
            # 避免 AddMText + CharHeight 在 COM STA 异常时出现 "can not be set" 错误
            text_obj = model_space.AddText(text, insertion_point, height)
            text_obj.Layer = layer
            if rotation != 0.0:
                text_obj.Rotation = rotation

            doc.Regen(0)

            handle = text_obj.Handle
            logger.info(f"Text added: '{text}' at ({x:.2f},{y:.2f}) h={height}")
            return handle

        except Exception as e:
            logger.error(f"add_text failed: '{text}' error={e}")
            raise RuntimeError(f"添加文字标注失败: {e}") from e

    @retry_on_com_error
    def add_dimension(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        dim_x: float,
        dim_y: float,
        rotation: float = 0.0,
        layer: str = "ELEC-DIM",
    ) -> str:
        """
        添加线性尺寸标注

        Args:
            x1, y1: 第一个标注点坐标
            x2, y2: 第二个标注点坐标
            dim_x, dim_y: 尺寸线放置位置
            rotation: 标注旋转角度（弧度），0=水平标注
            layer: 标注图层

        Returns:
            标注图元 Handle
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore
            from config import settings

            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            model_space = doc.ModelSpace

            ext_point1 = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x1, y1, 0.0],
            )
            ext_point2 = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [x2, y2, 0.0],
            )
            dim_line_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [dim_x, dim_y, 0.0],
            )

            dim = model_space.AddDimRotated(
                ext_point1,
                ext_point2,
                dim_line_point,
                rotation,
            )
            dim.Layer = layer
            doc.Regen(0)

            handle = dim.Handle
            logger.info(
                f"Dimension added: ({x1:.1f},{y1:.1f})->({x2:.1f},{y2:.1f}) "
                f"at ({dim_x:.1f},{dim_y:.1f})"
            )
            return handle

        except Exception as e:
            logger.error(f"add_dimension failed: {e}")
            raise RuntimeError(f"添加尺寸标注失败: {e}") from e

    @retry_on_com_error
    def add_leader(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        text: str,
        text_height: float = 3.5,
        layer: str = "ELEC-TEXT",
    ) -> str:
        """
        添加带引线的文字注释

        Args:
            start_x, start_y: 引线起点（箭头端，指向图元）
            end_x, end_y: 引线终点（文字端）
            text: 注释文字
            text_height: 文字高度
            layer: 图层

        Returns:
            引线图元 Handle
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore
            from config import settings

            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            model_space = doc.ModelSpace

            # 引线折点数组（起点 + 终点）
            points = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [start_x, start_y, 0.0, end_x, end_y, 0.0],
            )

            leader = model_space.AddLeader(points, None, 1)  # 1 = acLineNoArrow... 使用 0 = acLineWithArrow
            leader.Layer = layer

            # 添加注释文字
            text_point = win32com.client.VARIANT(
                win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                [end_x + 1, end_y, 0.0],
            )
            text_obj = model_space.AddText(text, text_point, text_height)
            text_obj.Layer = layer

            doc.Regen(0)

            handle = leader.Handle
            logger.info(f"Leader added: '{text}' from ({start_x:.1f},{start_y:.1f})")
            return handle

        except Exception as e:
            logger.error(f"add_leader failed: {e}")
            raise RuntimeError(f"添加引线标注失败: {e}") from e


# 全局单例
annotation_ops = AnnotationOps()
