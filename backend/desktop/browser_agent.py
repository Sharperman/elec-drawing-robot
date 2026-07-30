"""
Playwright 浏览器 Agent
独立浏览器实例，不干扰用户正在使用的浏览器。
"""
import asyncio
import base64
from typing import Optional

from loguru import logger


class BrowserAgent:
    """Playwright 浏览器控制器（独立实例，不与用户浏览器冲突）"""

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None
        self._loop = None

    async def _ensure_browser(self):
        """确保浏览器已启动（懒启动）"""
        if self._page is not None:
            return

        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()

            # 优先使用系统 Chrome
            try:
                self._browser = await self._pw.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                logger.info("Browser: using system Chrome")
            except Exception:
                # fallback: Playwright 自带 Chromium
                self._browser = await self._pw.chromium.launch(
                    headless=False,
                    args=["--no-sandbox"],
                )
                logger.info("Browser: using bundled Chromium")

            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            )
            self._page = await self._context.new_page()
            logger.info("Browser: ready")
        except Exception as e:
            logger.error(f"Browser启动失败: {e}")
            raise

    async def navigate(self, url: str) -> str:
        """打开网页，返回页面标题"""
        await self._ensure_browser()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await self._page.title()
        return title

    async def screenshot(self) -> str:
        """截取当前页面，返回 base64 PNG"""
        await self._ensure_browser()
        data = await self._page.screenshot(type="png", full_page=False)
        return base64.b64encode(data).decode("utf-8")

    async def get_text(self) -> str:
        """获取页面可见文本"""
        await self._ensure_browser()
        text = await self._page.inner_text("body")
        return text[:10000]  # 截断

    async def search(self, query: str, engine: str = "google") -> str:
        """
        搜索并返回结果摘要。
        返回搜索结果的第一页文本内容。
        """
        await self._ensure_browser()

        if engine == "google":
            url = f"https://www.google.com/search?q={_urlencode(query)}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={_urlencode(query)}"
        else:
            url = f"https://www.baidu.com/s?wd={_urlencode(query)}"

        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 等待搜索结果加载
        await asyncio.sleep(1.5)
        text = await self._page.inner_text("body")
        return text[:6000]

    async def click(self, selector: str):
        """点击页面元素"""
        await self._ensure_browser()
        await self._page.click(selector, timeout=10000)

    async def type_text(self, selector: str, text: str):
        """在输入框中输入文本"""
        await self._ensure_browser()
        await self._page.fill(selector, text)

    async def execute_js(self, script: str) -> str:
        """执行 JavaScript"""
        await self._ensure_browser()
        result = await self._page.evaluate(script)
        return str(result)

    async def close(self):
        """关闭浏览器"""
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if hasattr(self, '_pw'):
                await self._pw.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None


def _urlencode(s: str) -> str:
    """简单的 URL 编码"""
    import urllib.parse
    return urllib.parse.quote(s)


# 同步包装器，供 LangChain Tool 使用
class SyncBrowserAgent:
    """同步版本的浏览器 Agent（内部使用 asyncio）"""

    def __init__(self):
        self._agent = BrowserAgent()

    def navigate(self, url: str) -> str:
        return asyncio.run(self._agent.navigate(url))

    def screenshot(self) -> str:
        return asyncio.run(self._agent.screenshot())

    def search(self, query: str, engine: str = "google") -> str:
        return asyncio.run(self._agent.search(query, engine))

    def get_text(self) -> str:
        return asyncio.run(self._agent.get_text())

    def click(self, selector: str):
        return asyncio.run(self._agent.click(selector))

    def type_text(self, selector: str, text: str):
        return asyncio.run(self._agent.type_text(selector, text))

    def close(self):
        asyncio.run(self._agent.close())
