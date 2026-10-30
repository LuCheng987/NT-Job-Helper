# import csv
# import json
# import os
# import time
# from datetime import datetime
# from urllib.parse import urljoin
# from playwright.sync_api import sync_playwright
#
# BASE_URL = "https://careers.woolworthsgroup.com.au"
# JSON_FILE = "woolworths_jobs.json"
# CSV_FILE = "woolworths_jobs.csv"
#
#
# def load_existing_jobs():
#     """读取本地已经保存的职位数据（JSON格式）"""
#     if os.path.exists(JSON_FILE):
#         try:
#             with open(JSON_FILE, "r", encoding="utf-8") as f:
#                 data = json.load(f)
#                 return {job["url"]: job for job in data.get("jobs", [])}
#         except Exception as e:
#             print(f"⚠️ 读取本地 JSON 失败: {e}")
#     return {}
#
#
# def save_jobs_incremental(extracted_jobs):
#     """【即时保存】增量更新并持久化保存到本地 JSON 和 CSV 文件"""
#     existing_jobs = load_existing_jobs()
#     new_added_count = 0
#
#     for job in extracted_jobs:
#         job_url = job["url"]
#         if job_url not in existing_jobs:
#             existing_jobs[job_url] = job
#             new_added_count += 1
#             print(f"  ✨ 新增职位: {job['title']} | 地点: {job['location']}")
#         else:
#             existing_jobs[job_url]["last_seen"] = job["last_seen"]
#
#     all_jobs = list(existing_jobs.values())
#
#     # 1. 保存/更新 JSON
#     json_output = {
#         "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#         "total_unique_jobs": len(all_jobs),
#         "jobs": all_jobs,
#     }
#     with open(JSON_FILE, "w", encoding="utf-8") as f:
#         json.dump(json_output, f, ensure_ascii=False, indent=4)
#
#     # 2. 保存/更新 CSV
#     fieldnames = [
#         "title",
#         "location",
#         "brand",
#         "type",
#         "url",
#         "first_seen",
#         "last_seen",
#     ]
#     with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=fieldnames)
#         writer.writeheader()
#         for job in all_jobs:
#             writer.writerow({k: job.get(k, "") for k in fieldnames})
#
#     print(
#         f"💾 [即时写入完成] 本页新增 {new_added_count} 个职位，本地累计保存 {len(all_jobs)} 条记录。\n"
#     )
#
#
# def extract_page_jobs(page, now_str):
#     """解析当前页面的所有职位信息"""
#     jobs = []
#
#     # 针对 PageUp 系统的常见职位条目容器
#     job_cards = page.locator(
#         ".job-search-results .job-item, tr.job-row, .search-results-list > div, table[class*='Result'] tbody tr"
#     )
#     count = job_cards.count()
#
#     if count > 0:
#         for i in range(count):
#             card = job_cards.nth(i)
#             link_loc = card.locator('a[href*="/job/"]').first
#
#             if link_loc.count() == 0:
#                 continue
#
#             title = link_loc.inner_text().strip()
#             href = link_loc.get_attribute("href")
#             if href and href.startswith("/"):
#                 href = urljoin(BASE_URL, href)
#
#             card_text = card.inner_text()
#             jobs.append(
#                 {
#                     "title": title,
#                     "url": href,
#                     "location": (
#                         "Hobart, TAS" if "Hobart" in card_text else "TAS"
#                     ),
#                     "brand": (
#                         "Big W"
#                         if "Big W" in card_text
#                         else "Woolworths Supermarkets"
#                     ),
#                     "type": (
#                         "Casual"
#                         if "Casual" in card_text
#                         else "Part Time" if "Part Time" in card_text else ""
#                     ),
#                     "first_seen": now_str,
#                     "last_seen": now_str,
#                 }
#             )
#     else:
#         # 兜底：抓取所有 JobDetail 链接
#         job_links = page.locator('a[href*="/JobDetail/"], a[href*="/job/"]')
#         link_count = job_links.count()
#         for i in range(link_count):
#             link_loc = job_links.nth(i)
#             title = link_loc.inner_text().strip()
#             href = link_loc.get_attribute("href")
#
#             if href and title:
#                 if href.startswith("/"):
#                     href = urljoin(BASE_URL, href)
#
#                 jobs.append(
#                     {
#                         "title": title,
#                         "url": href,
#                         "location": "TAS",
#                         "brand": "Woolworths Group",
#                         "type": "",
#                         "first_seen": now_str,
#                         "last_seen": now_str,
#                     }
#                 )
#
#     return jobs
#
#
# def search_and_print_jobs():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(
#             headless=False,
#             slow_mo=200,
#             args=["--start-maximized"],
#         )
#
#         context = browser.new_context(
#             user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
#             viewport={"width": 1280, "height": 800},
#         )
#         page = context.new_page()
#
#         print("🌐 打开 Store Teams 招聘搜索页...")
#         page.goto(
#             "https://careers.woolworthsgroup.com.au/en_GB/apply/search-jobs?13316=6987&listFilterMode=1",
#             wait_until="domcontentloaded",
#             timeout=60000,
#         )
#
#         page.wait_for_selector('[id="13888"]', timeout=15000)
#
#         # ----------------------------------------------------
#         # 1. 设置搜索参数
#         # ----------------------------------------------------
#         print("🌏 1. 设置国家: Australia...")
#         page.locator('[id="13888"]').select_option(value="11322")
#
#         print("📍 2. 打开地点选择框并选择 Hobart...")
#         page.locator(".select2Container13321_location_place").click()
#
#         search_input = page.locator(
#             '.select2-container--open input.select2-search__field, input[aria-controls*="13321_location_place"]'
#         ).first
#         search_input.wait_for(state="visible", timeout=5000)
#         search_input.fill("Hobart")
#
#         target_item = page.locator('[id="liHobart, Tasmania, Australia"]')
#         target_item.wait_for(state="visible", timeout=5000)
#         target_item.click()
#
#         print("📏 3. 设置距离: 100 kilometers...")
#         page.locator('[id="13321_location_radius"]').select_option(value="100")
#
#         # ----------------------------------------------------
#         # 2. 点击 Search 提交搜索
#         # ----------------------------------------------------
#         page.evaluate("""
#             const placeSelect = document.getElementById('13321_location_place');
#             if (placeSelect) {
#                 placeSelect.dispatchEvent(new Event('change', {bubbles: true}));
#             }
#         """)
#
#         print("🔍 点击 Search 按钮...")
#         search_button = page.locator('[id="13322-submit"]')
#         try:
#             search_button.click()
#         except Exception:
#             page.evaluate("document.getElementById('13322-submit').click()")
#
#         # ----------------------------------------------------
#         # 3. 逐页解析 -> 本地保存 -> 寻找并点击 Next >>
#         # ----------------------------------------------------
#         now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         current_page = 1
#
#         # 根据您的 HTML，精确选择下一个按钮：
#         next_selector = "a.paginationNextLink"
#
#         while True:
#             print(f"📄 正在解析第 {current_page} 页职位列表...")
#             page.wait_for_timeout(2000)
#
#             # 步骤 1: 解析当前页
#             page_jobs = extract_page_jobs(page, now_str)
#             print(f"✅ 第 {current_page} 页提取到 {len(page_jobs)} 条记录")
#
#             # 步骤 2: 【关键】本页数据抓完后，立刻写入本地
#             if page_jobs:
#                 save_jobs_incremental(page_jobs)
#
#             # 步骤 3: 寻找 "Next >>" 分页链接
#             next_button = page.locator(next_selector).first
#
#             if next_button.count() > 0 and next_button.is_visible():
#                 next_href = next_button.get_attribute("href")
#                 print(f"➡️ 发现下一页链接: {next_href}")
#
#                 # 记录翻页前第一个职位的URL，用于判定页面刷新完成
#                 first_job_before = (
#                     page_jobs[0]["url"] if page_jobs else ""
#                 )
#
#                 # 点击 Next 按钮
#                 next_button.click()
#
#                 # 等待 DOM/页面刷新
#                 try:
#                     if first_job_before:
#                         page.wait_for_function(
#                             f"() => !document.body.innerHTML.includes('{first_job_before}')",
#                             timeout=8000,
#                         )
#                     else:
#                         page.wait_for_timeout(3000)
#                 except Exception:
#                     page.wait_for_timeout(3000)
#
#                 current_page += 1
#             else:
#                 print("🏁 未找到 'a.paginationNextLink' 按钮，说明已到达最后一页或仅有一页。")
#                 break
#
#         time.sleep(3)
#         browser.close()
#
#
# if __name__ == "__main__":
#     search_and_print_jobs()

