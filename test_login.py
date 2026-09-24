import asyncio
from playwright.async_api import async_playwright

from linkedin.login import login


async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        page = await browser.new_page()

        await page.goto(
            "https://www.linkedin.com/login",
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("LinkedIn page opened")
        print("URL:", page.url)

        await login(page)

        print("Login function finished")

        input("Press Enter to close browser...")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())