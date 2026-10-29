import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://ausvenueco.wd105.myworkdayjobs.com"
JSON_FILE = "shenannigans_jobs_nt.json"


def random_sleep(min_seconds=1.0, max_seconds=2.0):
    """[Anti-Scraping] Generate random sleep intervals to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Shenannigans job data from local storage (JSON format)."""
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

    print(f"💾 [Instant Write Complete] {new_added_count} new job(s) added. Total saved: {len(all_jobs)}.\n")


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically clear cookie mask overlays."""
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


def extract_shenannigans_jobs(page, now_str):
    """Precisely parse Workday job listing nodes for Shenannigans."""
    jobs = []

    items = page.locator('li:has(a[data-automation-id="jobTitle"]), li.css-1q2dra3')
    count = items.count()

    for i in range(count):
        try:
            item = items.nth(i)

            # 1. Safely locate title and URL
            title_loc = item.locator('a[data-automation-id="jobTitle"]').first
            if title_loc.count() == 0:
                continue

            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # 2. Extract location
            loc_node = item.locator('[data-automation-id="locations"] dd, [data-automation-id="locations"]').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            # 3. Extract post date
            posted_node = item.locator('[data-automation-id="postedOn"] dd, [data-automation-id="postedOn"]').first
            posted_on = posted_node.inner_text(timeout=2000).strip() if posted_node.count() > 0 else ""

            # 4. Extract job ID
            sub_node = item.locator('[data-automation-id="subtitle"] li').first
            job_id = sub_node.inner_text(timeout=2000).strip() if sub_node.count() > 0 else ""

            # 5. Precise NT filtering
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(kw in loc_upper or kw in title_upper for kw in ["NT", "NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS"]):
                jobs.append({
                    "title": title,
                    "job_id": job_id,
                    "url": href,
                    "location": location,
                    "posted_on": posted_on,
                    "brand": "Shenannigans",
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


def run_shenannigans_scraper():
    target_url = "https://ausvenueco.wd105.myworkdayjobs.com/AVC"

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
            print(f"🌐 Opening Shenannigans Careers (Workday): {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # 1. Handle cookie consent
            handle_cookie_banner(page)

            # 2. Input Northern Territory into search box
            print("📍 1. Locating keyword search input...")
            search_input = page.locator('input[data-automation-id="keywordSearchInput"]').first
            search_input.wait_for(state="visible", timeout=15000)

            job_section = page.locator('ul[role="list"]').first
            old_html = job_section.inner_html() if job_section.count() > 0 else ""

            random_sleep(0.5, 1.0)
            search_input.click()

            print("⌨️ 2. Simulating typing: Northern Territory...")
            search_input.fill("")
            search_input.press_sequentially("Northern Territory", delay=random.randint(80, 150))
            random_sleep(0.8, 1.2)

            print("🔍 3. Pressing Enter to submit search...")
            search_input.press("Enter")

            # 3. Wait for results to render
            print("⚡ Waiting for Workday to render Northern Territory data...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('ul[role=\"list\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=8000,
                    )
                    print("✨ DOM update detected, rendering complete!")
                else:
                    page.locator('a[data-automation-id="jobTitle"]').first.wait_for(state="visible", timeout=8000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(1.0, 1.8)

            # 4. Parse jobs
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            page_jobs = extract_shenannigans_jobs(page, now_str)
            print(f"✅ Successfully extracted {len(page_jobs)} NT job record(s)")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found.")

        except Exception as e:
            print(f"❌ An exception occurred: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_shenannigans_scraper()