import csv
import json
import os
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://careers.woolworthsgroup.com.au"
JSON_FILE = "woolworths_jobs_darwin.json"
CSV_FILE = "woolworths_jobs_darwin.csv"


def load_existing_jobs():
    """读取本地已经保存的职位数据（JSON格式）"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ 读取本地 JSON 失败: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """【即时保存】增量更新并持久化保存到本地 JSON 和 CSV 文件"""
    existing_jobs = load_existing_jobs()
    new_added_count = 0

    for job in extracted_jobs:
        job_url = job["url"]
        if job_url not in existing_jobs:
            existing_jobs[job_url] = job
            new_added_count += 1
            print(f"  ✨ 新增职位: {job['title']} | 地点: {job['location']}")
        else:
            existing_jobs[job_url]["last_seen"] = job["last_seen"]

    all_jobs = list(existing_jobs.values())

    # 1. 保存/更新 JSON
    json_output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_jobs),
        "jobs": all_jobs,
    }
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    # 2. 保存/更新 CSV
    fieldnames = [
        "title",
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

    print(
        f"💾 [即时写入完成] 本页新增 {new_added_count} 个职位，本地累计保存 {len(all_jobs)} 条记录。\n"
    )


def handle_cookie_banner(page):
    """【防 Cookie 拦截】自动点击同意 Cookie 或物理移除遮罩层"""
    try:
        cookie_btn = page.locator(
            "button:has-text('Accept'), button:has-text('Accept All'), "
            "button:has-text('Agree'), button:has-text('I Agree'), "
            "[id*='onetrust-accept'], [class*='cookie-accept']"
        ).first

        if cookie_btn.is_visible(timeout=3000):
            cookie_btn.click()
            print("🍪 成功自动点击同意 Cookie 弹窗！")
            page.wait_for_timeout(1000)
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
    """解析当前页面的所有职位信息（适配 Darwin, NT）"""
    jobs = []

    # 针对 PageUp 系统的常见职位条目容器
    job_cards = page.locator(
        ".job-search-results .job-item, tr.job-row, .search-results-list > div, table[class*='Result'] tbody tr"
    )
    count = job_cards.count()

    if count > 0:
        for i in range(count):
            card = job_cards.nth(i)
            link_loc = card.locator('a[href*="/job/"]').first

            if link_loc.count() == 0:
                continue

            title = link_loc.inner_text().strip()
            href = link_loc.get_attribute("href")
            if href and href.startswith("/"):
                href = urljoin(BASE_URL, href)

            card_text = card.inner_text()
            jobs.append(
                {
                    "title": title,
                    "url": href,
                    "location": (
                        "Darwin, NT" if "Darwin" in card_text else "NT"
                    ),
                    "brand": (
                        "Big W"
                        if "Big W" in card_text
                        else "Woolworths Supermarkets"
                    ),
                    "type": (
                        "Casual"
                        if "Casual" in card_text
                        else "Part Time" if "Part Time" in card_text else ""
                    ),
                    "first_seen": now_str,
                    "last_seen": now_str,
                }
            )
    else:
        # 兜底：抓取所有 JobDetail 链接
        job_links = page.locator('a[href*="/JobDetail/"], a[href*="/job/"]')
        link_count = job_links.count()
        for i in range(link_count):
            link_loc = job_links.nth(i)
            title = link_loc.inner_text().strip()
            href = link_loc.get_attribute("href")

            if href and title:
                if href.startswith("/"):
                    href = urljoin(BASE_URL, href)

                jobs.append(
                    {
                        "title": title,
                        "url": href,
                        "location": "Darwin, NT",
                        "brand": "Woolworths Group",
                        "type": "",
                        "first_seen": now_str,
                        "last_seen": now_str,
                    }
                )

    return jobs


def search_and_print_jobs():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=200,
            args=["--start-maximized"],
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print("🌐 打开 Store Teams 招聘搜索页...")
        page.goto(
            "https://careers.woolworthsgroup.com.au/en_GB/apply/search-jobs?13316=6987&listFilterMode=1",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        # 0. 检查并清理 Cookie 弹窗遮罩
        handle_cookie_banner(page)

        page.wait_for_selector('[id="13888"]', timeout=15000)

        # ----------------------------------------------------
        # 1. 设置搜索参数 (Australia -> Darwin, NT -> 100km)
        # ----------------------------------------------------
        print("🌏 1. 设置国家: Australia...")
        page.locator('[id="13888"]').select_option(value="11322")

        handle_cookie_banner(page)

        print("📍 2. 打开地点选择框并搜索选择 Darwin...")
        page.locator(".select2Container13321_location_place").click()

        search_input = page.locator(
            '.select2-container--open input.select2-search__field, input[aria-controls*="13321_location_place"]'
        ).first
        search_input.wait_for(state="visible", timeout=5000)

        # 填充 Darwin
        search_input.fill("Darwin")

        # 匹配下拉列表中包含 Darwin, Northern Territory 的选项
        target_item = page.locator(
            '[id="liDarwin, Northern Territory, Australia"], li.select2-results__option:has-text("Darwin")'
        ).first
        target_item.wait_for(state="visible", timeout=5000)
        target_item.click()

        print("📏 3. 设置距离: 100 kilometers...")
        page.locator('[id="13321_location_radius"]').select_option(value="100")

        # ----------------------------------------------------
        # 2. 点击 Search 提交搜索
        # ----------------------------------------------------
        page.evaluate("""
                      const placeSelect = document.getElementById('13321_location_place');
                      if (placeSelect) {
                          placeSelect.dispatchEvent(new Event('change', {bubbles: true}));
                      }
                      """)

        print("🔍 点击 Search 按钮...")
        search_button = page.locator('[id="13322-submit"]')
        try:
            search_button.click()
        except Exception:
            page.evaluate("document.getElementById('13322-submit').click()")

        # ----------------------------------------------------
        # 3. 逐页解析 -> 本地保存 -> 寻找并点击 Next >>
        # ----------------------------------------------------
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_page = 1

        next_selector = "a.paginationNextLink"

        while True:
            print(f"📄 正在解析第 {current_page} 页职位列表...")
            page.wait_for_timeout(2000)

            # 步骤 1: 解析当前页
            page_jobs = extract_page_jobs(page, now_str)
            print(f"✅ 第 {current_page} 页提取到 {len(page_jobs)} 条记录")

            # 步骤 2: 本页数据抓完后，立刻写入本地
            if page_jobs:
                save_jobs_incremental(page_jobs)

            # 步骤 3: 寻找 "Next >>" 分页链接
            next_button = page.locator(next_selector).first

            if next_button.count() > 0 and next_button.is_visible():
                next_href = next_button.get_attribute("href")
                print(f"➡️ 发现下一页链接: {next_href}")

                first_job_before = page_jobs[0]["url"] if page_jobs else ""

                next_button.click()

                try:
                    if first_job_before:
                        page.wait_for_function(
                            f"() => !document.body.innerHTML.includes('{first_job_before}')",
                            timeout=8000,
                        )
                    else:
                        page.wait_for_timeout(3000)
                except Exception:
                    page.wait_for_timeout(3000)

                current_page += 1
            else:
                print("🏁 未找到 'a.paginationNextLink' 按钮，说明已到达最后一页或仅有一页。")
                break

        time.sleep(3)
        browser.close()


if __name__ == "__main__":
    search_and_print_jobs()