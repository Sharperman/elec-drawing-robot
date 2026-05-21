"""
AutoCAD 截图工具
截取 AutoCAD 窗口截图并返回 base64 编码
"""
import io
from typing import Optional

from loguru import logger


class AutoCADSnapshot:
    """截取 AutoCAD 窗口截图"""

    def capture(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> str:
        """
        截取当前 AutoCAD 活动视口截图

        Args:
            width: 目标宽度（像素），None 则使用实际窗口大小
            height: 目标高度（像素）

        Returns:
            PNG 截图的 base64 编码字符串（含 data URL 前缀）

        Raises:
            RuntimeError: 截图失败
        """
        try:
            # 方法一：使用 AutoCAD COM 的 Export 方法
            return self._capture_via_com(width, height)
        except Exception as e:
            logger.warning(f"COM capture failed: {e}, falling back to screenshot method")
            # 方法二：屏幕截图方式（仅截取 AutoCAD 窗口区域）
            return self._capture_via_screenshot(width, height)

    def _capture_via_com(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> str:
        """通过 AutoCAD COM 接口导出截图（更精确）"""
        import win32com.client  # type: ignore
        import tempfile
        import os

        from autocad.connection import autocad_connection
        from utils.image_utils import file_to_base64, resize_image_if_needed
        from PIL import Image

        doc = autocad_connection.doc

        # 使用临时文件接收导出的图片
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # AutoCAD COM Export: 导出模型空间为 BMP
            doc.Export(tmp_path, "BMP", None)

            # 加载并转换为 PNG
            img = Image.open(tmp_path)
            if width and height:
                img = img.resize((width, height))
            elif width or height:
                img = resize_image_if_needed(img, max_size=max(width or 0, height or 0))

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            import base64
            b64 = base64.b64encode(buffer.read()).decode("utf-8")
            return f"data:image/png;base64,{b64}"

        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _capture_via_screenshot(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> str:
        """
        通过 Win32 API 截取 AutoCAD 窗口截图（备用方案）
        需要 AutoCAD 窗口在前台可见
        """
        import win32gui  # type: ignore
        import win32ui  # type: ignore
        import win32con  # type: ignore
        import win32api  # type: ignore
        import base64

        from autocad.connection import autocad_connection

        acad = autocad_connection.acad

        # 获取 AutoCAD 主窗口句柄
        hwnd = acad.HWND

        # 获取窗口区域
        rect = win32gui.GetWindowRect(hwnd)
        win_width = rect[2] - rect[0]
        win_height = rect[3] - rect[1]

        if win_width <= 0 or win_height <= 0:
            raise RuntimeError("AutoCAD 窗口尺寸无效")

        # 截图
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, win_width, win_height)
        save_dc.SelectObject(save_bitmap)
        save_dc.BitBlt(
            (0, 0), (win_width, win_height), mfc_dc, (0, 0), win32con.SRCCOPY
        )

        bmp_info = save_bitmap.GetInfo()
        bmp_data = save_bitmap.GetBitmapBits(True)

        from PIL import Image

        img = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_data,
            "raw",
            "BGRX",
            0,
            1,
        )

        if width and height:
            img = img.resize((width, height))

        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"


# 全局单例
autocad_snapshot = AutoCADSnapshot()
