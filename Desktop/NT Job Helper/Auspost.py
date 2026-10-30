import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://jobs.auspost.com.au"
JSON_FILE = "auspost_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to disrupt fixed-frequency request patterns."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """[Storage] Load previously saved AusPost job data from local storage (JSON format)."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ Failed to read local JSON: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """[Instant Save] Incrementally update and persist jobs to local JSON storage (CSV excluded)."""
    existing_jobs = load_existing_jobs()
    new_added_count = 0

    for job in extracted_jobs:
        job_url = job["url"]
        if job_url not in existing_jobs:
            existing_jobs[job_url] = job
            new_added_count += 1
            print(f"  ✨ New Job: {job['title']} | Location: {job['location']} | Type: {job['type']}")
        else:
            existing_jobs[job_url]["last_seen"] = job["last_seen"]

    all_jobs = list(existing_jobs.values())

    # Save/Update JSON output
    json_output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_jobs),
        "jobs": all_jobs,
    }
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    print(
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added this page. Total records saved locally: {len(all_jobs)}.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically click accept cookies or physically remove overlay masks."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Accept All'), "
            "button:has-text('Agree'), button:has-text('I Agree'), "
            "[id*='onetrust-accept'], [class*='cookie-accept']"
        ).first

        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click()
            random_sleep(1.0, 1.8)
    except Exception:
        pass

    try:
        page.evaluate("""
            const selectors = [
                '[id*="onetrust"]', '[id*="cookie"]', '[class*="cookie-banner"]',
                '[class*="cookie-modal"]', '.optanon-alert-box-wrapper'
            ];
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => el.remove());
            });
        """)
    except Exception:
        pass


def extract_page_jobs(page, now_str):
    """[Parsing] Parse job listings precisely using robust multi-tier fallback selectors with strict NT filtering."""
    jobs = []

    # Defensive check: Wait for article elements with multi-tier fallback
    try:
        page.locator('article.article--result, article[class*="result"]').first.wait_for(state="visible", timeout=12000)
    except Exception:
        print("⚠️ Warning: Job article containers took too long to appear.")
        return jobs

    # Multi-tier fallback locator for job articles
    job_articles = page.locator('article.article--result, article[class*="result"]')
    count = job_articles.count()
    print(f"  [Debug] Detected {count} total job article(s) on the page.")

    for i in range(count):
        try:
            article = job_articles.nth(i)

            # 1. Resilient title and link extraction
            link_loc = article.locator('h3 a.link, [class*="title"] a, a.link, h3 a').first
            if link_loc.count() == 0:
                continue

            title = link_loc.inner_text().strip()
            href = link_loc.get_attribute("href")
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # 2. Resilient subtitle/metadata extraction
            subtitle_loc = article.locator('.article__header__text__subtitle, [class*="subtitle"]').first
            card_text = subtitle_loc.inner_text() if subtitle_loc.count() > 0 else article.inner_text()
            card_text_upper = card_text.upper()
            title_upper = title.upper()

            # 3. Precise location extraction using specific sub-elements if available
            location_val = "Northern Territory"
            loc_span = article.locator('.list-item-location, [class*="location"]').first
            if loc_span.count() > 0:
                location_val = loc_span.inner_text().strip()
            else:
                if "DARWIN" in card_text_upper:
                    location_val = "Darwin, NT"
                elif "ALICE SPRINGS" in card_text_upper:
                    location_val = "Alice Springs, NT"

            # 4. Precise work type extraction
            job_type = ""
            type_span = article.locator('.list-item-workType, [class*="workType"]').first
            if type_span.count() > 0:
                job_type = type_span.inner_text().strip()
            else:
                if "CASUAL" in card_text_upper:
                    job_type = "Casual"
                elif "PART TIME" in card_text_upper:
                    job_type = "Part Time"
                elif "FULL TIME" in card_text_upper:
                    job_type = "Full Time"

            # Strict Northern Territory region filtering
            if any(kw in card_text_upper or kw in title_upper for kw in
                   ["NT", "NORTHERN TERRITORY", "DARWIN", "ALICE SPRINGS", "PALMERSTON", "KATHERINE", "TENNANT CREEK"]):
                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "location": location_val,
                        "brand": "Australia Post",
                        "type": job_type,
                        "first_seen": now_str,
                        "last_seen": now_str,
                    }
                )
        except Exception as e:
            print(f"⚠️ Error parsing article item {i}: {e}")
            continue

    return jobs


def run_auspost_scraper():
    target_url = "https://jobs.auspost.com.au/en_GB/careers/SearchJobs"

    with sync_playwright() as p:
        print("🌐 Launching full-screen visible browser (headless=False)...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=200,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-AU",
            timezone_id="Australia/Darwin",
        )

        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        try:
            print(f"🌐 Opening Australia Post SearchJobs page: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Clear cookie banners and overlays
            handle_cookie_banner(page)

            # 2. Click the Select2 dropdown container first to make the internal search input appear
            print("📍 Clicking Select2 dropdown container to expand...")
            dropdown_container = page.locator(
                '.select2-selection, [class*="select2-selection"], [aria-labelledby*="10975"]').first
            dropdown_container.wait_for(state="visible", timeout=15000)
            dropdown_container.click()
            random_sleep(1.0, 1.5)

            # 3. Locate the dynamic search input inside the dropdown and type "NT"
            print("⌨️ Locating Select2 internal search field ([id=\"10975-search__field\"])...")
            select2_input = page.locator('[id="10975-search__field"], input.select2-search__field').first
            select2_input.wait_for(state="visible", timeout=10000)

            select2_input.click()
            select2_input.fill("")

            print("⌨️ Typing 'NT' directly into the dropdown...")
            select2_input.press_sequentially("NT", delay=random.randint(100, 180))
            random_sleep(1.5, 2.0)

            # Press Enter and Escape to close the dropdown list and commit the selection
            page.keyboard.press("Enter")
            random_sleep(0.5, 1.0)
            page.keyboard.press("Escape")
            random_sleep(1.0, 1.5)
            print("  ✅ Successfully selected 'NT' and closed dropdown!")

            # Capture pre-submit HTML snapshot for dynamic change detection
            results_container = page.locator('.section__content__results, [class*="results"]').first
            old_html = results_container.inner_html() if results_container.count() > 0 else ""

            # 4. Scroll to Search button, ensure it's visible, and click it forcefully
            print("🔍 Locating and clicking Search button ([id=\"10981-submit\"])...")
            search_btn = page.locator('button[id="10981-submit"], button.submitButton').first
            search_btn.wait_for(state="visible", timeout=10000)

            # Scroll element into view to avoid obstruction
            search_btn.scroll_into_view_if_needed()
            random_sleep(0.5, 1.0)

            search_btn.click(force=True)
            print("  ✅ Clicked Search button successfully!")

            # 5. Wait for search results to refresh dynamically
            print("⚡ Waiting for search results to render...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('.section__content__results, [class*=\"results\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=12000,
                    )
                    print("✨ Search results updated successfully!")
                else:
                    page.locator('article.article--result, article[class*="result"]').first.wait_for(state="visible",
                                                                                                     timeout=10000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 6. Parse jobs and save incrementally with pagination
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1
            next_selector = "a.paginationNextLink, a[rel='next'], li.next a, a:has-text('Next'), [class*='next'] a"

            while True:
                print(f"📄 Parsing page {current_page} job listings...")

                page_jobs = extract_page_jobs(page, now_str)
                print(f"✅ Successfully extracted {len(page_jobs)} NT record(s) from page {current_page}")

                if page_jobs:
                    save_jobs_incremental(page_jobs)
                else:
                    print("⚠️ No matching NT records found on the current page.")

                next_button = page.locator(next_selector).first

                if next_button.count() > 0 and next_button.is_visible():
                    first_job_before = page_jobs[0]["url"] if page_jobs else ""
                    print("➡️ Next page found, clicking to turn page...")

                    random_sleep(1.5, 2.5)
                    next_button.click()

                    try:
                        if first_job_before:
                            page.wait_for_function(
                                f"() => !document.body.innerHTML.includes('{first_job_before}')",
                                timeout=10000,
                            )
                        else:
                            random_sleep(3.0, 4.0)
                    except Exception:
                        random_sleep(3.0, 4.0)

                    current_page += 1
                else:
                    print("🏁 No next page button found. Australia Post NT job parsing and saving complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_auspost_scraper()