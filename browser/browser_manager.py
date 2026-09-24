from playwright.async_api import async_playwright
import os

class BrowserManager:
    def __init__(self, headless=False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )

        if os.path.exists("sessions/linkedin.json"):
            self.context = await self.browser.new_context(
                storage_state="sessions/linkedin.json"
            )
        else:
            self.context = await self.browser.new_context()

        page = await self.context.new_page()

        return page

    async def save_session(self):
        await self.context.storage_state(
            path="sessions/linkedin.json"
        )

    async def close(self):
        await self.browser.close()
        await self.playwright.stop()