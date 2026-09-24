from playwright.sync_api import sync_playwright
from check_linkedin import search_jobs
from find_button import apply_easy_apply
import os

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)

        # If session file exists, reuse it; otherwise create fresh context
        if os.path.exists("linkedin_state.json"):
            context = browser.new_context(storage_state="linkedin_state.json")
        else:
            context = browser.new_context()

        page = context.new_page()

        jobs = search_jobs(page, keyword="Python Developer", location="India")
        for job in jobs[:5]:
            apply_easy_apply(page, job)

if __name__ == "__main__":
    main()
