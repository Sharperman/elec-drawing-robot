"""
Browser Skill — Playwright 浏览器自动化
"""
from pydantic import BaseModel, Field
from typing import Optional

from hermes.skills import HermesSkill


class BrowserInput(BaseModel):
    action: str = Field(..., description="操作: navigate / search / screenshot / get_text")
    url_or_query: Optional[str] = Field(None, description="URL 或 搜索关键词")
    engine: str = Field("baidu", description="搜索引擎: google / bing / baidu")


class BrowserSkill(HermesSkill):
    name: str = "desktop_browse"
    description: str = (
        "操控浏览器（Playwright 自动化），用于查资料、搜索信息。\n"
        "action 可选: navigate(打开URL)、search(搜索)、screenshot(截网页)、get_text(提取文字)。\n"
        "搜索默认使用百度。使用独立的浏览器实例，不干扰用户当前浏览器。"
    )

    def execute(self, action: str, url_or_query: Optional[str] = None,
                engine: str = "baidu") -> str:
        from desktop.browser_agent import SyncBrowserAgent

        browser = SyncBrowserAgent()
        try:
            if action == "navigate" and url_or_query:
                title = browser.navigate(url_or_query)
                return f"[BROWSE_OK] 已导航到: {title}"

            elif action == "search" and url_or_query:
                text = browser.search(url_or_query, engine)
                return f"[BROWSE_OK] 搜索结果 (前3000字):\n{text[:3000]}"

            elif action == "screenshot":
                img = browser.screenshot()
                return f"[BROWSE_OK] 网页截图 {len(img)} bytes"

            elif action == "get_text":
                text = browser.get_text()
                return f"[BROWSE_OK] 页面文本 (前5000字):\n{text[:5000]}"

            else:
                return f"[BROWSE_ERR] 未知操作: {action}"

        except Exception as e:
            return f"[BROWSE_ERR] {e}"
        finally:
            try:
                browser.close()
            except Exception:
                pass
