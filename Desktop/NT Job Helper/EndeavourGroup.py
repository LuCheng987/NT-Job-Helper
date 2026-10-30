import csv
import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://endeavourgroupcareers.com.au"
JSON_FILE = "endeavour_jobs_nt.json"
CSV_FILE = "endeavour_jobs_nt.csv"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Endeavour Group job data from local storage (JSON format)."""
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
            print(
                f"  ✨ New Job: {job['title']} | Location: {job['location']} |"
                f" Brand: {job['brand']} | ID: {job['job_id']}"
            )
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

    # 2. Save/Update CSV (utf-8-sig prevents Excel garbled characters for Chinese/special characters)
    fieldnames = [
        "title",
        "job_id",
        "reference_id",
        "location",
        "brand",
        "type",
        "work_style",
        "url",
        "first_seen",
        "last_seen",
    ]
    try:
        with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for job in all_jobs:
                writer.writerow({k: job.get(k, "") for k in fieldnames})
        print(f"  📊 [CSV Exported] Successfully updated {CSV_FILE}")
    except Exception as e:
        print(f"  ⚠️ Failed to save CSV file: {e}")

    print(
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added this page. Total records saved locally:"
        f" {len(all_jobs)} records.\n"
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


def extract_endeavour_jobs(page, now_str):
    """Precisely parse Endeavour Group job tiles (.attrax-vacancy-tile) with explicit safety checks."""
    jobs = []

    # 💡 Safety Check: Explicitly wait for vacancy tiles container to appear
    try:
        page.locator(".attrax-vacancy-tile").first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: Endeavour job tiles container took too long to appear.")
        return jobs

    tiles = page.locator(".attrax-vacancy-tile")
    count = tiles.count()

    for i in range(count):
        try:
            tile = tiles.nth(i)

            # 1. Extract Job ID attribute
            job_id = tile.get_attribute("data-jobid") or ""

            # 2. Extract title and URL
            title_loc = tile.locator("a.attrax-vacancy-tile__title").first
            if title_loc.count() == 0:
                continue

            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # 3. Extract detailed location
            loc_node = tile.locator(
                ".attrax-vacancy-tile__location-freetext"
                " .attrax-vacancy-tile__item-value"
            ).first
            location = (
                loc_node.inner_text(timeout=2000).strip()
                if loc_node.count() > 0
                else ""
            )

            # 4. Extract work type
            type_node = tile.locator(
                ".attrax-vacancy-tile__option-work-type"
                " .attrax-vacancy-tile__item-value"
            ).first
            work_type = (
                type_node.inner_text(timeout=2000).strip()
                if type_node.count() > 0
                else ""
            )

            # 5. Extract work style
            style_node = tile.locator(
                ".attrax-vacancy-tile__option-work-style"
                " .attrax-vacancy-tile__item-value"
            ).first
            work_style = (
                style_node.inner_text(timeout=2000).strip()
                if style_node.count() > 0
                else ""
            )

            # 6. Extract brand mapping
            brand_node = tile.locator(
                ".attrax-vacancy-tile__option-brand-mapping"
                " .attrax-vacancy-tile__item-value"
            ).first
            brand = (
                brand_node.inner_text(timeout=2000).strip()
                if brand_node.count() > 0
                else "Endeavour Group"
            )

            # 7. Extract reference ID
            ref_node = tile.locator(
                ".attrax-vacancy-tile__reference-value"
            ).first
            ref_id = (
                ref_node.inner_text(timeout=2000).strip()
                if ref_node.count() > 0
                else ""
            )

            # 8. Precise NT filtering double-insurance
            loc_upper = location.upper()
            title_upper = title.upper()

            if any(
                kw in loc_upper or kw in title_upper
                for kw in [
                    "NT",
                    "NORTHERN TERRITORY",
                    "DARWIN",
                    "PALMERSTON",
                    "BERRIMAH",
                    "ALICE SPRINGS",
                    "CASUARINA",
                    "COOLALINGA",
                ]
            ):
                jobs.append({
                    "title": title,
                    "job_id": job_id,
                    "reference_id": ref_id,
                    "url": href,
                    "location": location,
                    "brand": brand,
                    "type": work_type,
                    "work_style": work_style,
                    "first_seen": now_str,
                    "last_seen": now_str,
                })

        except Exception:
            continue

    return jobs


def run_endeavour_scraper():
    target_url = (
        "https://endeavourgroupcareers.com.au/jobs?options=220&page=1&ln=&la=0&lo=0&lr=20&li=/?utm_campaign=alh-website&utm_medium=alh-network&utm_source=referral"
    )

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
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
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
            print(f"🌐 Opening Endeavour Group Careers: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. Handle cookie banner
            handle_cookie_banner(page)

            # 2. Click Locations dropdown menu safely
            print("📍 1. Clicking Locations dropdown menu...")
            locations_btn = page.locator(
                '.option-type-header:has-text("Locations"), '
                'h3.option-type-header-text:has-text("Locations")'
            ).first

            locations_btn.wait_for(state="visible", timeout=15000)
            random_sleep(0.8, 1.2)
            locations_btn.click()

            # Capture pre-click DOM list snapshot
            list_container = page.locator(".attrax-list-widget__lists").first
            old_html = (
                list_container.inner_html() if list_container.count() > 0 else ""
            )

            # 3. Check NT option safely
            print("📍 2. Selecting NT checkbox...")
            nt_option = page.locator(
                'li[data-option-id="3311"] .filter-contents, '
                'span.filter-contents[aria-label="NT"]'
            ).first

            nt_option.wait_for(state="visible", timeout=10000)
            random_sleep(0.8, 1.2)
            nt_option.click()

            # 4. Trigger Apply filters submission securely
            print("🔍 3. Triggering 'Apply filters' submission...")
            random_sleep(1.0, 1.5)
            try:
                page.evaluate(
                    "window.jobFilterNoReloadController.applyJobFilters();"
                )
                print("  ✅ Successfully triggered applyJobFilters() via JS!")
            except Exception as e:
                print(f"⚠️ JS trigger failed, attempting force click: {e}")
                apply_btn = page.locator("button.apply-filters-btn").first
                apply_btn.click(force=True)

            # 5. Conditionally wait for DOM refresh
            print("⚡ Waiting for DOM filter refresh...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el ="
                        " document.querySelector('.attrax-list-widget__lists');"
                        " return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=10000,
                    )
                else:
                    page.locator(".attrax-vacancy-tile").first.wait_for(
                        state="visible", timeout=10000
                    )
            except Exception:
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 6. [Multi-page Loop] Pagination and extraction
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1

            while True:
                print(f"\n📄 Parsing page {current_page} job listings...")
                random_sleep(1.5, 2.0)

                page_jobs = extract_endeavour_jobs(page, now_str)
                print(
                    f"✅ Successfully extracted {len(page_jobs)} NT job record(s) from page {current_page}"
                )

                if page_jobs:
                    save_jobs_incremental(page_jobs)
                else:
                    print("⚠️ No matching NT jobs found on current page.")

                # Locate Next pagination button
                next_btn = page.locator(".attrax-pagination__next a").first

                if next_btn.count() > 0 and next_btn.is_visible():
                    href = next_btn.get_attribute("href") or ""
                    if "javascript:void" in href or not href or href == "#/":
                        print("🏁 Reached the last page. Endeavour Group scraping complete!")
                        break

                    current_first_title = (
                        page_jobs[0]["title"] if page_jobs else ""
                    )
                    print("➡️ Clicking Next button to turn page...")

                    random_sleep(1.5, 2.5)
                    next_btn.click()

                    # Wait for DOM update
                    try:
                        if current_first_title:
                            page.wait_for_function(
                                "title => !"
                                " document.querySelector('.attrax-list-widget__lists').innerHTML.includes(title)",
                                arg=current_first_title,
                                timeout=10000,
                            )
                        else:
                            random_sleep(3.0, 4.0)
                    except Exception:
                        random_sleep(3.0, 4.0)

                    current_page += 1
                else:
                    print("🏁 No available Next button found, parsing complete!")
                    break

        except Exception as e:
            print(f"❌ An exception occurred during execution: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_endeavour_scraper()