import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://jobs.target.com.au"
JSON_FILE = "target_jobs_nt.json"


def random_sleep(min_seconds=1.0, max_seconds=2.0):
    """[Anti-Scraping] Generate random sleep intervals to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Target job data from local storage (JSON format)."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ Failed to read local JSON: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """[Instant Save] Incrementally update and persist jobs to local JSON file only."""
    existing_jobs = load_existing_jobs()
    new_added_count = 0

    for job in extracted_jobs:
        job_url = job["url"]
        if job_url not in existing_jobs:
            existing_jobs[job_url] = job
            new_added_count += 1
            print(f"  ✨ New Job: {job['title']} | Location: {job['location']} | ID: {job.get('job_id', '')}")
        else:
            existing_jobs[job_url]["last_seen"] = job["last_seen"]

    all_jobs = list(existing_jobs.values())

    # Save/Update JSON
    json_output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_jobs),
        "jobs": all_jobs,
    }
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    print(
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added. Total records saved locally: {len(all_jobs)}.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically clear cookie consent or privacy mask overlays."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Accept All'), "
            "button:has-text('Agree'), button:has-text('I Agree'), "
            "[id*='onetrust-accept'], [class*='cookie-accept']"
        ).first

        if cookie_btn.is_visible(timeout=2000):
            cookie_btn.click()
            random_sleep(0.5, 1.0)
    except Exception:
        pass


def extract_target_jobs(page, now_str):
    """Precisely parse SuccessFactors standard table nodes (tr.jobResultItem / table.searchResults)."""
    jobs = []

    items = page.locator('table.searchResults tbody tr, tr.jobResultItem, tr[class*="data-row"]')
    count = items.count()

    for i in range(count):
        try:
            item = items.nth(i)

            # 1. Safely extract title and URL
            title_loc = item.locator('a.jobTitle-link, a[class*="jobTitle"], td a').first
            if title_loc.count() == 0:
                continue

            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # 2. Extract location
            loc_node = item.locator('td.colLocation, [class*="location"], td:nth-child(2)').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            # 3. Extract posted date / ID if any
            date_node = item.locator('td.colDate, [class*="date"]').first
            posted_on = date_node.inner_text(timeout=2000).strip() if date_node.count() > 0 else ""

            # 4. Strict entity-level NT regional filtering
            loc_upper = location.upper()
            title_upper = title.upper()

            valid_keywords = ["NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS", "CASUARINA"]
            is_nt_match = any(kw in loc_upper or kw in title_upper for kw in valid_keywords) or \
                          any(word == "NT" for word in loc_upper.split()) or \
                          any(word == "NT" for word in title_upper.split())

            if is_nt_match:
                jobs.append({
                    "title": title,
                    "job_id": href.split("/")[-2] if "/" in href else "",
                    "url": href,
                    "location": location,
                    "posted_on": posted_on,
                    "brand": "Target Australia",
                    "type": (
                        "Casual"
                        if "CASUAL" in title_upper
                        else "Part Time" if "PART TIME" in title_upper else "Full Time" if "FULL TIME" in title_upper else ""
                    ),
                    "first_seen": now_str,
                    "last_seen": now_str,
                })

        except Exception:
            continue

    return jobs


def run_target_scraper():
    target_url = "https://jobs.target.com.au/search/"

    with sync_playwright() as p:
        print("🌐 Launching full-screen visible browser (headless=False)...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=100,
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
            print(f"🌐 Opening Target Australia Careers: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # 1. Automatically handle cookie consent banners
            handle_cookie_banner(page)

            # 2. Locate location input box
            print("📍 1. Locating location input box (#location)...")
            location_input = page.locator('#location, input[name="location"]').first
            location_input.wait_for(state="visible", timeout=15000)

            # Snapshot table DOM container before filtering
            table_container = page.locator('table.searchResults, tbody').first
            old_html = table_container.inner_html() if table_container.count() > 0 else ""

            random_sleep(0.5, 1.0)
            location_input.click()

            # 3. Type NT and trigger change events
            print("⌨️ 2. Typing 'NT' and activating change events...")
            location_input.fill("")
            location_input.press_sequentially("NT", delay=random.randint(100, 200))

            location_input.evaluate("""el => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""")

            random_sleep(0.8, 1.2)

            # 4. Precisely click #searchfilter-submit to submit filter
            print("🔍 3. Clicking #searchfilter-submit to submit filter...")
            filter_btn = page.locator('#searchfilter-submit, input[value="Filter"]').first
            filter_btn.wait_for(state="visible", timeout=5000)
            filter_btn.click()
            print("  ✅ Successfully clicked Filter button!")

            # 5. Wait for table content to refresh
            print("⚡ Waiting for table to render latest NT jobs...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('table.searchResults, tbody'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=8000,
                    )
                    print("✨ Table DOM successfully refreshed!")
                else:
                    page.locator('table.searchResults tbody tr').first.wait_for(state="visible", timeout=8000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(1.0, 1.8)

            # 6. Parse job lists and incrementally save
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("📄 Parsing Target job listings...")

            page_jobs = extract_target_jobs(page, now_str)
            print(f"✅ Successfully extracted {len(page_jobs)} matching NT job record(s)")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found currently.")

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_target_scraper()