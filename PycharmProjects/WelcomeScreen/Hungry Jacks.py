import csv
import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://hungryjacks.wd105.myworkdayjobs.com"
JSON_FILE = "hungry_jacks_jobs_nt.json"
CSV_FILE = "hungry_jacks_jobs_nt.csv"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate random sleep intervals to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Hungry Jack's job data from local storage (JSON format)."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ Failed to read local JSON: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """[Instant Save] Incrementally update and persist jobs to local JSON and CSV files."""
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

    # 1. Save/Update JSON
    json_output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_jobs),
        "jobs": all_jobs,
    }
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    # 2. Save/Update CSV
    fieldnames = [
        "title",
        "job_id",
        "location",
        "brand",
        "type",
        "url",
        "posted_on",
        "first_seen",
        "last_seen",
    ]
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in all_jobs:
            writer.writerow({k: job.get(k, "") for k in fieldnames})

    print(
        f"\n💾 [Instant Write Complete] {new_added_count} new job(s) added this page. Total records saved locally: {len(all_jobs)}.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically clear cookie mask overlays safely."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Accept All'), "
            "button:has-text('Agree'), button:has-text('I Agree'), "
            "[id*='onetrust-accept'], [class*='cookie-accept']"
        ).first

        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click()
            random_sleep(0.5, 1.0)
    except Exception:
        pass


def extract_hungry_jacks_jobs(page, now_str):
    """Precisely parse Workday ul/li DOM structures with safety load checks."""
    jobs = []

    # 💡 Safety Check: Explicitly wait for job list container to be fully visible before parsing
    try:
        page.locator('ul[role="list"]').first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: Job list container took too long to appear.")
        return jobs

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
            loc_node = item.locator('[data-automation-id="locations"] dd').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            # 3. Extract post date
            posted_node = item.locator('[data-automation-id="postedOn"] dd').first
            posted_on = posted_node.inner_text(timeout=2000).strip() if posted_node.count() > 0 else ""

            # 4. Extract job ID
            sub_node = item.locator('[data-automation-id="subtitle"] li').first
            job_id = sub_node.inner_text(timeout=2000).strip() if sub_node.count() > 0 else ""

            # 5. Precise NT filtering double-insurance
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(kw in loc_upper or kw in title_upper for kw in
                   ["NT", "NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS", "CASUARINA",
                    "COOLALINGA"]):
                jobs.append({
                    "title": title,
                    "job_id": job_id,
                    "url": href,
                    "location": location,
                    "posted_on": posted_on,
                    "brand": "Hungry Jack's",
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


def run_hungry_jacks_scraper():
    target_url = "https://hungryjacks.wd105.myworkdayjobs.com/en-GB/HungryJacksCareers"

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
            print(f"🌐 Opening Hungry Jack's Careers: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Automatically handle cookies
            handle_cookie_banner(page)

            # 2. Click Location filter button safely
            print("📍 1. Clicking Location filter button...")
            location_filter_btn = page.locator(
                'button[data-automation-id="distanceLocation"], '
                'button[data-uxi-element-id="filter_distanceLocation"]'
            ).first

            location_filter_btn.wait_for(state="visible", timeout=15000)
            random_sleep(0.8, 1.2)
            location_filter_btn.click()

            # Capture DOM snapshot before selection
            job_section = page.locator('ul[role="list"]').first
            old_html = job_section.inner_html() if job_section.count() > 0 else ""

            # 3. Click Northern Territory option safely
            print("📍 2. Clicking 'Northern Territory' option...")
            nt_label = page.locator('label:has-text("Northern Territory")').first
            nt_label.wait_for(state="visible", timeout=10000)
            random_sleep(0.8, 1.2)
            nt_label.click()

            # 4. Click Search button to submit
            search_btn = page.locator(
                'button:has-text("Search"), '
                'button:has-text("Apply"), '
                'button[data-automation-id*="searchButton"]'
            ).first

            if search_btn.count() > 0 and search_btn.is_visible():
                print("  ➡️ Clicking Search to submit...")
                search_btn.click()

            # 5. Conditional wait for DOM content refresh
            print("⚡ Waiting for Workday job list DOM to render...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('ul[role=\"list\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=10000,
                    )
                    print("✨ DOM successfully refreshed!")
                else:
                    page.locator('a[data-automation-id="jobTitle"]').first.wait_for(state="visible", timeout=10000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 6. Parse jobs and save incrementally
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("📄 Extracting NT job records...")

            page_jobs = extract_hungry_jacks_jobs(page, now_str)
            print(f"✅ Successfully extracted {len(page_jobs)} NT job record(s)")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found.")

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_hungry_jacks_scraper()