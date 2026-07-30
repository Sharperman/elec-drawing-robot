"""
白名单管理器
管理哪些应用可以被 Computer Use Agent 自动控制。
"""
from typing import List, Optional


class Whitelist:
    """白名单：自动授权的应用列表"""

    # 默认白名单（按窗口标题关键词匹配）
    DEFAULT_WHITELIST = [
        "AutoCAD",
        "Google Chrome",
        "Microsoft Edge",
        "Firefox",
        "文件资源管理器",
        "File Explorer",
        "Windows Explorer",
        "记事本",
        "Notepad",
    ]

    def __init__(self):
        self._custom: List[str] = []

    def is_allowed(self, app_title: str) -> bool:
        """
        检查应用是否在白名单中。
        app_title: 窗口标题（部分匹配）
        """
        all_list = self.DEFAULT_WHITELIST + self._custom
        for name in all_list:
            if name.lower() in app_title.lower():
                return True
        return False

    def find_matching(self, app_title: str) -> Optional[str]:
        """找到匹配的白名单条目"""
        all_list = self.DEFAULT_WHITELIST + self._custom
        for name in all_list:
            if name.lower() in app_title.lower():
                return name
        return None

    def add_custom(self, app_name: str):
        """添加自定义白名单"""
        if app_name not in self._custom:
            self._custom.append(app_name)

    def remove_custom(self, app_name: str):
        """移除自定义白名单"""
        if app_name in self._custom:
            self._custom.remove(app_name)

    def get_list(self) -> List[str]:
        """获取完整白名单"""
        return self.DEFAULT_WHITELIST + self._custom
