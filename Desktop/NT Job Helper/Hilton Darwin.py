import csv
import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://efet.fa.us2.oraclecloud.com"
JSON_FILE = "hilton_darwin_jobs_nt.json"
CSV_FILE = "hilton_darwin_jobs_nt.csv"


def random_sleep(min_seconds=1.0, max_seconds=2.0):
    """[Anti-Scraping] Generate random sleep intervals to simulate human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """Load previously saved Hilton Darwin job data from local storage."""
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
        "first_seen",
        "last_seen",
    ]
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in all_jobs:
            writer.writerow({k: job.get(k, "") for k in fieldnames})

    print(f"💾 [Instant Write Complete] {new_added_count} new job(s) added. Total saved: {len(all_jobs)}.\n")


def extract_oracle_jobs(page, now_str):
    """[Bulletproof Parsing] Precisely parse Oracle Cloud CX job items using data-qa='searchResultItem'."""
    jobs = []
    seen_urls = set()

    # 🛡️ 核心精准定位：Oracle Cloud 原生标准岗位容器，完美屏蔽人才社区和广告组件
    items = page.locator('li[data-qa="searchResultItem"]')
    count = items.count()
    print(f"  [Debug] Detected {count} valid 'searchResultItem' job list items.")

    for i in range(count):
        try:
            item = items.nth(i)

            # 1. 提取职位标题
            title_loc = item.locator('.job-tile__title, span[data-bind*="job.title"]').first
            if title_loc.count() == 0:
                continue
            title = title_loc.inner_text().strip()
            if not title:
                continue

            # 2. 提取岗位详情链接和 Job ID
            link_loc = item.locator('a.job-list-item__link, a[href*="/job/"]').first
            if link_loc.count() == 0:
                continue
            href = link_loc.get_attribute("href") or ""
            if not href:
                continue

            if href.startswith("/"):
                href = urljoin(BASE_URL, href)

            # URL 去重保护
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 从 URL 中精确切出数字 Job ID（例如 /job/228408/ -> 228408）
            job_id = ""
            if "/job/" in href:
                parts = href.split("/job/")
                if len(parts) > 1:
                    job_id = parts[1].split("/")[0]

            # 3. 提取工作地点
            location = ""
            loc_loc = item.locator('posting-locations span[data-bind*="primaryLocation"], .job-list-item__job-info-value').first
            if loc_loc.count() > 0:
                location = loc_loc.inner_text().strip()

            card_text = item.inner_text()
            card_text_upper = card_text.upper()

            # 4. 严谨的实体级 NT / Darwin 过滤
            valid_keywords = ["DARWIN", "PALMERSTON", "BERRIMAH", "NORTHERN TERRITORY", "ALICE SPRINGS"]
            is_nt_location = any(kw in card_text_upper for kw in valid_keywords) or \
                             any(word == "NT" for word in card_text_upper.split())

            if is_nt_location:
                jobs.append({
                    "title": title,
                    "job_id": job_id,
                    "location": location if location else "Northern Territory, Australia",
                    "brand": "Hilton Darwin",
                    "type": (
                        "Full Time"
                        if "FULL TIME" in card_text_upper
                        else "Part Time" if "PART TIME" in card_text_upper else "Casual" if "CASUAL" in card_text_upper else ""
                    ),
                    "url": href,
                    "first_seen": now_str,
                    "last_seen": now_str,
                })
        except Exception as e:
            print(f"  ⚠️ Error parsing card #{i}: {e}")
            continue

    return jobs


def run_hilton_darwin_scraper():
    target_url = "https://efet.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1009/jobs"

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
            print(f"🌐 Opening Hilton Darwin Careers (Oracle Cloud): {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            random_sleep(3.0, 4.0)

            # 1. 定位并输入搜索关键词
            print("📍 Locating search input...")
            search_input = page.locator(
                'input[placeholder*="City"], input[placeholder*="location"], input[aria-label*="Search"]').first
            if search_input.count() > 0:
                search_input.click()
                search_input.fill("NT, Australia")
                random_sleep(1.0, 2.5)
                page.keyboard.press("Enter")
                print("✨ Search submitted, waiting for results container...")
                random_sleep(3.0, 5.0)

            # 2. 显式等待搜索结果列表渲染出来
            try:
                page.locator('li[data-qa="searchResultItem"]').first.wait_for(state="visible", timeout=12000)
            except Exception:
                print("⚠️ Warning: Search results list container took too long to appear.")

            # 3. 解析岗位并增量保存
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            extracted_jobs = extract_oracle_jobs(page, now_str)

            print(f"✅ Successfully extracted {len(extracted_jobs)} valid Hilton NT job(s).")

            if extracted_jobs:
                save_jobs_incremental(extracted_jobs)
            else:
                print("⚠️ No matching NT jobs found.")

        except Exception as e:
            print(f"❌ An exception occurred: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_hilton_darwin_scraper()