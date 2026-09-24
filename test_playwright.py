import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto("https://www.google.com")

        print("Playwright is working!")

        input("Press Enter to close browser...")

        await browser.close()

asyncio.run(main())