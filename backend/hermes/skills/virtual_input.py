"""
Virtual Input Skills — 鼠标点击 + 键盘输入
"""
from pydantic import BaseModel, Field

from hermes.skills import HermesSkill


class ClickInput(BaseModel):
    x: int = Field(..., description="X 坐标（相对目标窗口左上角）")
    y: int = Field(..., description="Y 坐标（相对目标窗口左上角）")
    target_window: str = Field("AutoCAD", description="窗口标题关键字")
    button: str = Field("left", description="left / right")
    double: bool = Field(False, description="是否双击")


class TypeTextInput(BaseModel):
    text: str = Field(..., description="要输入的文本")
    target_window: str = Field("AutoCAD", description="窗口标题关键字")


class ClickSkill(HermesSkill):
    name: str = "desktop_click"
    description: str = (
        "在目标窗口指定坐标执行鼠标点击。x/y 为相对窗口左上角的像素坐标。"
        "target_window 为窗口标题关键字（大小写不敏感，如 'AutoCAD'）。"
        "button 可选 'left' 或 'right'，double 设为 true 可双击。"
    )

    def execute(self, x: int, y: int, target_window: str = "AutoCAD",
                button: str = "left", double: bool = False) -> str:
        from desktop import virtual_input, whitelist

        if not whitelist.is_allowed(target_window):
            return f"[CLICK_DENIED] '{target_window}' 不在白名单中"

        hwnd = virtual_input.find_window_by_title(target_window)
        if not hwnd:
            return f"[CLICK_ERR] 未找到窗口 '{target_window}'"

        if double:
            ok = virtual_input.double_click(x, y, hwnd)
        else:
            ok = virtual_input.click(x, y, hwnd, button)

        return f"[CLICK_OK] {target_window} ({x},{y}) {button}{'_double' if double else ''}"


class TypeTextSkill(HermesSkill):
    name: str = "desktop_type"
    description: str = (
        "向目标窗口发送文本输入。使用 PostMessage 发送 WM_CHAR 消息，不干扰物理键盘。"
        "target_window 为窗口标题关键字。注意：AutoCAD 处于命令行模式时可直接输入命令。"
    )

    def execute(self, text: str, target_window: str = "AutoCAD") -> str:
        from desktop import virtual_input, whitelist

        if not whitelist.is_allowed(target_window):
            return f"[TYPE_DENIED] '{target_window}' 不在白名单中"

        hwnd = virtual_input.find_window_by_title(target_window)
        if not hwnd:
            return f"[TYPE_ERR] 未找到窗口 '{target_window}'"

        virtual_input.type_text(text, hwnd)
        short = (text[:50] + '...') if len(text) > 50 else text
        return f"[TYPE_OK] '{short}' -> {target_window}"
