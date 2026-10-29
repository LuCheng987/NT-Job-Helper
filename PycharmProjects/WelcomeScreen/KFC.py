import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://careers.kfc.com.au"
JSON_FILE = "kfc_jobs_nt.json"


def random_sleep(min_seconds=1.5, max_seconds=3.0):
    """[Anti-Scraping] Generate a random sleep interval to simulate human operation delays."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved KFC job data from local storage (JSON format)."""
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
        f"💾 [Instant Write Complete] {new_added_count} new job(s) added this page. Total records saved locally: {len(all_jobs)}.\n"
    )


def handle_cookie_banner(page):
    """[Anti-Interception] Automatically accept cookies or forcefully remove overlay masks."""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Accept All'), "
            "button:has-text('Agree'), button:has-text('I Agree'), "
            "[id*='onetrust-accept'], [class*='cookie-accept']"
        ).first

        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click(force=True)
            random_sleep(0.8, 1.2)
    except Exception:
        pass


def dismiss_ai_chat_if_present(page):
    """[Anti-Interception] Extensible guardian: Instantly dismisses the AI chat popup whenever it pops up."""
    try:
        close_btn = page.locator('button[aria-label="Close widget chat"], button[title="Close widget chat"], button.ea1514').first
        if close_btn.is_visible(timeout=1500):
            close_btn.click(force=True)
            print("  🛡️ [Guardian] Detected and safely dismissed sudden AI chat popup!")
            random_sleep(0.5, 0.8)
    except Exception:
        pass


def extract_kfc_jobs(page, now_str):
    """Precisely parse KFC job listings from results list items with strict entity-level NT filtering."""
    jobs = []

    try:
        page.locator('li[data-testid="jobs-list-only_jobs-list_item"]').first.wait_for(state="visible", timeout=10000)
    except Exception:
        print("⚠️ Warning: KFC job items container took too long to appear.")
        return jobs

    items = page.locator('li[data-testid="jobs-list-only_jobs-list_item"]')
    count = items.count()

    for i in range(count):
        try:
            item = items.nth(i)

            title_loc = item.locator('a.results-list__item-title--link').first
            if title_loc.count() == 0:
                continue

            title = title_loc.inner_text(timeout=2000).strip()
            href = title_loc.get_attribute("href") or ""
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            loc_node = item.locator('span.results-list__item-street--label').first
            location = loc_node.inner_text(timeout=2000).strip() if loc_node.count() > 0 else ""

            loc_upper = location.upper()
            title_upper = title.upper()

            # Strict regional matching
            valid_keywords = ["NORTHERN TERRITORY", "DARWIN", "PALMERSTON", "BERRIMAH", "ALICE SPRINGS", "CASUARINA", "COOLALINGA"]
            is_nt_match = any(kw in loc_upper or kw in title_upper for kw in valid_keywords) or \
                          any(word == "NT" for word in loc_upper.split()) or \
                          any(word == "NT" for word in title_upper.split())

            if is_nt_match:
                jobs.append({
                    "title": title,
                    "url": href,
                    "location": location,
                    "brand": "KFC",
                    "type": (
                        "Casual"
                        if "Casual" in title
                        else "Part Time" if "Part Time" in title else "Full Time" if "Full Time" in title else ""
                    ),
                    "first_seen": now_str,
                    "last_seen": now_str,
                })

        except Exception:
            continue

    return jobs


def run_kfc_scraper():
    target_url = "https://careers.kfc.com.au/jobs"

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
            print(f"🌐 Opening KFC Careers page: {target_url}")
            page.goto(target_url, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            random_sleep(2.0, 3.0)

            # 1. 随时拦截：清理 Cookie 弹窗和初次可能出现的 AI 窗口
            handle_cookie_banner(page)
            dismiss_ai_chat_if_present(page)

            # 2. 定位搜索框
            print("📍 Locating location search input...")
            search_input = page.locator('input[data-testid="jobs-search_location_input"]').first
            search_input.wait_for(state="visible", timeout=15000)

            list_container = page.locator('ul[data-testid="jobs-list-only_jobs-list"]').first
            old_html = list_container.inner_html() if list_container.count() > 0 else ""

            random_sleep(0.8, 1.2)
            search_input.click()
            search_input.fill("")

            # 3. 再次防守：在输入文字前检查 AI 窗口是否突然弹出
            dismiss_ai_chat_if_present(page)

            print("⌨️ Simulating human typing: NT...")
            search_input.press_sequentially("NT", delay=random.randint(100, 200))
            random_sleep(1.0, 1.5)

            # 4. 关键防守：输入完后、点击搜索前，AI 窗口最喜欢在这个空档跳出来，再次拦截！
            dismiss_ai_chat_if_present(page)

            # 5. 点击 Search 按钮
            print("🔍 Clicking Search button...")
            search_btn = page.locator('button[data-testid="jobs-search_button-search"]').first
            search_btn.wait_for(state="visible", timeout=5000)

            try:
                search_btn.click(force=True)
            except Exception:
                page.evaluate("document.querySelector('button[data-testid=\"jobs-search_button-search\"]').click()")

            # 6. 等待搜索结果渲染，顺便再扫一眼防守
            dismiss_ai_chat_if_present(page)

            print("⚡ Waiting for KFC search results to refresh...")
            try:
                if old_html:
                    page.wait_for_function(
                        "old => { const el = document.querySelector('ul[data-testid=\"jobs-list-only_jobs-list\"]'); return el && el.innerHTML !== old; }",
                        arg=old_html,
                        timeout=10000,
                    )
                    print("✨ Detected DOM update, results rendering complete!")
                else:
                    page.locator('li[data-testid="jobs-list-only_jobs-list_item"]').first.wait_for(state="visible", timeout=10000)
            except Exception:
                print("⚠️ DOM update wait timed out, falling back to network idle...")
                page.wait_for_load_state("networkidle", timeout=5000)

            random_sleep(2.0, 3.0)

            # 7. 解析岗位并增量保存
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print("📄 Parsing KFC job listings...")

            page_jobs = extract_kfc_jobs(page, now_str)
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
    run_kfc_scraper()