def search_jobs(page, keyword="Software Engineer", location="India"):
    page.goto("https://www.linkedin.com/jobs", timeout=60000)
    page.fill("input[aria-label='Search jobs']", keyword)
    page.fill("input[aria-label='Search location']", location)
    page.keyboard.press("Enter")
    page.wait_for_load_state("domcontentloaded", timeout=60000)

    jobs = page.query_selector_all(".jobs-search-results__list-item")
    print(f"Found {len(jobs)} jobs")
    return jobs
