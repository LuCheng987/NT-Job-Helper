import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://jobs.kmart.com.au/KMARTAUNZ/"
JSON_FILE = "kmart_jobs_nt.json"


def random_sleep(min_seconds=1.0, max_seconds=2.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved job data from local storage (JSON format)."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ Failed to read local JSON: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """[Instant Save] Incrementally update and persist jobs to local JSON file."""
    existing_jobs = load_existing_jobs()
    new_added_count = 0

    for job in extracted_jobs:
        job_url = job["url"]
        if job_url not in existing_jobs:
            existing_jobs[job_url] = job
            new_added_count += 1
            print(
                f"  ✨ New Job: {job['title']} | Location: {job['location']} | ID:"
                f" {job.get('job_id', '')}"
            )
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
        print("🍪 Checking for cookie or privacy banners...")
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Allow All'), "
            "button:has-text('Agree'), [id*='cookie'], #onetrust-accept-btn-handler"
        ).first
        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click(force=True)
            print("  ✅ Successfully dismissed cookie banner!")
            random_sleep(1.0, 1.5)
    except Exception:
        pass


def extract_kmart_jobs(page, now_str):
    """Precisely parse job list nodes from Kmart platform and filter NT jobs in Python."""
    jobs = []

    items = page.locator('tr.data-row, div.job-tile, .job-result-item, ul.jobs-list > li')
    if items.count() == 0:
        items = page.locator('table#searchresults tr:not(:first-child), div[class*="job"]')

    count = items.count()
    print(f"  [Debug] Detected {count} job item nodes on current page.")

    for i in range(count):
        try:
            item = items.nth(i)

            title_loc = item.locator('a.jobTitle, a[class*="title"], h3 a, a').first
            if title_loc.count() == 0:
                continue

            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin("https://jobs.kmart.com.au", href)
            elif href and not href.startswith("http"):
                href = urljoin(BASE_URL, href)

            job_id = ""
            if "job/" in href or "jobId=" in href:
                job_id = href.split("/")[-1].split("?")[0]

            loc_node = item.locator('.colLocation, span[class*="location"], td:nth-child(2)').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            date_node = item.locator('.colDate, span[class*="date"]').first
            posted_on = date_node.inner_text(timeout=2000).strip() if date_node.count() > 0 else ""

            loc_upper = location.upper()
            title_upper = title.upper()

            # Double-insurance regional filtering: Ensure only NT-related jobs are captured
            nt_keywords = ["NT", "NORTHERN TERRITORY", "DARWIN", "ALICE SPRINGS", "PALMERSTON", "KATHERINE", "TENNANT CREEK"]
            if any(kw in loc_upper or kw in title_upper for kw in nt_keywords):
                jobs.append({
                    "title": title,
                    "job_id": job_id,
                    "location": location,
                    "posted_on": posted_on,
                    "url": href,
                    "first_seen": now_str,
                    "last_seen": now_str,
                })
        except Exception as e:
            print(f"  [Warning] Error parsing job item #{i+1}: {e}")
            continue

    return jobs


def run_kmart_scraper():
    target_url = BASE_URL

    try:
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

            print(f"🌐 Opening Kmart careers homepage: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # Clear cookie overlay masks
            handle_cookie_banner(page)

            # 1. Locate the keyword search input box (name="q")
            print("📍 1. Locating search input box (name='q')...")
            search_input = page.locator('input[name="q"].keywordsearch-q').first
            search_input.wait_for(state="attached", timeout=15000)
            search_input.scroll_into_view_if_needed()
            random_sleep(0.5, 1.0)

            # 2. Simulate human typing for keyword 'NT'
            print("⌨️ 2. Simulating sequential typing for 'NT'...")
            search_input.click(force=True)
            search_input.fill("")
            search_input.press_sequentially("NT", delay=150)
            random_sleep(1.0, 1.5)

            # 3. Click the search button to submit
            print("🔍 3. Clicking search submission button...")
            search_submit_btn = page.locator('input[type="submit"].keywordsearch-button').first
            if search_submit_btn.is_visible(timeout=3000):
                search_submit_btn.click(force=True)
            else:
                search_input.press("Enter")

            print("⚡ Waiting for NT search results to load...")
            random_sleep(3.0, 4.0)

            # 4. Parse and instantly save results
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            page_jobs = extract_kmart_jobs(page, now_str)
            print(f"✅ Successfully extracted {len(page_jobs)} NT job record(s)")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found under current criteria.")

    except Exception as e:
        print(f"❌ An exception occurred during execution: {e}")


if __name__ == "__main__":
    run_kmart_scraper()