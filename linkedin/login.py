from playwright.async_api import Page
from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD


async def login(page: Page):

    print("Checking login fields...")

    await page.wait_for_timeout(3000)

    print(
        "Email fields:",
        await page.locator("input[type='email']").count()
    )

    print(
        "Visible email fields:",
        await page.locator("input[type='email']:visible").count()
    )

    print(
        "Password fields:",
        await page.locator("input[type='password']").count()
    )

    print(
        "Visible password fields:",
        await page.locator("input[type='password']:visible").count()
    )


    email = page.locator(
        "input[type='email']:visible"
    ).first

    password = page.locator(
        "input[type='password']:visible"
    ).first


    print("Clicking email box...")
    await email.click()

    await email.fill(
        LINKEDIN_EMAIL
    )

    print("Email entered")


    print("Clicking password box...")
    await password.click()

    await password.fill(
        LINKEDIN_PASSWORD
    )

    print("Password entered")


    await page.screenshot(
        path="before_login_click.png"
    )


    print("Clicking Sign in button...")

    await page.get_by_role(
        "button",
        name="Sign in"
    ).first.click()


    print("Sign in clicked")


    await page.wait_for_timeout(10000)


    print(
        "After login URL:",
        page.url
    )


    await page.screenshot(
        path="after_login.png"
    )


    input(
        "Check browser then press Enter..."
    )