"""
通用屏幕截图模块
支持全屏、指定窗口、指定区域截图，窗口枚举。
"""
import base64
import io
from typing import Optional, List, Tuple

import mss
import mss.tools
from PIL import Image
from loguru import logger

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class ScreenCapture:
    """通用屏幕截图器 (mss + win32gui)"""

    def __init__(self):
        self._sct = mss.mss()

    def capture_fullscreen(self) -> str:
        """
        截取主显示器全屏，返回 base64 PNG（不含 data URI 前缀）
        对多显示器/BitBlt 失败有 fallback
        """
        # 尝试 mss monitors（跳过 monitor[0]="所有显示器合并"）
        for idx in range(1, min(len(self._sct.monitors), 5)):
            try:
                monitor = self._sct.monitors[idx]
                img = self._sct.grab(monitor)
                png = mss.tools.to_png(img.rgb, img.size)
                return base64.b64encode(png).decode("utf-8")
            except Exception:
                continue

        # 回退：PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=False)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e2:
            logger.error(f"全屏截图失败 (all methods): {e2}")
            return ""

    def capture_window(self, title_substring: str) -> str:
        """
        按窗口标题模糊匹配截图，返回 base64 PNG
        """
        hwnd = self._find_window(title_substring)
        if not hwnd:
            return ""

        try:
            rect = win32gui.GetWindowRect(hwnd)
            # 确保窗口可见
            if rect[0] < -10000 or rect[2] - rect[0] < 50:
                logger.warning(f"窗口 '{title_substring}' 可能最小化或离屏")
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                import time
                time.sleep(0.2)
                rect = win32gui.GetWindowRect(hwnd)

            monitor = {"top": rect[1], "left": rect[0], "width": rect[2] - rect[0], "height": rect[3] - rect[1]}
            img = self._sct.grab(monitor)
            png = mss.tools.to_png(img.rgb, img.size)
            return base64.b64encode(png).decode("utf-8")
        except Exception as e:
            logger.error(f"窗口截图失败 '{title_substring}': {e}")
            return ""

    def capture_region(self, x: int, y: int, w: int, h: int) -> str:
        """截图指定区域，返回 base64 PNG"""
        try:
            monitor = {"top": y, "left": x, "width": w, "height": h}
            img = self._sct.grab(monitor)
            png = mss.tools.to_png(img.rgb, img.size)
            return base64.b64encode(png).decode("utf-8")
        except Exception as e:
            logger.error(f"区域截图失败: {e}")
            return ""

    def capture_fullscreen_numpy(self):
        """截取全屏为 numpy 数组 (供视频录制使用)"""
        try:
            monitor = self._sct.monitors[1]
            img = self._sct.grab(monitor)
            import numpy as np
            return np.array(img)
        except Exception as e:
            logger.error(f"Numpy 全屏截图失败: {e}")
            return None

    def get_window_list(self) -> List[dict]:
        """枚举所有可见窗口"""
        if not HAS_WIN32:
            return []

        windows = []

        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title.strip()) > 0:
                    rect = win32gui.GetWindowRect(hwnd)
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "rect": rect,
                        "width": rect[2] - rect[0],
                        "height": rect[3] - rect[1],
                    })

        win32gui.EnumWindows(_enum, None)
        return windows

    def get_main_display_info(self) -> dict:
        """获取主显示器信息"""
        monitor = self._sct.monitors[1]
        return {
            "width": monitor["width"],
            "height": monitor["height"],
            "left": monitor["left"],
            "top": monitor["top"],
        }

    def _find_window(self, title_substring: str) -> Optional[int]:
        """按标题模糊查找窗口句柄"""
        if not HAS_WIN32:
            return None

        result = []

        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title_substring.lower() in title.lower():
                    result.append(hwnd)

        win32gui.EnumWindows(_enum, None)
        return result[0] if result else None
