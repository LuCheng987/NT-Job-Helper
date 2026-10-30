import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://apply.workable.com/journey-beyond/"
JSON_FILE = "darwin_harbour_cruises_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """[Storage] Load previously saved Darwin Harbour Cruises job data from local storage (JSON format)."""
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
            print(
                f"  ✨ New Job: {job['title']} | Location: {job['location']} | Type:"
                f" {job.get('type', '')}"
            )
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
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added. Total records saved locally:"
        f" {len(all_jobs)} records.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Force wait and use force=True to robustly click the Accept all button."""
    try:
        print("🍪 Checking for Cookie consent banner...")
        accept_btn = page.locator('button[data-ui="cookie-consent-accept"]')
        accept_btn.wait_for(state="visible", timeout=5000)
        accept_btn.click(force=True)
        print("  ✅ Successfully clicked 'Accept all' button!")
        random_sleep(1.0, 1.5)
    except Exception as e:
        print(f"  ℹ️ Cookie banner not detected or already skipped: {e}")


def extract_workable_jobs(page, now_str):
    """[Parsing] Precisely parse Workable job list items using robust fallback selectors."""
    jobs = []

    try:
        page.locator('ul[data-ui="list"] li[data-ui="job"], li[data-ui="job"]').first.wait_for(state="visible", timeout=12000)
    except Exception:
        print("⚠️ Warning: Workable job items container took too long to appear.")
        return jobs

    items = page.locator('ul[data-ui="list"] li[data-ui="job"], li[data-ui="job"]')
    count = items.count()
    print(f"  [Debug] Detected {count} job card nodes on the page.")

    for i in range(count):
        try:
            item = items.nth(i)

            # 1. Extract job title and URL
            link_loc = item.locator('a[href*="/journey-beyond/j/"], a').first
            if link_loc.count() == 0:
                continue

            href = link_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin("https://apply.workable.com", href)

            title_loc = item.locator('h3[data-ui="job-title"], h3').first
            title = title_loc.inner_text(timeout=2000).strip() if title_loc.count() > 0 else ""
            if not title:
                continue

            # 2. Extract location text
            loc_node = item.locator('[data-ui="job-location"], div[class*="location"]').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else "Northern Territory"

            # 3. Extract job type and department
            type_node = item.locator('[data-ui="job-type"]').first
            job_type = type_node.inner_text(timeout=2000).strip() if type_node.count() > 0 else ""

            dept_node = item.locator('[data-ui="job-department"]').first
            department = dept_node.inner_text(timeout=2000).strip() if dept_node.count() > 0 else ""

            print(f"    - Found Card: [{title}] at [{location}]")

            # 4. Strict NT filtering double-insurance
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(kw in loc_upper or kw in title_upper for kw in
                   ["NT", "NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "ALICE SPRINGS", "KATHERINE", "WINNELLIE", "LARRAKEYAH"]):
                jobs.append({
                    "title": title,
                    "location": location,
                    "type": job_type,
                    "department": department,
                    "url": href,
                    "first_seen": now_str,
                    "last_seen": now_str,
                })
        except Exception as e:
            print(f"  [Warning] Error parsing job item #{i + 1}: {e}")
            continue

    return jobs


def run_darwin_harbour_cruises_scraper():
    target_url = BASE_URL

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
            print(f"🌐 Opening Darwin Harbour Cruises Careers (Workable): {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            handle_cookie_banner(page)

            # 1. Click the Location dropdown container safely using text or robust ID
            print("📍 1. Clicking 'Location' dropdown input...")
            location_input = page.locator('#locations-filter_input, [data-ui="locations-filter"]').first
            location_input.wait_for(state="visible", timeout=15000)

            list_container = page.locator('ul[data-ui="list"], ul[class*="jobs"]').first
            old_html = list_container.inner_html() if list_container.count() > 0 else ""

            location_input.click()
            random_sleep(1.0, 1.5)

            # 2. Select 'Northern Territory' robustly using text matching (bypassing unstable IDs)
            print("📍 2. Selecting 'Northern Territory' from location options...")
            try:
                nt_option = page.get_by_text("Northern Territory", exact=False).first
                nt_option.wait_for(state="visible", timeout=5000)
                nt_option.click()
                print("  ✅ Successfully clicked 'Northern Territory' option!")
            except Exception as e:
                print(f"⚠️ Text match click failed ({e}), trying fallback key events...")
                page.keyboard.type("Northern Territory")
                page.keyboard.press("Enter")

            random_sleep(1.0, 1.5)

            # 3. Force click blank area to clear any lingering dropdown overlay
            print("🖱️ 3. Click blank area to dismiss dropdown menu...")
            page.mouse.click(200, 100)
            random_sleep(1.5, 2.0)

            # 4. Wait for DOM content to refresh automatically based on address selection
            print("⚡ Waiting for results to update dynamically...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('ul[data-ui=\"list\"], ul[class*=\"jobs\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=10000,
                    )
                else:
                    page.locator('ul[data-ui="list"] li[data-ui="job"], li[data-ui="job"]').first.wait_for(state="visible", timeout=10000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 5. [Optional Show more Loop] Click 'Show more' if present
            print("🔄 Checking for 'Show more' button...")
            load_more_btn = page.locator('button[data-ui="load-more-button"]').first
            if load_more_btn.count() > 0 and load_more_btn.is_visible():
                click_count = 0
                while load_more_btn.count() > 0 and load_more_btn.is_visible():
                    try:
                        click_count += 1
                        print(f"  ➡️ Clicking 'Show more' button (Attempt {click_count})...")
                        load_more_btn.click(force=True)
                        random_sleep(1.8, 2.5)
                        load_more_btn = page.locator('button[data-ui="load-more-button"]').first
                    except Exception:
                        break
                print("✨ All additional listings expanded!")
            else:
                print("ℹ️ No 'Show more' button found, proceeding directly to record jobs...")

            # 6. Parse and incrementally save JSON records
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            page_jobs = extract_workable_jobs(page, now_str)
            print(f"✅ Successfully matched and extracted {len(page_jobs)} NT job record(s).")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found. Please verify if Darwin Harbour Cruises has active NT roles currently.")

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_darwin_harbour_cruises_scraper()