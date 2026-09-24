import asyncio

from browser.browser_manager import get_browser


async def main():
    browser = await get_browser()

    page = await browser.new_page()

    await page.goto("https://www.google.com")

    print("Browser opened successfully!")

    input("Press Enter to close...")

    await browser.close()


asyncio.run(main())