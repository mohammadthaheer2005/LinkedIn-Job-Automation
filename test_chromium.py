import asyncio
from playwright.async_api import async_playwright


async def main():
    print("Starting Playwright...")

    async with async_playwright() as p:
        print("Launching browser...")

        browser = await p.chromium.launch(
            headless=False
        )

        print("Browser opened!")

        page = await browser.new_page()

        await page.goto("https://www.google.com")

        print("Page loaded:", await page.title())

        input("Press Enter to close...")

        await browser.close()


asyncio.run(main())