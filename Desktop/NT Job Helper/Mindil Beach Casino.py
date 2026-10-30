import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://careers.delawarenorth.com"
JSON_FILE = "mindil_beach_casino_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate random sleep intervals to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Mindil Beach Casino job data from local storage (JSON format)."""
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
            print(f"  ✨ New Job: {job['title']} | Type: {job['type']} | Category: {job['category']}")
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
    """[Anti-Interception] Automatically clear cookie mask overlays safely."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Agree'), [id*='onetrust-accept']"
        ).first
        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click()
            random_sleep(0.5, 1.0)
    except Exception:
        pass


def extract_page_jobs(page, now_str):
    """Precisely parse job listing nodes for Mindil Beach Casino Resort with safety checks."""
    jobs = []

    # Explicitly wait for job cards container to appear, up to 10 seconds to prevent premature parsing
    try:
        page.locator('#widget-jobsearch-results-list div[role="row"].job').first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: Job cards container took too long to appear or is empty.")
        return jobs

    job_cards = page.locator('#widget-jobsearch-results-list div[role="row"].job')
    count = job_cards.count()

    for i in range(count):
        card = job_cards.nth(i)
        link_loc = card.locator(".jobTitle a").first

        if link_loc.count() == 0:
            continue

        title = link_loc.inner_text().strip()
        href = link_loc.get_attribute("href")
        if href and href.startswith("/"):
            href = urljoin(BASE_URL, href)

        # Extract Location
        loc_node = card.locator(".joblist-location").first
        location = loc_node.inner_text().strip() if loc_node.count() > 0 else "Darwin, Northern Territory"

        # Extract Category and Job Type
        cells = card.locator('div[role="cell"]')
        category = ""
        job_type = ""

        if cells.count() >= 3:
            category = cells.nth(1).inner_text().strip()
            job_type = cells.nth(2).inner_text().strip()
        elif cells.count() == 2:
            category = cells.nth(1).inner_text().strip()

        jobs.append({
            "title": title,
            "job_id": href.split("/")[-2] if "/" in href else "",
            "url": href,
            "location": location,
            "brand": "Mindil Beach Casino Resort",
            "category": category,
            "type": job_type,
            "first_seen": now_str,
            "last_seen": now_str,
        })

    return jobs


def run_mindil_beach_scraper():
    target_url = "https://careers.delawarenorth.com/anz/?primary_country[]=AU&primary_country[]=NZ&department[]=AU&department[]=NZ&primary_city=Darwin"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=200,
            args=["--start-maximized"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            print("🌐 Opening Mindil Beach Casino Careers page...")
            # Ensure network and DOM are fully loaded
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Handle cookie consent
            handle_cookie_banner(page)

            # 2. Click City dropdown and select Darwin safely
            print("📍 Locating and selecting City: Darwin...")
            city_container = page.locator(
                '#select2-cws_quickjobsearch_primary_city-container, .select2-selection--single').first
            city_container.wait_for(state="visible", timeout=15000)
            city_container.click()

            # Wait for Select2 dropdown popup and animation to render
            random_sleep(1.0, 1.5)

            search_input = page.locator('.select2-container--open input.select2-search__field').first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.fill("Darwin")
            random_sleep(0.5, 1.0)

            darwin_option = page.locator('li.select2-results__option:has-text("Darwin")').first
            darwin_option.wait_for(state="visible", timeout=8000)
            darwin_option.click()
            random_sleep(0.5, 1.0)

            # 3. Click Search Jobs button
            print("🔍 Clicking Search Jobs button...")
            search_btn = page.locator("input.quicksearch-submit[type='submit']").first
            search_btn.wait_for(state="visible", timeout=8000)

            try:
                search_btn.click()
            except Exception:
                page.evaluate("document.querySelector('input.quicksearch-submit').click()")

            # Wait for search results response and refresh
            print("⚡ Waiting for search results to load and render...")
            random_sleep(3.0, 4.0)

            # 4. Parse job lists and incrementally save
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1
            next_selector = "a.paginationNextLink, a[rel='next']"

            while True:
                print(f"📄 Parsing page {current_page} job listings...")

                page_jobs = extract_page_jobs(page, now_str)
                print(f"✅ Extracted {len(page_jobs)} record(s) from page {current_page}")

                if page_jobs:
                    save_jobs_incremental(page_jobs)
                else:
                    print("⚠️ No jobs found on the current page.")

                next_button = page.locator(next_selector).first

                if next_button.count() > 0 and next_button.is_visible():
                    first_job_before = page_jobs[0]["url"] if page_jobs else ""
                    print("➡️ Next page found, clicking to turn page...")
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
                    print("🏁 No next page button found, job scraping complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_mindil_beach_scraper()