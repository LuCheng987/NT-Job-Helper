import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://careers.mcdonalds.com.au"
JSON_FILE = "mcdonalds_jobs_nt.json"


def random_sleep(min_seconds=1.0, max_seconds=2.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved McDonald's job data from local storage (JSON format)."""
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
            print(f"  ✨ New Job: {job['title']} | Location: {job['location']}")
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


def extract_mcdonalds_jobs(page, now_str):
    """Parse McDonald's job listings with safety checks and precise NT regional filtering."""
    jobs = []

    items = page.locator('li[data-testid="jobs-list-only_jobs-list_item"], li.results-list__item')
    count = items.count()

    for i in range(count):
        try:
            item = items.nth(i)

            # 1. Safety check: If the list item has no title link, skip immediately without timing out
            title_loc = item.locator('a.results-list__item-title--link').first
            if title_loc.count() == 0:
                continue

            # 2. Extract title and URL with a safe 2000ms timeout
            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # 3. Extract location
            loc_node = item.locator('span.results-list__item-street--label').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            # 4. Strict entity-level NT regional filtering
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(kw in loc_upper or kw in title_upper for kw in
                   ["NT", "NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS"]):
                jobs.append({
                    "title": title,
                    "url": href,
                    "location": location,
                    "brand": "McDonald's",
                    "type": (
                        "Casual"
                        if "Casual" in title
                        else "Part Time" if "Part Time" in title else "Full Time" if "Full Time" in title else ""
                    ),
                    "first_seen": now_str,
                    "last_seen": now_str,
                })

        except Exception:
            # Catch exceptions on malformed nodes to ensure unaffected nodes are processed normally
            continue

    return jobs


def run_mcdonalds_scraper():
    target_url = "https://careers.mcdonalds.com.au/jobs"

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
            print(f"🌐 Opening McDonald's Careers page: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # 1. Automatically handle cookie consent banners
            handle_cookie_banner(page)

            # 2. Check and expand the State/Territory filter dropdown
            print("📍 Checking 'State/Territory' filter menu...")
            state_header = page.locator('#state-filter-label, [title="Filter by State/Territory"]').first
            state_header.wait_for(state="visible", timeout=15000)

            random_sleep(0.5, 1.0)

            is_expanded = state_header.get_attribute("aria-expanded")
            if is_expanded != "true":
                print("  🔽 Clicking to expand State/Territory filter menu...")
                state_header.click()
                random_sleep(0.5, 1.0)
            else:
                print("  ✅ State/Territory menu is already expanded.")

            # 3. Physically click the Northern Territory checkbox
            print("📍 Checking 'Northern Territory' option...")

            nt_option = page.locator(
                'label:has(#northern-territory_3-option-input), '
                'input#northern-territory_3-option-input, '
                'input[value="Northern Territory"], '
                '#northern-territory-label-3'
            ).first

            nt_option.wait_for(state="visible", timeout=10000)

            # Snapshot the DOM content before clicking
            container_loc = page.locator('.results-container, [data-testid="jobs-list-only_list_container"]').first
            old_html = container_loc.inner_html() if container_loc.count() > 0 else ""

            random_sleep(0.5, 1.0)
            nt_option.click()
            print("  ✅ Successfully clicked Northern Territory!")

            # 4. Block and wait for DOM updates to complete
            print("⚡ Waiting for DOM to render updated NT data...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('.results-container, [data-testid=\"jobs-list-only_list_container\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=8000,
                    )
                    print("✨ Detected DOM mutation, rendering complete!")
                else:
                    page.locator('li[data-testid="jobs-list-only_jobs-list_item"]').first.wait_for(state="visible", timeout=8000)
            except Exception:
                print("⚠️ DOM mutation wait timed out, falling back to network idle check...")
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(1.0, 1.8)

            # 5. Safely extract jobs and save incrementally
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("📄 Parsing job listings...")

            page_jobs = extract_mcdonalds_jobs(page, now_str)
            print(f"✅ Successfully extracted {len(page_jobs)} NT job record(s)")

            if page_jobs:
                save_jobs_incremental(page_jobs)
            else:
                print("⚠️ No matching NT jobs found currently.")

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_mcdonalds_scraper()