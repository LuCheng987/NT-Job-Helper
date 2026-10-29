import json
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.jbhifi.com.au"
JSON_FILE = "jbhifi_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved JB Hi-Fi job data from local storage (JSON format)."""
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
            print(f"  ✨ New Job: {job['title']} | Location: {job['location']} | Type: {job['type']}")
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
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added this page. Total records saved locally: {len(all_jobs)}.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically clear cookie mask overlays safely."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Agree'), "
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
    """Precisely parse JB Hi-Fi (SmartRecruiters) job rows with explicit safety checks and strict NT filtering."""
    jobs = []

    # Safety Check: Explicitly wait for job rows container to appear before parsing
    try:
        page.locator("tr[class*='srJobListJob']").first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: SmartRecruiters job rows took too long to appear.")
        return jobs

    job_rows = page.locator("tr[class*='srJobListJob']")
    count = job_rows.count()

    if count > 0:
        for i in range(count):
            try:
                row = job_rows.nth(i)

                # Extract job title
                title_loc = row.locator("td.srJobListJobTitle").first
                if title_loc.count() == 0:
                    continue
                title = title_loc.inner_text().strip()

                # Extract URL from onclick attribute
                onclick_attr = row.get_attribute("onclick") or ""
                url_match = re.search(r'https?://[^\s"\']+', onclick_attr)
                href = url_match.group(0) if url_match else ""

                # Extract employment type
                type_loc = row.locator("td.srJobListTypeOfEmployment").first
                job_type = type_loc.inner_text().strip() if type_loc.count() > 0 else ""

                # Extract department / category
                dept_loc = row.locator("td.srJobListDepartment").first
                category = dept_loc.inner_text().strip() if dept_loc.count() > 0 else ""

                # Extract location
                loc_element = row.locator("td.srJobListLocation spl-job-location").first
                location = ""
                if loc_element.count() > 0:
                    location = loc_element.get_attribute("formattedaddress") or loc_element.inner_text().strip()

                # Extract published date
                pub_loc = row.locator("td.srJobListPublishedSince").first
                published_at = pub_loc.inner_text().strip() if pub_loc.count() > 0 else ""

                # Strict entity-level NT / Darwin filtering (Prevents capturing out-of-region jobs)
                row_text = row.inner_text()
                location_upper = location.upper()
                valid_keywords = ["DARWIN", "PALMERSTON", "BERRIMAH", "NORTHERN TERRITORY", "ALICE SPRINGS"]
                is_nt_location = any(kw in location_upper for kw in valid_keywords) or \
                                 any(word == "NT" for word in location_upper.split()) or \
                                 any(kw in row_text.upper() for kw in valid_keywords)

                if is_nt_location:
                    jobs.append(
                        {
                            "title": title,
                            "url": href,
                            "location": location,
                            "brand": "JB Hi-Fi",
                            "category": category,
                            "type": job_type,
                            "published_at": published_at,
                            "first_seen": now_str,
                            "last_seen": now_str,
                        }
                    )
            except Exception:
                continue

    return jobs


def run_jbhifi_scraper():
    target_url = "https://www.jbhifi.com.au/pages/jobs"

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
            print("🌐 Opening JB Hi-Fi Jobs page...")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Handle cookie consent banners
            handle_cookie_banner(page)

            # 2. Locate filter input and type NT safely
            print("📍 1. Locating search input...")
            search_input = page.locator('#filter-by:visible, input[aria-label*="Filter by title"]:visible').first
            search_input.wait_for(state="visible", timeout=15000)

            random_sleep(1.0, 1.8)
            search_input.click()

            print("⌨️ 2. Simulating typing search keyword: NT...")
            search_input.press_sequentially("NT", delay=random.randint(100, 200))
            random_sleep(1.0, 1.5)

            # 3. Click Search button
            print("🔍 3. Clicking Search button...")
            search_btn = page.locator('input.srSearchButton[type="button"]:visible, input[value="Search"]:visible').first

            try:
                search_btn.wait_for(state="visible", timeout=5000)
                search_btn.click()
                print("  ✅ Successfully clicked Search button!")
            except Exception as e:
                print(f"⚠️ Button click blocked, falling back to Enter key: {e}")
                page.keyboard.press("Enter")

            print("✨ Search submitted, waiting for results to render...")
            random_sleep(3.0, 5.0)

            # 4. Parse results and incrementally save
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1
            next_selector = "a.srPaginationNext, a[rel='next'], li.next a"

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
                                timeout=10000,
                            )
                        else:
                            random_sleep(3.0, 4.0)
                    except Exception:
                        random_sleep(3.0, 4.0)

                    current_page += 1
                else:
                    print("🏁 No next page button found. JB Hi-Fi job parsing complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_jbhifi_scraper()