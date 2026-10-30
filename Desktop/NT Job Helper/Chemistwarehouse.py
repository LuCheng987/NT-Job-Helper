import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://careers.chemistwarehouse.com"
JSON_FILE = "chemist_warehouse_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """[Storage] Load previously saved Chemist Warehouse job data from local storage (JSON format)."""
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
            print(f"  ✨ New Job: {job['title']} | Location: {job['location']} | ID: {job.get('job_id', '')}")
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
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added. Total records saved locally: {len(all_jobs)}.\n"
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


def extract_chemist_warehouse_jobs(page, now_str):
    """[Parsing] Parse standard SuccessFactors table nodes with explicit safety checks and strict NT filtering."""
    jobs = []

    # Safety Check: Explicitly wait for search results table to be visible before parsing
    try:
        page.locator('table.searchResults, tr.jobResultItem').first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: Search results table took too long to appear.")
        return jobs

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

            # 3. Extract post date
            date_node = item.locator('td.colDate, [class*="date"]').first
            posted_on = date_node.inner_text(timeout=2000).strip() if date_node.count() > 0 else ""

            # 4. Precise NT filtering double-insurance
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(kw in loc_upper or kw in title_upper for kw in ["NT", "NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS", "CASUARINA", "COOLALINGA", "KATHERINE"]):
                jobs.append({
                    "title": title,
                    "job_id": href.split("/")[-2] if "/" in href else "",
                    "url": href,
                    "location": location,
                    "posted_on": posted_on,
                    "brand": "Chemist Warehouse",
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


def run_chemist_warehouse_scraper():
    target_url = "https://careers.chemistwarehouse.com/go/Australia-Careers/7906010/"

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
            print(f"🌐 Opening Chemist Warehouse Careers: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Automatically handle cookie masks
            handle_cookie_banner(page)

            # 2. Locate Region input box (#state) safely
            print("📍 1. Precisely locating Region input box (#state)...")
            region_input = page.locator('#state, input[name="state"]').first
            region_input.wait_for(state="visible", timeout=15000)

            # Capture DOM table snapshot before clicking
            table_container = page.locator('table.searchResults, tbody').first
            old_html = table_container.inner_html() if table_container.count() > 0 else ""

            random_sleep(0.8, 1.2)
            region_input.click()

            # 3. Simulate human-like character-by-character typing for NT and dispatch events
            print("⌨️ 2. Typing 'NT' character by character and dispatching events...")
            region_input.fill("")
            region_input.press_sequentially("NT", delay=random.randint(100, 180))

            region_input.evaluate("""el => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""")

            random_sleep(1.0, 1.5)

            # 4. Click explicit 'Search Jobs' submit button
            print("🔍 3. Clicking 'Search Jobs' button...")
            search_btn = page.locator('input.keywordsearch-button, input[value="Search Jobs"]').first

            if search_btn.count() > 0 and search_btn.is_visible():
                search_btn.click()
                print("  ✅ Successfully clicked 'Search Jobs' button!")
            else:
                print("⚠️ Search Jobs button not visible, falling back to Enter key...")
                region_input.press("Enter")

            # 5. Conditionally wait for table content to refresh
            print("⚡ Waiting for the table to render latest NT jobs...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('table.searchResults, tbody'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=12000,
                    )
                    print("✨ Table DOM refresh complete!")
                else:
                    page.locator('table.searchResults tbody tr').first.wait_for(state="visible", timeout=10000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 6. [Multi-page Pagination Loop] Automatically loop through pages using precise target page numbers
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1

            while True:
                print(f"\n📄 Parsing page {current_page} job listings...")
                page_jobs = extract_chemist_warehouse_jobs(page, now_str)
                print(f"✅ Successfully matched and extracted {len(page_jobs)} matching NT job(s) from page {current_page}.")

                if page_jobs:
                    save_jobs_incremental(page_jobs)
                else:
                    print("⚠️ No NT region jobs found on the current page.")

                # Precise Pagination: Look strictly for the next sequential page number link
                target_page_num = current_page + 1
                next_page_link = page.locator(
                    f'ul.pagination a[title="Page {target_page_num}"], ul.pagination a:text-is("{target_page_num}")'
                ).first

                if next_page_link.count() > 0 and next_page_link.is_visible():
                    current_first_url = page_jobs[0]["url"] if page_jobs else ""
                    print(f"➡️ Turning to page {target_page_num}...")

                    random_sleep(1.5, 2.5)
                    next_page_link.click()

                    # Wait for table content to update with new page data (Fixed with safe arg passing)
                    try:
                        if current_first_url:
                            page.wait_for_function(
                                "(oldUrl) => !document.querySelector('table.searchResults').innerHTML.includes(oldUrl)",
                                arg=current_first_url,
                                timeout=10000,
                            )
                        else:
                            random_sleep(3.0, 4.0)
                    except Exception:
                        random_sleep(3.0, 4.0)

                    current_page += 1
                else:
                    print(f"🏁 Reached the last page (Page {current_page}). Chemist Warehouse NT job scraping complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_chemist_warehouse_scraper()