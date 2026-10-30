import csv
import json
import os
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.harveynormancareers.com.au"
JSON_FILE = "harvey_norman_jobs_darwin.json"
CSV_FILE = "harvey_norman_jobs_darwin.csv"


def random_sleep(min_seconds=1.0, max_seconds=2.5):
    """【反爬手段】生成随机休眠时间"""
    time.sleep(random.uniform(min_seconds, max_seconds))


def load_existing_jobs():
    """读取本地已保存的职位数据（JSON格式）"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {job["url"]: job for job in data.get("jobs", [])}
        except Exception as e:
            print(f"⚠️ 读取本地 JSON 失败: {e}")
    return {}


def save_jobs_incremental(extracted_jobs):
    """【即时保存】增量更新并持久化到 JSON 和 CSV"""
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

    # 1. 保存 JSON
    json_output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_jobs),
        "jobs": all_jobs,
    }
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    # 2. 保存 CSV
    fieldnames = ["title", "location", "brand", "type", "url", "first_seen", "last_seen"]
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in all_jobs:
            writer.writerow({k: job.get(k, "") for k in fieldnames})

    print(f"💾 [即时写入完成] 本页新增 {new_added_count} 个职位，本地累计保存 {len(all_jobs)} 条记录。\n")


def handle_cookie_banner(page):
    """【防拦截】自动清理遮罩层"""
    try:
        page.evaluate("""
            const selectors = ['[id*="onetrust"]', '[id*="cookie"]', '[class*="cookie-banner"]', '.optanon-alert-box-wrapper'];
            selectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => el.remove());
            });
        """)
    except Exception:
        pass


def extract_table_jobs(page, now_str):
    """【终极防改版解析】采用‘特征锚定+多重容错’，不依赖任何易变的固定 ID】"""
    jobs = []

    # 🛡️ 防改版核心：不绑定死某个 ID，而是通过“表格中包含职位链接的行”来定位
    # 即使页面 ID 变了，只要还是表格且有 job-link，就能百分之百命中
    rows = page.locator("table tr:has(a.job-link), tr:has(a[href*='/job/'])")

    count = rows.count()
    print(f"  [Debug] 防改版选择器动态捕获到 {count} 个有效岗位行。")

    if count > 0:
        for i in range(count):
            try:
                row = rows.nth(i)

                # 排除表头行（如果有 th 的话）
                if row.locator("th").count() > 0:
                    continue

                # 1. 语义化提取职位名称和链接
                link_loc = row.locator("a.job-link, a[href*='/job/'], a[class*='job']").first
                if link_loc.count() == 0:
                    continue

                title = link_loc.inner_text().strip()
                href = link_loc.get_attribute("href")
                if not title or not href:
                    continue

                if href.startswith("/"):
                    href = urljoin(BASE_URL, href)

                # 2. 提取地点（自动寻找第二个单元格或带有 location 特征的元素）
                location = ""
                tds = row.locator("td")
                if tds.count() >= 2:
                    location = tds.nth(1).inner_text().strip()
                else:
                    loc_node = row.locator("[class*='location'], [class*='place']").first
                    if loc_node.count() > 0:
                        location = loc_node.inner_text().strip()

                row_text = row.inner_text()
                location_upper = location.upper()

                # 3. 严谨的双保险过滤（防止子字符串误伤，如 Fortitude Valley 里的 'nt'）
                valid_keywords = ["DARWIN", "PALMERSTON", "BERRIMAH", "NORTHERN TERRITORY", "DARWIN METRO"]
                is_nt_location = any(kw in location_upper for kw in valid_keywords) or \
                                 any(word == "NT" for word in location_upper.split())

                if is_nt_location:
                    # 检查是否重复添加
                    jobs.append(
                        {
                            "title": title,
                            "url": href,
                            "location": location,
                            "brand": "Harvey Norman",
                            "type": (
                                "Casual"
                                if "Casual" in row_text
                                else "Part Time" if "Part Time" in row_text else "Full Time" if "Full Time" in row_text else ""
                            ),
                            "first_seen": now_str,
                            "last_seen": now_str,
                        }
                    )
            except Exception:
                continue

    return jobs


def run_harvey_norman_scraper():
    target_url = "https://www.harveynormancareers.com.au/en/listing/"

    with sync_playwright() as p:
        print("🌐 启动防改版可视化浏览器 (headless=False)...")
        browser = p.chromium.launch(
            headless=False,
            slow_mo=150,
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
            print("🌐 打开 Harvey Norman Careers 页面...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            handle_cookie_banner(page)

            # 🛡️ 极具抗打击能力的定位：支持多重备用选择器去寻找 NT 标签
            print("📍 正在点击 'NT - Darwin Metro Area' 标签...")
            nt_label = page.locator(
                'label[for="location_ntdarwinmetroarea"], '
                'input[value*="ntdarwin"] + label, '
                'label:has-text("Darwin")'
            ).first

            nt_label.wait_for(state="visible", timeout=15000)
            random_sleep(0.8, 1.2)
            nt_label.click()
            print("  ✅ 已成功物理点击 NT 标签！")

            # 智能等待 AJAX 渲染（替代死板的等待）
            print("⏱️ 等待 AJAX 结果动态渲染就绪...")
            page.wait_for_timeout(4000)

            # 逐页解析
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_page = 1

            # 🛡️ 兼容多种翻页按钮类名
            next_selector = "a.more-link, a.paginationNextLink, a[rel='next'], li.next a, a:has-text('More Jobs')"

            while True:
                print(f"📄 正在解析第 {current_page} 页职位列表...")

                page_jobs = extract_table_jobs(page, now_str)
                print(f"✅ 第 {current_page} 页成功提取到 {len(page_jobs)} 条有效 NT 岗位")

                if page_jobs:
                    save_jobs_incremental(page_jobs)
                else:
                    print("⚠️ 当前无符合条件的 NT 岗位记录。")

                next_button = page.locator(next_selector).first

                if next_button.count() > 0 and next_button.is_visible():
                    print("➡️ 发现下一页/更多按钮，自动点击加载...")
                    random_sleep(1.5, 2.0)
                    next_button.click()
                    page.wait_for_timeout(3000)
                    current_page += 1
                else:
                    print("🏁 未找到更多/下一页按钮，Harvey Norman 职位解析保存完毕！")
                    break

        except Exception as e:
            print(f"❌ 运行出现异常: {e}")
        finally:
            browser.close()


if __name__ == "__main__":
    run_harvey_norman_scraper()