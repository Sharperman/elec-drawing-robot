"""
AutoCAD 缩放控制模块
通过 COM API 实现精确视口控制，支持：
- zoom_extents: 全局视图
- zoom_center: 居中放大到指定点
- zoom_window: 窗口放大
- zoom_scale: 比例缩放
- get_view_extents: 获取当前视口范围
用于 /learn 模式的多尺度图纸学习
"""

from loguru import logger


class ZoomController:
    """
    AutoCAD 视口缩放控制器

    封装 AutoCAD COM API 的缩放操作，使 LLM 能够像人一样
    "先看全局，再放大看细节"。
    """

    def __init__(self, app=None, doc=None):
        self.app = app
        self.doc = doc

    def _get_app(self):
        """获取 AutoCAD Application 对象（属性名是 .acad 不是 .app）"""
        if self.app is None:
            from autocad.connection import autocad_connection
            conn = autocad_connection.connect()
            if not conn:
                raise RuntimeError("AutoCAD 未连接，无法执行缩放操作")
            self.app = autocad_connection.acad
            self.doc = autocad_connection.doc
        return self.app

    def _get_doc(self):
        """获取当前文档"""
        if self.doc is None:
            self._get_app()
        return self.doc

    # ── 公开方法 ─────────────────────────────────────────────

    def zoom_extents(self) -> bool:
        """
        缩放到全局视图（显示整张图纸）
        AutoCAD COM: Application.ZoomExtents()
        """
        try:
            app = self._get_app()
            app.ZoomExtents()
            logger.info("ZoomController: ZoomExtents 执行成功")
            return True
        except Exception as e:
            logger.error(f"ZoomExtents 失败: {e}")
            return False

    def zoom_center(
        self,
        center_x: float,
        center_y: float,
        height: float,
    ) -> bool:
        """
        居中放大到指定点
        AutoCAD COM: Application.ZoomCenter(CenterPoint, Magnification)

        Args:
            center_x: 中心点 X 坐标（图纸坐标系）
            center_y: 中心点 Y 坐标（图纸坐标系）
            height:   视口高度（图纸单位），越小放大倍数越大
        """
        try:
            app = self._get_app()
            import array
            center = array.array('d', [center_x, center_y, 0.0])
            app.ZoomCenter(center, height)
            logger.info(f"ZoomCenter: ({center_x}, {center_y}) height={height}")
            return True
        except Exception as e:
            logger.error(f"ZoomCenter 失败: {e}")
            return False

    def zoom_window(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
    ) -> bool:
        """
        窗口放大（框选区域放大）
        AutoCAD COM: Application.ZoomWindow(LowerLeft, UpperRight)
        参数必须是 VARIANT (VT_ARRAY | VT_R8) 类型

        Args:
            x1, y1: 窗口左下角坐标
            x2, y2: 窗口右上角坐标
        """
        try:
            app = self._get_app()
            import array
            p1 = array.array('d', [x1, y1, 0.0])
            p2 = array.array('d', [x2, y2, 0.0])
            app.ZoomWindow(p1, p2)
            logger.info(f"ZoomWindow: ({x1},{y1}) → ({x2},{y2})")
            return True
        except Exception as e:
            # Fallback: 用 SendCommand 发 ZOOM W 命令
            logger.warning(f"ZoomWindow COM 失败: {e}, trying SendCommand fallback")
            try:
                doc = self._get_doc()
                cmd = f"ZOOM W {x1},{y1} {x2},{y2} "
                doc.SendCommand(cmd)
                logger.info(f"ZoomWindow via SendCommand: ({x1},{y1}) → ({x2},{y2})")
                return True
            except Exception as e2:
                logger.error(f"ZoomWindow SendCommand 也失败: {e2}")
                return False

    def zoom_scale(self, scale: float) -> bool:
        """
        比例缩放（相对于当前视图）

        Args:
            scale: 缩放比例，>1 放大，<1 缩小
        """
        try:
            app = self._get_app()
            app.ZoomScaled(scale, 1)  # acZoomScaledRelative = 1
            logger.info(f"ZoomScale: {scale}x")
            return True
        except Exception as e:
            logger.error(f"ZoomScale 失败: {e}")
            return False

    def get_view_extents(self) -> tuple[float, float, float, float] | None:
        """
        获取当前视口范围
        返回 (min_x, min_y, max_x, max_y) 图纸坐标
        """
        try:
            doc = self._get_doc()
            # 获取当前视图中心和高宽
            view_center = doc.GetVariable("VIEWCTR")
            view_size = doc.GetVariable("VIEWSIZE")
            # 屏幕宽高比
            screen_size = doc.GetVariable("SCREENSIZE")
            if screen_size and len(screen_size) >= 2:
                aspect = screen_size[0] / float(screen_size[1]) if screen_size[1] != 0 else 1.33
            else:
                aspect = 1.33

            cx, cy = view_center[0], view_center[1]
            half_h = view_size / 2.0
            half_w = half_h * aspect

            return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
        except Exception as e:
            logger.error(f"get_view_extents 失败: {e}")
            return None

    def learn_zoom_sequence(self) -> list:
        """
        生成学习模式的默认缩放序列：
        全局视图 → 左上 → 右上 → 左下 → 右下 → 全局视图
        每个区域的坐标需要先 zoom_extents 后通过 get_view_extents 动态计算。
        但由于 get_view_extents 依赖当前视口，我们这里先用固定策略。
        """
        ex = self.get_view_extents() or (0, 0, 1000, 1000)
        mx, my, Mx, My = ex
        w, h = Mx - mx, My - my
        hw, hh = w / 2, h / 2

        return [
            {"step": 1, "type": "extents", "description": "全局视图"},
            {"step": 2, "type": "window", "description": "左上区域",
             "params": {"x1": mx, "y1": my + hh, "x2": mx + hw, "y2": My}},
            {"step": 3, "type": "window", "description": "右上区域",
             "params": {"x1": mx + hw, "y1": my + hh, "x2": Mx, "y2": My}},
            {"step": 4, "type": "window", "description": "左下区域",
             "params": {"x1": mx, "y1": my, "x2": mx + hw, "y2": my + hh}},
            {"step": 5, "type": "window", "description": "右下区域",
             "params": {"x1": mx + hw, "y1": my, "x2": Mx, "y2": my + hh}},
            {"step": 6, "type": "extents", "description": "回到全局视图"},
        ]


# 全局单例
_zoom_ctrl: ZoomController | None = None


def get_zoom_controller() -> ZoomController:
    """获取 ZoomController 全局实例"""
    global _zoom_ctrl
    if _zoom_ctrl is None:
        _zoom_ctrl = ZoomController()
    return _zoom_ctrl
