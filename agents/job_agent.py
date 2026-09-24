import os
import json
import asyncio
import logging
from pydantic import Field
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from config import OLLAMA_MODEL, JOB_KEYWORD, JOB_LOCATION, MAX_APPLICATIONS, HEADLESS
from dotenv import load_dotenv

load_dotenv()

# Silence the noisy storage_state + user_data_dir warning from browser-use
logging.getLogger("browser_use.browser.utils").setLevel(logging.ERROR)
logging.getLogger("utils").setLevel(logging.ERROR)
logging.getLogger("browser_use.utils").setLevel(logging.ERROR)
logging.getLogger("browser_use.browser.profile").setLevel(logging.ERROR)
logging.getLogger("browser_use.browser.session").setLevel(logging.ERROR)


def create_llm():
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    USE_GROQ = os.getenv("USE_GROQ", "false").lower() == "true"
    USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"
    USE_ANTHROPIC = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
    
    # MULTI-KEY ROTATION LOGIC:
    # Get all Gemini keys from comma-separated env var
    google_keys_env = os.getenv("GOOGLE_API_KEYS", "")
    google_keys_list = []
    if google_keys_env:
        google_keys_list = [k.strip() for k in google_keys_env.split(",") if k.strip()]
    google_key = os.getenv("GOOGLE_API_KEY", "")
    
    if USE_GROQ:
        from browser_use.llm.openai.chat import ChatOpenAI as BrowserUseChatOpenAI
        api_key = os.getenv("GROQ_API_KEY")
        model = os.getenv("MODEL", "llama-3.3-70b-versatile")
        print(f"🚀 Using Groq high-speed model via OpenAI wrapper: {model}")
        return BrowserUseChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.0
        )
    elif USE_ANTHROPIC:
        # Require langchain-anthropic to be installed
        from langchain_anthropic import ChatAnthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("MODEL", "claude-3-5-sonnet-latest")
        print(f"🌟 Using Anthropic model: {model}")
        return ChatAnthropic(
            model_name=model,
            anthropic_api_key=api_key,
            temperature=0.0
        )
    elif USE_OPENROUTER:
        from browser_use.llm.openai.chat import ChatOpenAI as BrowserUseChatOpenAI
        api_key = os.getenv("OPENROUTER_API_KEY")
        model = os.getenv("MODEL", "google/gemma-4-31b-it:free")
        print(f"🌐 Using OpenRouter cloud model: {model}")
        return BrowserUseChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.0,
            remove_min_items_from_schema=True,
            default_headers={
                "HTTP-Referer": "https://github.com/linkedin-job-automation",
                "X-Title": "LinkedIn Job Automation",
            }
        )
    elif len(google_keys_list) > 1:
        # ROTATING MULTI-KEY MODE: Use all Gemini keys in round-robin to bypass rate limits
        from browser_use.llm.google.chat import ChatGoogle
        import itertools
        
        model = os.getenv("MODEL", "gemini-2.5-flash")
        print(f"⚡ Using Google AI Studio with {len(google_keys_list)} rotating keys!")
        
        # Create a round-robin key cycler
        key_cycler = itertools.cycle(google_keys_list)
        
        class RotatingChatGoogle(ChatGoogle):
            """Wrapper that rotates the API key on every single API call."""
            
            def __init__(self, keys_cycle, **kwargs):
                super().__init__(**kwargs)
                self._keys_cycle = keys_cycle
                self._call_count = 0
            
            def _rotate_key(self):
                new_key = next(self._keys_cycle)
                self._call_count += 1
                # Update the internal client's API key
                self.api_key = new_key
                # Force a fresh client on next call
                self._client = None
                print(f"   🔄 Key rotation #{self._call_count}: using ...{new_key[-4:]}")
            
            async def ainvoke(self, *args, **kwargs):
                self._rotate_key()
                return await super().ainvoke(*args, **kwargs)
        
        return RotatingChatGoogle(
            keys_cycle=key_cycler,
            model=model,
            api_key=google_keys_list[0],
            temperature=0.0
        )
    elif (google_key and google_key.strip()) or (len(google_keys_list) == 1):
        from browser_use.llm.google.chat import ChatGoogle
        single_key = google_keys_list[0] if google_keys_list else google_key
        model = os.getenv("MODEL", "gemini-2.5-flash")
        print(f"⚡ Using Google AI Studio model: {model}")
        return ChatGoogle(
            model=model,
            api_key=single_key,
            temperature=0.0
        )

    else:
        from langchain_ollama import ChatOllama
        print(f"🤖 Using local Ollama model: {OLLAMA_MODEL}")
        llm = ChatOllama(model=OLLAMA_MODEL, temperature=0.0, num_predict=4096)
        llm.__dict__["provider"] = "ollama"
        llm.__dict__["model_name"] = OLLAMA_MODEL
        return llm


