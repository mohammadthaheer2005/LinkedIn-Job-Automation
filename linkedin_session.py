import os
from playwright.sync_api import sync_playwright

def login_to_linkedin():
    # Ensure sessions directory exists
    os.makedirs("sessions", exist_ok=True)
    session_path = os.path.join("sessions", "linkedin.json")

    print("🚀 Launching browser for manual LinkedIn login...")
    with sync_playwright() as p:
        # Launch Chromium in non-headless mode so the user can interact
        browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        page = context.new_page()

        # Open LinkedIn login page
        print("🔗 Navigating to LinkedIn login page...")
        page.goto("https://www.linkedin.com/login", timeout=90000)

        print("\n" + "="*60)
        print("👉 ACTION REQUIRED: Please log in manually in the browser window.")
        print("👉 Resolve any CAPTCHAs, email verification, or security checks.")
        print("="*60 + "\n")
        
        input("👉 Press [Enter] here in the console AFTER you have successfully logged in and see your home feed...")

        # Save context (cookies, local storage, session state)
        context.storage_state(path=session_path)
        print(f"\n✅ LinkedIn session successfully saved to '{session_path}'")
        
        browser.close()

if __name__ == "__main__":
    login_to_linkedin()
