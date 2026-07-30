"""
虚拟输入控制器
通过 PostMessage/SendMessage 向目标窗口发消息，不移动物理鼠标。
"""
import time
from typing import Optional

from loguru import logger

try:
    import win32gui
    import win32con
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Windows 消息常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_MOUSEWHEEL = 0x020A
WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
MK_LBUTTON = 0x0001

# 虚拟键码
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_ALT = 0x12
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

KEY_MAP = {
    "enter": VK_RETURN, "return": VK_RETURN,
    "esc": VK_ESCAPE, "escape": VK_ESCAPE,
    "tab": VK_TAB,
    "backspace": VK_BACK, "delete": VK_DELETE,
    "ctrl": VK_CONTROL, "shift": VK_SHIFT, "alt": VK_ALT,
    "left": VK_LEFT, "up": VK_UP, "right": VK_RIGHT, "down": VK_DOWN,
}


class VirtualInput:
    """虚拟输入：不移动物理鼠标，直接向目标窗口发送消息"""

    def _ensure_win32(self):
        if not HAS_WIN32:
            raise RuntimeError("win32gui/win32api 不可用")

    def find_window_by_title(self, title_substring: str) -> Optional[int]:
        """按标题模糊查找窗口句柄"""
        self._ensure_win32()
        result = []
        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title_substring.lower() in title.lower():
                    result.append(hwnd)
        try:
            win32gui.EnumWindows(_enum, None)
        except Exception:
            pass
        return result[0] if result else None

    def click(self, x: int, y: int, hwnd: Optional[int] = None, button: str = "left") -> bool:
        """
        向指定窗口发送点击消息
        x, y: 相对于窗口客户区的坐标
        hwnd: 目标窗口句柄，None 则发送到前台窗口
        """
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            lparam = (y << 16) | (x & 0xFFFF)

            if button == "right":
                win32api.PostMessage(target, WM_RBUTTONDOWN, 0, lparam)
                time.sleep(0.03)
                win32api.PostMessage(target, WM_RBUTTONUP, 0, lparam)
            else:
                win32api.PostMessage(target, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
                time.sleep(0.03)
                win32api.PostMessage(target, WM_LBUTTONUP, 0, lparam)

            logger.debug(f"虚拟点击: ({x},{y}) on hwnd={target}")
            return True
        except Exception as e:
            logger.warning(f"虚拟点击失败: {e}")
            return False

    def double_click(self, x: int, y: int, hwnd: Optional[int] = None) -> bool:
        """双击"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            lparam = (y << 16) | (x & 0xFFFF)
            win32api.PostMessage(target, WM_LBUTTONDBLCLK, MK_LBUTTON, lparam)
            return True
        except Exception as e:
            logger.warning(f"双击失败: {e}")
            return False

    def move_mouse(self, x: int, y: int, hwnd: Optional[int] = None) -> bool:
        """移动鼠标（不显示物理光标移动，仅更新窗口内的鼠标位置）"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            lparam = (y << 16) | (x & 0xFFFF)
            win32api.PostMessage(target, WM_MOUSEMOVE, 0, lparam)
            return True
        except Exception as e:
            logger.warning(f"移动鼠标失败: {e}")
            return False

    def type_text(self, text: str, hwnd: Optional[int] = None) -> bool:
        """向窗口发送文本（WM_CHAR）"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            for ch in text:
                win32api.PostMessage(target, WM_CHAR, ord(ch), 0)
                time.sleep(0.01)
            return True
        except Exception as e:
            logger.warning(f"输入文本失败: {e}")
            return False

    def press_key(self, key: str, hwnd: Optional[int] = None) -> bool:
        """按下并释放一个键"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            vk = KEY_MAP.get(key.lower())
            if vk is None:
                vk = ord(key.upper()) if len(key) == 1 else None
            if vk is None:
                return False

            win32api.PostMessage(target, WM_KEYDOWN, vk, 0)
            time.sleep(0.02)
            win32api.PostMessage(target, WM_KEYUP, vk, 0)
            return True
        except Exception as e:
            logger.warning(f"按键失败 '{key}': {e}")
            return False

    def scroll(self, clicks: int, x: int = 0, y: int = 0, hwnd: Optional[int] = None) -> bool:
        """滚轮滚动。正数向上，负数向下"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            lparam = (y << 16) | (x & 0xFFFF)
            wparam = clicks * 120 << 16  # WHEEL_DELTA = 120
            win32api.PostMessage(target, WM_MOUSEWHEEL, wparam, lparam)
            return True
        except Exception as e:
            logger.warning(f"滚动失败: {e}")
            return False

    def hotkey(self, keys: list, hwnd: Optional[int] = None) -> bool:
        """发送组合键，如 ['ctrl', 'c']"""
        self._ensure_win32()
        try:
            target = hwnd or win32gui.GetForegroundWindow()
            vks = [KEY_MAP.get(k.lower(), ord(k.upper()) if len(k) == 1 else 0) for k in keys]
            for vk in vks:
                if not vk:
                    return False
            # 按下修饰键
            for vk in vks[:-1]:
                win32api.PostMessage(target, WM_KEYDOWN, vk, 0)
                time.sleep(0.02)
            # 按下并释放主键
            win32api.PostMessage(target, WM_KEYDOWN, vks[-1], 0)
            time.sleep(0.02)
            win32api.PostMessage(target, WM_KEYUP, vks[-1], 0)
            # 释放修饰键
            for vk in reversed(vks[:-1]):
                time.sleep(0.02)
                win32api.PostMessage(target, WM_KEYUP, vk, 0)
            return True
        except Exception as e:
            logger.warning(f"组合键失败: {e}")
            return False

    def get_mouse_position(self):
        """获取当前物理鼠标位置 (用于获取参考坐标，不用于虚拟操作)"""
        try:
            import pyautogui
            return pyautogui.position()
        except Exception:
            return (0, 0)

    def get_screen_size(self) -> tuple:
        """获取屏幕分辨率"""
        try:
            import pyautogui
            return pyautogui.size()
        except Exception:
            return (1920, 1080)
