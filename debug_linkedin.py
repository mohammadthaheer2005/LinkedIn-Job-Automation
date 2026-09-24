import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        page = await browser.new_page()

        await page.goto(
            "https://www.linkedin.com/login",
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(5000)

        print("URL:", page.url)
        print("TITLE:", await page.title())

        count = await page.locator("input").count()

        print("Inputs found:", count)

        for i in range(count):
            inp = page.locator("input").nth(i)

            print(
                i,
                "id=",
                await inp.get_attribute("id"),
                "name=",
                await inp.get_attribute("name"),
                "type=",
                await inp.get_attribute("type"),
                "placeholder=",
                await inp.get_attribute("placeholder")
            )

        input("Press Enter to close")

        await browser.close()


asyncio.run(main())