def load_profile():
    profile_path = "profile_data.json"
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def sanitize_session(session_path: str) -> dict:
    """Strip problematic cookie fields browser-use can't deserialize."""
    with open(session_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ALLOWED_COOKIE_FIELDS = {
        "name", "value", "domain", "path", "expires",
        "httpOnly", "secure", "sameSite"
    }
    clean_cookies = []
    for cookie in data.get("cookies", []):
        clean = {k: v for k, v in cookie.items() if k in ALLOWED_COOKIE_FIELDS}
        # Only keep LinkedIn and essential cookies to reduce noise
        if any(d in clean.get("domain", "") for d in ["linkedin.com", "licdn.com"]):
            clean_cookies.append(clean)

    data["cookies"] = clean_cookies
    return data


async def run_direct_linkedin_playwright_fallback(keyword, location, resume_text, experience, extra_details, status_dict=None):
    """
    Direct Playwright Engine for LinkedIn.
    Specifically selects the Easy Apply filter option on LinkedIn,
    finds Easy Apply job cards, fills form questions, and submits applications!
    """
    from playwright.async_api import async_playwright
    import urllib.parse

    print("🚀 Direct Playwright LinkedIn Engine Activated ($0 Cost, 0 API Keys)...")
    if status_dict:
        status_dict["message"] = "🚀 Running Direct Playwright Engine..."

    # Clean URL parameters
    clean_kw = urllib.parse.quote(str(keyword).strip())
    clean_loc = urllib.parse.quote(str(location).strip())
    
    session_path = os.path.join("sessions", "linkedin_clean.json")
    if not os.path.exists(session_path):
        session_path = os.path.join("sessions", "linkedin.json")

    profile = load_profile()
    user_phone = profile.get("phone") or os.getenv("APPLICANT_PHONE", "")
    user_email = profile.get("email") or os.getenv("LINKEDIN_EMAIL", "")
    user_name = profile.get("full_name") or os.getenv("APPLICANT_NAME", "Applicant")
    user_exp = str(experience if experience else profile.get("years_of_experience", 0))

    # ALWAYS include Easy Apply filter (f_AL) + Experience Level filter (f_E=1,2 = Internship + Entry Level)
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={clean_kw}&location={clean_loc}&f_LF=f_AL&f_E=1,2"

    applied_companies = []
    applied_count = 0

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            # Load saved LinkedIn session cookies so it opens ALREADY LOGGED IN
            context_kwargs = {"viewport": {"width": 1280, "height": 800}}
            if os.path.exists(session_path):
                context_kwargs["storage_state"] = session_path
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            print(f"🌐 Navigating to LinkedIn Job Search: {search_url}")
            if status_dict:
                status_dict["message"] = f"Opening LinkedIn jobs for '{keyword}'..."

            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            # Accurate login check: only trigger auto-login if URL is actually at login/checkpoint or login inputs visible
            is_logged_out = (
                "/login" in page.url
                or "/checkpoint" in page.url
                or "/uas/login" in page.url
                or await page.locator("input#username:visible, input#session_key:visible").count() > 0
            )
            if is_logged_out:
                print("⚠️ LinkedIn session expired or logged out. Performing automatic login...")
                login_email = os.getenv("LINKEDIN_EMAIL", "").strip()
                login_password = os.getenv("LINKEDIN_PASSWORD", "").strip()
                if login_email and login_password:
                    await page.goto("https://www.linkedin.com/login", timeout=30000)
                    email_inp = page.locator("input[type='email']:visible, input#username:visible").last
                    if await email_inp.count() > 0:
                        await email_inp.fill(login_email)
                        pwd_inp = page.locator("input[type='password']:visible, input#password:visible").last
                        if await pwd_inp.count() > 0:
                            await pwd_inp.fill(login_password)
                            await pwd_inp.press("Enter")
                            await page.wait_for_timeout(6000)
                            # Save fresh session states
                            await context.storage_state(path=os.path.join("sessions", "linkedin.json"))
                            await context.storage_state(path=os.path.join("sessions", "linkedin_clean.json"))
                            print("✅ Fresh login successful & saved to sessions!")
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

            # Check & Click "Easy Apply" Filter Option ONLY if not already in URL
            try:
                if "f_LF=f_AL" not in page.url:
                    easy_filter_btn = page.locator("button#searchFilter_applyWithLinkedin, button[aria-label*='Easy Apply filter']").first
                    if await easy_filter_btn.count() > 0 and await easy_filter_btn.is_visible():
                        aria_checked = str(await easy_filter_btn.get_attribute("aria-checked") or "").lower()
                        if aria_checked != "true":
                            print("🎯 Clicking 'Easy Apply' filter pill on LinkedIn top filter bar...")
                            await easy_filter_btn.click()
                            await page.wait_for_timeout(2000)
            except Exception as fe:
                print(f"Filter pill check info: {fe}")

            # Robust selectors for LinkedIn job cards (finds member and public card variants)
            card_selectors = "li[data-occludable-job-id], div.job-card-container, div[data-job-id], li.jobs-search-results__list-item, div.base-card, div.base-search-card, ul.jobs-search__results-list > li"
            job_cards = page.locator(card_selectors)
            card_count = await job_cards.count()
            print(f"📋 Found {card_count} job cards on page.")

            if card_count == 0:
                # Scroll the job list container or window to trigger lazy loading
                try:
                    container = await page.query_selector("div.jobs-search-results-list, div.scaffold-layout__list, ul.jobs-search-results__list")
                    if container:
                        await container.evaluate('(el) => { el.scrollTop = el.scrollHeight; }')
                    else:
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
                job_cards = page.locator(card_selectors)
                card_count = await job_cards.count()
                print(f"📋 Retry check found {card_count} job cards.")

            for i in range(min(card_count, MAX_APPLICATIONS)):
                if status_dict and status_dict.get("stop_requested"):
                    print("🛑 Bot stop requested by user.")
                    break

                try:
                    card = job_cards.nth(i)
                    try:
                        await card.scroll_into_view_if_needed(timeout=3000)
                    except Exception:
                        pass  # Continue even if scroll fails
                    click_target = card.locator("a.job-card-container__link, a[data-control-name='job_card_click'], strong").first
                    if await click_target.count() > 0:
                        await click_target.click(timeout=5000)
                    else:
                        await card.click(timeout=5000)
                    await page.wait_for_timeout(500)

                    # Extract Job Title & Company
                    title_elem = page.locator("h2.job-details-jobs-unified-top-card__job-title, h1.t-24, a.job-card-container__link span").first
                    company_elem = page.locator("div.job-details-jobs-unified-top-card__company-name, a.ember-view, span.job-card-container__primary-description").first
                    
                    title_str = (await title_elem.text_content() if await title_elem.count() > 0 else f"Job #{i+1}").strip()
                    company_str = (await company_elem.text_content() if await company_elem.count() > 0 else "Company").strip()
                    # Fast filter: skip obvious senior/management titles only
                    if any(bad in title_str.lower() for bad in ["senior", "sr.", "sr ", "lead", "manager", "director", "architect", "principal", "head"]):
                        print(f"⏩ Skipping Senior role: {title_str}")
                        continue

                    # Look for Easy Apply button specifically inside job details panel
                    easy_apply_btn = page.locator("button.jobs-apply-button:has-text('Easy Apply'), button[aria-label*='Easy Apply']").first
                    if await easy_apply_btn.count() == 0 or not await easy_apply_btn.is_visible():
                        print(f"⏩ Skipping non-Easy Apply job: {title_str}")
                        continue

                    # FAST APPLY: URL already filtered f_LF=f_AL & f_E=1,2.
                    print(f"🎯 Applying to Easy Apply job ({i+1}/{card_count}): {title_str} at {company_str}")
                    if status_dict:
                        status_dict["message"] = f"Applying: {title_str} ({company_str})..."

                    await easy_apply_btn.click(timeout=2000)
                    await page.wait_for_timeout(300)

                    # Multi-page form handling - ultra fast, fills ONLY empty fields
                    form_success = False
                    for page_step in range(8):
                        await page.wait_for_timeout(100)

                        # ── FAST CHECK: IS SUBMIT BUTTON READY? (e.g. Review step) ──
                        submit_btn = page.locator("div.jobs-easy-apply-modal button[aria-label*='Submit application'], div.jobs-easy-apply-modal button:has-text('Submit application')").first
                        if await submit_btn.count() > 0 and await submit_btn.is_visible():
                            await submit_btn.click()
                            await page.wait_for_timeout(500)
                            applied_count += 1
                            applied_companies.append(f"{title_str} @ {company_str}")
                            form_success = True
                            if status_dict:
                                status_dict["applications"] = applied_count
                                status_dict["applied_companies"] = applied_companies
                                status_dict["message"] = f"Applied to {applied_count} jobs: {title_str}"
                            print(f"✅ Successfully applied to: {title_str} ({applied_count}/{MAX_APPLICATIONS})")

                            # Instant close success dialog (Escape + Done fallback)
                            try:
                                await page.keyboard.press("Escape")
                                await page.wait_for_timeout(150)
                                done_btn = page.locator("div[role='dialog'] button:has-text('Done'), div[role='dialog'] button[aria-label*='Dismiss']").first
                                if await done_btn.is_visible():
                                    await done_btn.click(timeout=600)
                            except Exception:
                                pass
                            break

                        # ── 1. FILL TEXT / NUMBER / CITY / PHONE / TEXTAREA INPUTS (ONLY IF EMPTY) ──
                        text_inputs = page.locator("div.jobs-easy-apply-modal input:not([type='checkbox']):not([type='radio']):not([type='hidden']), div.jobs-easy-apply-modal textarea")
                        for idx in range(await text_inputs.count()):
                            inp = text_inputs.nth(idx)
                            try:
                                if not await inp.is_visible():
                                    continue
                                # Check if already filled by user or LinkedIn profile
                                current_val = (await inp.input_value()).strip()
                                if current_val:
                                    continue  # Already filled - skip immediately!

                                inp_id = await inp.get_attribute("id") or ""
                                inp_type = (await inp.get_attribute("type") or "text").lower()
                                aria = (await inp.get_attribute("aria-label") or "").lower()
                                placeholder = (await inp.get_attribute("placeholder") or "").lower()
                                label_text = ""
                                if inp_id and not (aria or placeholder):
                                    label = page.locator(f"label[for='{inp_id}']")
                                    if await label.count() > 0:
                                        label_text = (await label.text_content()).strip().lower()

                                hint = f"{label_text} {aria} {placeholder} {inp_id.lower()}"

                                if any(w in hint for w in ["phone", "mobile", "contact"]):
                                    await inp.fill(user_phone)
                                elif any(w in hint for w in ["email", "e-mail"]):
                                    await inp.fill(user_email)
                                elif any(w in hint for w in ["city", "location", "current city", "place", "state", "reside", "address"]):
                                    loc_val = profile.get("current_location", location or "Chennai")
                                    await inp.fill(loc_val)
                                    await page.wait_for_timeout(150)
                                    suggest = page.locator("div.basic-typeahead__selectable-list li, div[role='listbox'] div[role='option'], div.typeahead-results li").first
                                    if await suggest.count() > 0 and await suggest.is_visible():
                                        await suggest.click()
                                    else:
                                        await inp.press("ArrowDown")
                                        await inp.press("Enter")
                                elif any(w in hint for w in ["experience", "years", "yrs", "how many"]):
                                    await inp.fill(user_exp if user_exp else "1")
                                elif any(w in hint for w in ["salary", "ctc", "stipend", "compensation", "expectation"]):
                                    await inp.fill("15000")
                                elif any(w in hint for w in ["name"]):
                                    await inp.fill(user_name)
                                elif any(w in hint for w in ["notice", "period", "joining"]):
                                    await inp.fill("0")
                                elif inp_type == "number":
                                    await inp.fill("1")
                                else:
                                    await inp.fill("Yes")
                            except Exception:
                                pass

                        # ── 2. FILL SELECT DROPDOWNS (ONLY IF NOT SELECTED) ──
                        selects = page.locator("div.jobs-easy-apply-modal select")
                        for s_idx in range(await selects.count()):
                            sel = selects.nth(s_idx)
                            try:
                                if not await sel.is_visible():
                                    continue
                                # Instant check: Already has a valid selected option? Skip!
                                already_selected = await sel.evaluate("""el => {
                                    if (!el.options || el.selectedIndex < 0) return false;
                                    const opt = el.options[el.selectedIndex];
                                    return opt && opt.value && !opt.text.toLowerCase().includes('select');
                                }""")
                                if already_selected:
                                    continue  # Already filled - skip!

                                options = sel.locator("option")
                                opt_count = await options.count()
                                if opt_count <= 1:
                                    continue

                                sel_id = await sel.get_attribute("id") or ""
                                label_text = ""
                                if sel_id:
                                    label = page.locator(f"label[for='{sel_id}']")
                                    if await label.count() > 0:
                                        label_text = (await label.text_content()).strip().lower()

                                field_hint = label_text or sel_id.lower()
                                selected = False

                                for o_idx in range(opt_count):
                                    opt = options.nth(o_idx)
                                    opt_text = ((await opt.text_content()) or "").strip().lower()
                                    opt_val = (await opt.get_attribute("value") or "").strip()
                                    if not opt_val or opt_text.startswith("select"):
                                        continue

                                    if any(w in field_hint for w in ["sponsor", "sponsorship"]):
                                        if "no" in opt_text:
                                            await sel.select_option(value=opt_val)
                                            selected = True
                                            break
                                    else:
                                        if any(k in opt_text for k in ["yes", "comfortable", "agree", "confirm", "authorized"]):
                                            await sel.select_option(value=opt_val)
                                            selected = True
                                            break

                                if not selected and opt_count > 1:
                                    for o_idx in range(opt_count):
                                        opt = options.nth(o_idx)
                                        opt_val = (await opt.get_attribute("value") or "").strip()
                                        opt_text = ((await opt.text_content()) or "").strip().lower()
                                        if opt_val and not opt_text.startswith("select"):
                                            await sel.select_option(value=opt_val)
                                            break
                            except Exception:
                                pass

                        # ── 3. FILL RADIO BUTTONS (ONLY IF NOT ANSWERED) ──
                        fieldsets = page.locator("div.jobs-easy-apply-modal fieldset, div.jobs-easy-apply-modal div.fb-dash-form-element")
                        for f_idx in range(await fieldsets.count()):
                            fs = fieldsets.nth(f_idx)
                            try:
                                if not await fs.is_visible():
                                    continue
                                # Instant check: Is ANY radio in this group already selected? Skip!
                                already_checked = await fs.evaluate("el => !!el.querySelector('input[type=\"radio\"]:checked')")
                                if already_checked:
                                    continue  # Already filled - skip!

                                legend = fs.locator("legend, span.fb-dash-form-element__label, label")
                                legend_text = ""
                                if await legend.count() > 0:
                                    legend_text = ((await legend.first.text_content()) or "").strip().lower()

                                radios = fs.locator("input[type='radio']")
                                radio_count = await radios.count()
                                if radio_count == 0:
                                    continue

                                for r_i in range(radio_count):
                                    radio = radios.nth(r_i)
                                    r_id = await radio.get_attribute("id") or ""
                                    lbl = page.locator(f"label[for='{r_id}']")
                                    r_label = ""
                                    if await lbl.count() > 0:
                                        r_label = ((await lbl.text_content()) or "").strip().lower()

                                    should_select = False
                                    if any(w in legend_text for w in ["sponsor", "sponsorship"]):
                                        should_select = "no" in r_label
                                    elif any(w in legend_text for w in ["gender", "race", "disability", "veteran"]):
                                        should_select = any(d in r_label for d in ["decline", "prefer not", "don't wish"])
                                    else:
                                        should_select = any(k in r_label for k in ["yes", "comfortable", "agree", "confirm", "authorized"])

                                    if should_select:
                                        try:
                                            if await lbl.count() > 0 and await lbl.is_visible():
                                                await lbl.click()
                                            else:
                                                await radio.check(force=True)
                                        except Exception:
                                            await radio.check(force=True)
                                        print(f"   🔘 Answered: '{legend_text[:35]}' → '{r_label[:20]}'")
                                        break
                                else:
                                    try:
                                        await radios.first.check(force=True)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                        # ── 4. CHECK REQUIRED CHECKBOXES ──
                        checkboxes = page.locator("div.jobs-easy-apply-modal input[type='checkbox']")
                        for c_idx in range(await checkboxes.count()):
                            try:
                                cb = checkboxes.nth(c_idx)
                                if await cb.is_visible() and not await cb.is_checked():
                                    await cb.check(force=True)
                            except Exception:
                                pass

                        # ── 5. HANDLE NEXT OR DISMISS ──
                        next_btn = page.locator("div.jobs-easy-apply-modal button[aria-label*='Continue to next step'], div.jobs-easy-apply-modal button:has-text('Next'), div.jobs-easy-apply-modal button:has-text('Review')").first

                        if await next_btn.count() > 0 and await next_btn.is_visible():
                            await next_btn.click()
                            await page.wait_for_timeout(250)
                        else:
                            # Modal stuck or done – close it and move on
                            closed = False
                            for close_sel in [
                                "div.jobs-easy-apply-modal button[aria-label='Dismiss']",
                                "div[role='dialog'] button[aria-label='Dismiss']",
                                "button[aria-label='Dismiss']",
                            ]:
                                try:
                                    btn = page.locator(close_sel).first
                                    if await btn.is_visible(timeout=800):
                                        await btn.click(timeout=1000)
                                        closed = True
                                        break
                                except Exception:
                                    pass
                            if closed:
                                await page.wait_for_timeout(200)
                                try:
                                    discard = page.locator("button:has-text('Discard')").first
                                    if await discard.is_visible(timeout=500):
                                        await discard.click(timeout=800)
                                except Exception:
                                    pass
                            break


                except Exception as card_err:
                    print(f"⚠️ Card #{i+1} processing issue: {card_err}")
                    continue

            await browser.close()
            final_msg = f"🏆 Direct Playwright Engine Complete! Total applications submitted: {applied_count}"
            print(final_msg)
            if status_dict:
                status_dict["message"] = final_msg
                status_dict["applications"] = applied_count
                status_dict["applied_companies"] = applied_companies
            return final_msg

    except Exception as err:
        print(f"Direct Playwright LinkedIn Automation failed: {err}")
        if status_dict:
            status_dict["message"] = f"Direct Playwright completed with status: {err}"
        return str(err)


async def run_linkedin_agent(keyword, location, resume_text, experience, extra_details, status_dict=None):
    profile = load_profile()
    profile_str = json.dumps(profile, indent=2)

    session_path = os.path.join("sessions", "linkedin.json")
    if not os.path.exists(session_path):
        print(f"⚠️ Session file '{session_path}' not found.")
        print("Please run 'linkedin_session.py' first to save your LinkedIn login.")
        if status_dict:
            status_dict["message"] = "Error: Session file not found. Please login first."
        return

    # Priority 1: Gemini AI Agent first (uses Gemini API keys)
    # Priority 2: Fast Direct Playwright Engine if Gemini fails or hits rate limits
    gemini_succeeded = False
    browser_session = None

    try:
        print("🤖 Priority 1: Starting Gemini AI Agent with API keys...")
        if status_dict:
            status_dict["message"] = "Starting Gemini AI Agent with API keys..."

        llm = create_llm()

        print("🧹 Sanitizing session cookies...")
        clean_session = sanitize_session(session_path)
        
        clean_session_path = os.path.join("sessions", "linkedin_clean.json")
        with open(clean_session_path, "w", encoding="utf-8") as f:
            json.dump(clean_session, f, indent=2)

        print("🌐 Initializing BrowserSession...")
        browser_session = BrowserSession(
            storage_state=clean_session_path,
            user_data_dir=None,             # Set to None to prevent warnings and conflict issues
            headless=HEADLESS,
            is_local=True,
            wait_between_actions=2.5,
            minimum_wait_page_load_time=1.0,
            disable_security=True,
        )

        exp_filter = ""
        exp_str = str(experience).strip()
        kw_lower = str(keyword).lower()
        if exp_str == "0" or "intern" in kw_lower or "entry" in kw_lower or "fresh" in kw_lower:
            exp_filter = "&f_E=1,2"

        search_url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}&f_LF=f_AL{exp_filter}"

        user_phone = profile.get('phone') or os.getenv("APPLICANT_PHONE", "")
        user_email = profile.get('email') or os.getenv("LINKEDIN_EMAIL", "")
        user_name = profile.get('full_name') or os.getenv("APPLICANT_NAME", "Applicant")

        task_prompt = f"""You are a LinkedIn job application bot. You are already logged in to LinkedIn.

GOAL: Apply to up to {MAX_APPLICATIONS} Easy Apply jobs for keyword '{keyword}' in '{location}'.

APPLICANT PROFILE:
- Full Name: {user_name}
- Email: {user_email}
- Phone Number: {user_phone}
- Target Role / Keyword: {keyword}
- Target Experience Level: {experience} years (Internship / Entry Level / 0 years)
- User Technical Skills: {extra_details}

RESUME / SKILLS DATA:
{resume_text if resume_text else profile_str}

STEP-BY-STEP FAST WORKFLOW:
1. Navigate to: {search_url}

CRITICAL HIGH SPEED INSTRUCTION: 
The URL already filtered for Easy Apply (f_LF=f_AL) and Entry level (f_E=1,2).
DO NOT scroll down to read long descriptions. DO NOT analyze experience text. 

2. For each job card in the list:
   a. Click the job card.
   b. If the job title contains 'Senior', 'Sr', 'Lead', 'Manager', 'Director', 'Principal', skip to next card.
   c. If there is an 'Easy Apply' button, IMMEDIATELY click 'Easy Apply'.
   d. Fill out the application form quickly (ONLY FILL FIELDS THAT ARE CURRENTLY EMPTY; IF ALREADY FILLED, DO NOT TOUCH OR RE-TYPE THEM):
      - Full name: {user_name}
      - Email: {user_email}
      - Phone number: ALWAYS ENTER EXACTLY '{user_phone}'
      - City/Location: {location}
      - Experience: {experience} (e.g. 0)
      - Work authorization / eligible: Yes / Authorized
      - Sponsorship required: No
      - Notice period: Immediate / 0
      - Stipend / Salary / Compensation: Comfortable / Yes / 15000
      - Dropdowns / Radios: Pick 'Yes' / 'Comfortable' / Agree
   e. Click 'Next' or 'Continue' immediately.
   f. Click 'Submit application' when available.
   g. Close any success modal and move to the next job card immediately!

3. After {MAX_APPLICATIONS} successful submissions, STOP and report.

CRITICAL SPEED & SELECTION RULES:
- DO NOT scroll or read long descriptions in detail!
- ONLY check the Job Title and Experience on the top card:
  - If title is NOT Senior, Lead, Manager, Director, Principal, Architect, or Trainer, and experience fits (Intern/Entry/0-{experience} yrs): APPLY IMMEDIATELY.
- ALWAYS use Phone Number: '{user_phone}' for any empty phone input field.
- NEVER apply to Senior/Lead/Manager/3+ year experience positions.
- For ALL work authorization and stipend questions, answer Yes / Comfortable.
- KEEP TRACK IN YOUR MEMORY: (1) Total count of successful applications, and (2) Company Name & Job Title for every applied job.
- AT THE END: Print a clear final summary listing total applications submitted and companies applied to.
"""

        def step_callback(browser_state, model_output, step_number):
            if status_dict:
                # Check for stop request from UI
                if status_dict.get("stop_requested"):
                    status_dict["message"] = "Stopping agent as requested..."
                    raise asyncio.CancelledError("User requested bot stop.")

                status_dict["message"] = f"Step {step_number}: {model_output.next_goal or 'Thinking next action...'}"
                if model_output.memory:
                    import re
                    # Try to extract the number of successful applications from memory
                    nums = re.findall(r'(\d+)\s*(?:successful)?\s*(?:application|applied|submit)', model_output.memory.lower())
                    if nums:
                        status_dict["applications"] = int(nums[-1])

        print("🚀 Spawning browser-use Agent...")
        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser_session,
            use_vision=False,           # Disable vision
            max_failures=2,             # Quick failover to Playwright on 503 or quota errors
            enable_planning=False,      # Disable planning
            use_thinking=False,         # Disable chain-of-thought
            max_actions_per_step=1,     # Force one action at a time for reliability
            register_new_step_callback=step_callback
        )

        if status_dict:
            status_dict["message"] = "Agent started. Navigating to LinkedIn jobs..."
        result = await agent.run(max_steps=200)
        print("\n🏆 Gemini AI Agent execution complete!")
        print("Result Summary:")
        print(result)
        
        # Parse applied companies from agent history
        companies = []
        if hasattr(result, 'history') or hasattr(result, 'all_results'):
            items = getattr(result, 'all_results', getattr(result, 'history', []))
            for item in items:
                content = str(getattr(item, 'extracted_content', '')) + " " + str(getattr(item, 'long_term_memory', ''))
                if "applied" in content.lower() or "submit" in content.lower() or "clicked" in content.lower():
                    for line in content.split('\n'):
                        if any(kw in line.lower() for kw in ['applied', 'submit', 'clicked a', 'clicked span']):
                            clean_line = line.strip(' *"-🖱️')
                            if clean_line and clean_line not in companies:
                                companies.append(clean_line)
        
        total_applied = status_dict.get('applications', 0) if status_dict else 0
        if total_applied > 0:
            if status_dict:
                if companies:
                    status_dict["applied_companies"] = companies
                status_dict["message"] = f"Completed! Total applications submitted: {total_applied}"
            gemini_succeeded = True
            return result
        else:
            print("⚠️ Gemini AI Agent ended with 0 applications submitted (connection error or stuck). Switching to Fast Direct Playwright Engine...")
            gemini_succeeded = False

    except asyncio.CancelledError:
        print("🛑 Agent stopped by user request.")
        if status_dict:
            status_dict["message"] = "Bot stopped by user."
        return "Bot stopped by user."

    except Exception as e:
        print(f"⚠️ Gemini AI Agent error or quota exhausted: {e}")
        gemini_succeeded = False

    finally:
        if browser_session:
            print("🔒 Closing Gemini browser session...")
            try:
                await browser_session.stop()
            except Exception:
                pass

    # Priority 2: Fallback to Fast Direct Playwright Engine if Gemini failed / keys exhausted
    if not gemini_succeeded and not (status_dict and status_dict.get("stop_requested")):
        print("⚡ Switching to Fast Direct Playwright Engine (0 API Keys, Rapid Applying)...")
        if status_dict:
            status_dict["message"] = "Gemini API unavailable. Switched to Fast Direct Playwright Engine..."
        try:
            return await run_direct_linkedin_playwright_fallback(
                keyword, location, resume_text, experience, extra_details, status_dict
            )
        except Exception as pw_err:
            print(f"❌ Direct Playwright fallback error: {pw_err}")
            if status_dict:
                status_dict["message"] = f"Application error: {pw_err}"
            return str(pw_err)

if __name__ == "__main__":
    asyncio.run(run_linkedin_agent(JOB_KEYWORD, JOB_LOCATION, "", 0, ""))
