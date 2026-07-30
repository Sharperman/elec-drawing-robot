"""
Screenshot Skill — 桌面截图
"""
from pydantic import BaseModel, Field
from typing import Optional, Type

from hermes.skills import HermesSkill


class ScreenshotInput(BaseModel):
    region: Optional[str] = Field(None, description="目标窗口标题关键字（如'AutoCAD'、'Chrome'），不填则全屏")


class ScreenshotSkill(HermesSkill):
    name: str = "desktop_screenshot"
    description: str = (
        "截取屏幕或指定窗口的截图。传入 region 参数可按窗口标题截图（如 'AutoCAD'），"
        "不传则全屏截图。返回 base64 编码的图片数据，可供后续视觉分析。"
    )

    def execute(self, region: Optional[str] = None) -> str:
        from desktop import screen_capture

        try:
            if region:
                img = screen_capture.capture_window(region)
                if not img:
                    return f"[SCREENSHOT_ERR] 未找到窗口 '{region}'"
            else:
                img = screen_capture.capture_fullscreen()
                if not img:
                    return "[SCREENSHOT_ERR] 截图失败"

            # 存到状态中供后续使用
            from hermes import hermes_state
            hermes_state._last_screenshot = img

            return f"[SCREENSHOT_OK] {len(img)} bytes (base64 png) — 截图已就绪"
        except Exception as e:
            return f"[SCREENSHOT_ERR] {e}"
