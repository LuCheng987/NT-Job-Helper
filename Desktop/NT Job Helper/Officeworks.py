import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://mycareer.officeworks.com.au"
JSON_FILE = "officeworks_jobs_darwin.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Officeworks job data from local storage (JSON format)."""
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
    """Parse job listings on the current Officeworks page with strict regional validation."""
    jobs = []

    # Target PageUp / SuccessFactors system job result rows/nodes
    job_rows = page.locator(
        "table.searchResults tr.searchResultItem, table[id*='jobSearchResult'] tbody tr, div.searchResultsShell div.job-tile"
    )
    count = job_rows.count()

    if count > 0:
        for i in range(count):
            try:
                row = job_rows.nth(i)
                link_loc = row.locator('a[href*="/job/"], a.jobTitle-link').first

                if link_loc.count() == 0:
                    continue

                title = link_loc.inner_text().strip()
                href = link_loc.get_attribute("href")
                if href and href.startswith("/"):
                    href = urljoin(BASE_URL, href)

                row_text = row.inner_text()
                row_text_upper = row_text.upper()

                # Strict entity-level NT / Darwin regional filtering
                valid_keywords = ["NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS"]
                is_nt_match = any(kw in row_text_upper for kw in valid_keywords) or \
                              any(word == "NT" for word in row_text_upper.split())

                if is_nt_match:
                    jobs.append(
                        {
                            "title": title,
                            "url": href,
                            "location": "Darwin, Northern Territory, Australia" if "DARWIN" in row_text_upper else "Northern Territory, Australia",
                            "brand": "Officeworks",
                            "type": (
                                "Casual"
                                if "CASUAL" in row_text_upper
                                else "Part Time" if "PART TIME" in row_text_upper else "Full Time" if "FULL TIME" in row_text_upper else ""
                            ),
                            "first_seen": now_str,
                            "last_seen": now_str,
                        }
                    )
            except Exception:
                continue
    else:
        # Fallback parsing: if specific table nodes aren't found, extract links containing job paths
        job_links = page.locator('a[href*="/job/"]')
        link_count = job_links.count()
        for i in range(link_count):
            try:
                link_loc = job_links.nth(i)
                title = link_loc.inner_text().strip()
                href = link_loc.get_attribute("href")

                if href and title and len(title) > 3:
                    if href.startswith("/"):
                        href = urljoin(BASE_URL, href)

                    jobs.append(
                        {
                            "title": title,
                            "url": href,
                            "location": "Northern Territory, Australia",
                            "brand": "Officeworks",
                            "type": "",
                            "first_seen": now_str,
                            "last_seen": now_str,
                        }
                    )
            except Exception:
                continue

    return jobs


def run_officeworks_scraper():
    target_url = "https://mycareer.officeworks.com.au/?cm_sp=all:corp-hub:button:::my-career"

    with sync_playwright() as p:
        print("🌐 Launching visible browser (headless=False)...")
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
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
            print("🌐 Opening Officeworks Careers homepage...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            # 1. Automatically handle cookie consent banners
            handle_cookie_banner(page)

            # 2. Click 'Show More Options' to expand facets
            print("📍 1. Clicking 'Show More Options' button...")
            show_more_btn = page.locator('#options-search, a:has-text("Show More Options")').first
            show_more_btn.wait_for(state="visible", timeout=15000)

            random_sleep(1.0, 1.8)
            try:
                show_more_btn.click()
            except Exception:
                page.evaluate("document.getElementById('options-search').click()")

            # 3. Select 'NT' in State dropdown
            print("📍 2. Selecting 'NT' in State dropdown...")
            state_select = page.locator('#optionsFacetsDD_customfield3')
            state_select.wait_for(state="visible", timeout=10000)

            random_sleep(0.8, 1.5)
            state_select.select_option(value="NT")
            print("  ✅ Successfully selected State: NT")

            # 4. Click 'Search Jobs' button to submit
            print("🔍 3. Clicking 'Search Jobs' button...")
            search_btn = page.locator('input.keywordsearch-button[type="submit"]:visible').first

            try:
                search_btn.wait_for(state="visible", timeout=10000)
                random_sleep(0.8, 1.5)
                search_btn.click()
                print("  ✅ Successfully clicked Search Jobs button!")
            except Exception as e:
                print(f"⚠️ Standard click blocked, triggering physical JS click: {e}")
                page.evaluate("""
                    const btn = Array.from(document.querySelectorAll('input.keywordsearch-button'))
                        .find(b => b.offsetWidth > 0 && b.offsetHeight > 0);
                    if (btn) btn.click();
                """)

            print("✨ Search submitted, waiting for results to render...")
            random_sleep(3.0, 5.0)

            # 5. Parse job listings and incrementally save page by page
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1
            next_selector = "a.paginationNextLink, a[rel='next'], li.next a"

            while True:
                print(f"📄 Parsing page {current_page} job listings...")
                random_sleep(2.0, 3.5)

                page_jobs = extract_page_jobs(page, now_str)
                print(f"✅ Extracted {len(page_jobs)} NT record(s) from page {current_page}")

                if page_jobs:
                    save_jobs_incremental(page_jobs)

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
                                timeout=8000,
                            )
                        else:
                            random_sleep(3.0, 4.0)
                    except Exception:
                        random_sleep(3.0, 4.0)

                    current_page += 1
                else:
                    print("🏁 No next page button found. Officeworks job parsing complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_officeworks_scraper()