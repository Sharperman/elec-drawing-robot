"""
Hermes 模块 — DrawAgent 的桌面操作工具扩展

Hermes 不是一个独立 Agent，而是一组可插拔的 Skills。
每个 Skill 实现标准接口，统一注册为 LangChain Tool，
在 CU 开关开启时动态注入 DrawAgent 的工具列表。
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class HermesState:
    """Hermes 全局状态（线程安全）"""
    enabled: bool = False
    running: bool = False
    current_action: str = ""
    action_count: int = 0
    interrupt_requested: bool = False
    action_log: list[str] = field(default_factory=list)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_status(self, msg: str):
        with self._lock:
            self.current_action = msg
            self.action_log.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(self.action_log) > 200:
                self.action_log = self.action_log[-100:]

    def interrupt(self):
        with self._lock:
            self.interrupt_requested = True
        self.set_status("用户请求中断")

    def start_run(self):
        with self._lock:
            self.running = True
            self.action_count = 0
            self.interrupt_requested = False
            self.action_log.clear()

    def stop_run(self):
        with self._lock:
            self.running = False

    def inc_action(self):
        with self._lock:
            self.action_count += 1

    def status_dict(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": self.running,
                "current_action": self.current_action,
                "action_count": self.action_count,
                "action_log": self.action_log[-20:],
            }


# ─── 全局单例 ─────────────────────────────────────────────────

hermes_state = HermesState()

# Skill 注册表 — 模块级 dict，所有 Skill 实例在此注册
_registry: list = []  # list of HermesSkill instances


def register_skill(skill):
    """注册一个 Hermes Skill"""
    global _registry
    if skill.__class__.__name__ not in [s.__class__.__name__ for s in _registry]:
        _registry.append(skill)


def get_hermes_tools():
    """
    获取所有已注册 Hermes Skill 的 LangChain Tool 列表。
    在 CU 开启时由 draw_agent 调用，注入工具列表。
    """
    if not _registry:
        _ensure_default_skills()
    return [s.as_tool() for s in _registry]


def _ensure_default_skills():
    """懒加载默认 Skill"""
    from hermes.skills.screenshot import ScreenshotSkill
    from hermes.skills.virtual_input import ClickSkill, TypeTextSkill
    from hermes.skills.browser import BrowserSkill
    global _registry
    names = {s.__class__.__name__ for s in _registry}
    for cls in [ScreenshotSkill, ClickSkill, TypeTextSkill, BrowserSkill]:
        if cls.__name__ not in names:
            try:
                _registry.append(cls())
            except Exception as e:
                import logging
                logging.getLogger("hermes").error(f"Failed to instantiate {cls.__name__}: {e}")
