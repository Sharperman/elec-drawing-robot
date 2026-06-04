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
from typing import Optional, Tuple
import pythoncom
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

    def _get_utility(self):
        """获取 AutoCAD Utility 对象（用于 Zoom 相关方法）"""
        if self.doc is None:
            if self.app is None:
                from autocad.connection import autocad_connection
                conn = autocad_connection.connect()
                if not conn or not conn.get("connected"):
                    raise RuntimeError("AutoCAD 未连接，无法执行缩放操作")
                self.app = autocad_connection.app
                self.doc = autocad_connection.doc
            else:
                from autocad.connection import autocad_connection
                self.doc = autocad_connection.doc

        return self.doc.Utility

    # ── 公开方法 ─────────────────────────────────────────────

    def zoom_extents(self) -> bool:
        """
        缩放到全局视图（显示整张图纸）

        Returns:
            成功返回 True
        """
        try:
            util = self._get_utility()
            util.ZoomExtents()
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

        Args:
            center_x: 中心点 X 坐标（图纸坐标系）
            center_y: 中心点 Y 坐标（图纸坐标系）
            height:   视口高度（图纸单位），越小放大倍数越大

        Returns:
            成功返回 True
        """
        try:
            util = self._get_utility()
            # ZoomCenter 接受三个参数：中心点（Variant Array），视口高度
            from comtypes.automation import VARIANT
            import array

            center_array = array.array('d', [center_x, center_y, 0.0])
            # COM 调用 ZoomCenter
            util.ZoomCenter(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                center_array,
                height,
            )
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

        Args:
            x1, y1: 窗口左下角坐标
            x2, y2: 窗口右上角坐标

        Returns:
            成功返回 True
        """
        try:
            util = self._get_utility()
            import array

            p1 = array.array('d', [x1, y1, 0.0])
            p2 = array.array('d', [x2, y2, 0.0])
            util.ZoomWindow(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, p1,
                pythoncom.VT_ARRAY | pythoncom.VT_R8, p2,
            )
            logger.info(f"ZoomWindow: ({x1},{y1}) -> ({x2},{y2})")
            return True
        except Exception as e:
            logger.error(f"ZoomWindow 失败: {e}")
            return False

    def zoom_scale(self, scale_factor: float) -> bool:
        """
        按比例缩放（基于当前视口）

        Args:
            scale_factor: 缩放因子，>1 放大，<1 缩小
                          2.0 = 放大 2 倍，0.5 = 缩小到 50%

        Returns:
            成功返回 True
        """
        try:
            util = self._get_utility()
            util.ZoomScaled(scale_factor)
            logger.info(f"ZoomScaled: factor={scale_factor}")
            return True
        except Exception as e:
            logger.error(f"ZoomScaled 失败: {e}")
            return False

    def zoom_point(self, x: float, y: float, factor: float = 0.5) -> bool:
        """
        以指定点为中心，按比例缩放（便捷方法）

        Args:
            x, y:     中心坐标
            factor:    缩放因子（相对于当前视口高度）

        Returns:
            成功返回 True
        """
        try:
            # 先获取当前视口范围
            ext = self.get_view_extents()
            if ext is None:
                return False
            current_height = ext["max_y"] - ext["min_y"]
            new_height = current_height * factor
            return self.zoom_center(x, y, new_height)
        except Exception as e:
            logger.error(f"ZoomPoint 失败: {e}")
            return False

    def get_view_extents(self) -> Optional[dict]:
        """
        获取当前视口范围（图纸坐标系）

        Returns:
            {
                "min_x": float, "min_y": float,
                "max_x": float, "max_y": float,
                "center_x": float, "center_y": float,
                "height": float, "width": float,
            }
            获取失败返回 None
        """
        try:
            if self.doc is None:
                from autocad.connection import autocad_connection
                self.doc = autocad_connection.doc
                if self.doc is None:
                    return None

            # ActiveViewport 可能不存在，回退用 GetVariable
            try:
                vp = self.doc.ActiveViewport
                center = vp.Center
                height = vp.Height
                width = vp.Width
                min_x = center[0] - width / 2
                min_y = center[1] - height / 2
                return {
                    "min_x": float(min_x),
                    "min_y": float(min_y),
                    "max_x": float(min_x + width),
                    "max_y": float(min_y + height),
                    "center_x": float(center[0]),
                    "center_y": float(center[1]),
                    "height": float(height),
                    "width": float(width),
                }
            except Exception:
                # 回退：用 GetVariable 获取系统变量
                vt = self.doc.GetVariable("VIEWSIZE")
                vc = self.doc.GetVariable("VIEWCTR")
                if vc and vt:
                    cx, cy = float(vc[0]), float(vc[1])
                    h = float(vt)
                    w = h * 2.0  # 近似宽度
                    return {
                        "min_x": cx - w / 2, "min_y": cy - h / 2,
                        "max_x": cx + w / 2, "max_y": cy + h / 2,
                        "center_x": cx, "center_y": cy,
                        "height": h, "width": w,
                    }
        except Exception as e:
            logger.warning(f"GetViewExtents 失败: {e}")
            return None

    def get_drawing_extents(self) -> Optional[dict]:
        """
        获取图纸实际范围（所有实体的边界框）

        Returns:
            同 get_view_extents 格式；若无可识别实体返回 None
        """
        try:
            if self.doc is None:
                from autocad.connection import autocad_connection
                self.doc = autocad_connection.doc
                if self.doc is None:
                    return None

            blocks = self.doc.Blocks
            # 遍历模型空间所有实体，计算包围盒
            model_space = None
            for b in blocks:
                if b.Name == "*Model_Space":
                    model_space = b
                    break
            if model_space is None:
                # 回退：用 ActiveLayout
                layout = self.doc.ActiveLayout
                ents = layout.Block
            else:
                ents = model_space

            min_x = min_y = float("inf")
            max_x = max_y = float("-inf")
            count = 0
            for i in range(ents.Count):
                try:
                    e = ents.Item(i)
                    bb = e.GetBoundingBox()
                    if bb and len(bb) == 2:
                        (x1, y1, _), (x2, y2, _) = bb
                        min_x = min(min_x, x1)
                        min_y = min(min_y, y1)
                        max_x = max(max_x, x2)
                        max_y = max(max_y, y2)
                        count += 1
                except Exception:
                    continue

            if count == 0:
                return None

            # 加 5% 边距
            pad_x = (max_x - min_x) * 0.05 or 10.0
            pad_y = (max_y - min_y) * 0.05 or 10.0
            return {
                "min_x": min_x - pad_x, "min_y": min_y - pad_y,
                "max_x": max_x + pad_x, "max_y": max_y + pad_y,
                "center_x": (min_x + max_x) / 2,
                "center_y": (min_y + max_y) / 2,
                "height": (max_y - min_y) + 2 * pad_y,
                "width": (max_x - min_x) + 2 * pad_x,
            }
        except Exception as e:
            logger.warning(f"GetDrawingExtents 失败: {e}")
            return None

    def pan_to(self, x: float, y: float) -> bool:
        """
        平移视口中心点（不缩放）

        Args:
            x, y: 目标中心点坐标

        Returns:
            成功返回 True
        """
        try:
            util = self._get_utility()
            import array
            center_array = array.array('d', [x, y, 0.0])
            # AutoCAD COM 没有直接 Pan，用 ZoomCenter + 恢复原高度实现
            ext = self.get_view_extents()
            if ext is None:
                return False
            return self.zoom_center(x, y, ext["height"])
        except Exception as e:
            logger.error(f"PanTo 失败: {e}")
            return False

    def learn_zoom_sequence(
        self,
        drawing_extents: Optional[dict] = None,
    ) -> list[dict]:
        """
        生成"学习用"缩放序列（供 LearnAgent 调用）

        策略：
        1. ZoomExtents（全局）
        2. 按网格划分区域，逐个放大到每个区域
        3. 识别关键设备位置，再放大到设备周围

        Args:
            drawing_extents: 图纸范围（None 则自动获取）

        Returns:
            缩放步骤列表，每项:
            {"step": int, "type": "extents"|"window"|"center",
             "params": {...}, "description": str}
        """
        if drawing_extents is None:
            drawing_extents = self.get_drawing_extents()
        if drawing_extents is None:
            # 实在获取不到，至少返回全局视图
            return [{
                "step": 1, "type": "extents",
                "params": {}, "description": "全局视图（无法获取图纸范围）",
            }]

        seq = []
        cx, cy = drawing_extents["center_x"], drawing_extents["center_y"]
        h  = drawing_extents["height"]
        w  = drawing_extents["width"]

        # Step 1: 全局
        seq.append({
            "step": 1, "type": "extents",
            "params": {},
            "description": "全局视图 — 查看图纸整体框架",
        })

        # Step 2~5: 四分区域放大
        regions = [
            (cx - w/4, cy + h/4, w/2, h/2, "左上区域"),
            (cx + w/4, cy + h/4, w/2, h/2, "右上区域"),
            (cx - w/4, cy - h/4, w/2, h/2, "左下区域"),
            (cx + w/4, cy - h/4, w/2, h/2, "右下区域"),
        ]
        for i, (rx, ry, rw, rh, desc) in enumerate(regions, start=2):
            seq.append({
                "step": i, "type": "window",
                "params": {
                    "x1": rx - rw/2, "y1": ry - rh/2,
                    "x2": rx + rw/2, "y2": ry + rh/2,
                },
                "description": f"放大 — {desc}",
            })

        # Step 6: 回到全局
        seq.append({
            "step": len(seq) + 1, "type": "extents",
            "params": {},
            "description": "回到全局视图 — 确认整体布局",
        })

        return seq

    def execute_sequence(self, sequence: list[dict]) -> list[dict]:
        """
        执行缩放序列，每步后等待并返回结果

        Args:
            sequence: learn_zoom_sequence 返回的序列

        Returns:
            每步的执行结果列表:
            [{"step": 1, "success": bool, "screenshot": "base64..."}]
        """
        results = []
        for item in sequence:
            t = item["type"]
            params = item["params"]
            ok = False
            try:
                if t == "extents":
                    ok = self.zoom_extents()
                elif t == "window":
                    ok = self.zoom_window(
                        params["x1"], params["y1"],
                        params["x2"], params["y2"],
                    )
                elif t == "center":
                    ok = self.zoom_center(
                        params["center_x"], params["center_y"],
                        params.get("height", 100.0),
                    )
                else:
                    logger.warning(f"未知缩放类型: {t}")
            except Exception as e:
                logger.error(f"执行缩放步骤 {item['step']} 失败: {e}")

            results.append({
                "step": item["step"],
                "type": t,
                "description": item["description"],
                "success": ok,
            })
        return results


# ── 全局单例 ─────────────────────────────────────────────────
_zoom_controller: Optional[ZoomController] = None


def get_zoom_controller() -> ZoomController:
    """获取 ZoomController 单例"""
    global _zoom_controller
    if _zoom_controller is None:
        _zoom_controller = ZoomController()
    return _zoom_controller
