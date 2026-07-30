"""
Desktop Adapter 层 — 通用桌面操作能力
提供截图、虚拟输入、浏览器控制、白名单管理。
"""
from desktop.screen_capture import ScreenCapture
from desktop.virtual_input import VirtualInput
from desktop.browser_agent import BrowserAgent
from desktop.whitelist import Whitelist

screen_capture = ScreenCapture()
virtual_input = VirtualInput()
browser_agent = BrowserAgent()
whitelist = Whitelist()

__all__ = ["ScreenCapture", "VirtualInput", "BrowserAgent", "Whitelist",
           "screen_capture", "virtual_input", "browser_agent", "whitelist"]
