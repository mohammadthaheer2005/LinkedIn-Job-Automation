def apply_easy_apply(page, job):
    job.click()
    page.wait_for_timeout(2000)

    try:
        apply_button = page.query_selector("button.jobs-apply-button")
        if apply_button:
            apply_button.click()
            page.wait_for_timeout(2000)
            print("✅ Applied via Easy Apply")
        else:
            print("❌ No Easy Apply button")
    except Exception as e:
        print("Error applying:", e)
