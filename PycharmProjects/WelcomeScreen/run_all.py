import subprocess
import json
import os
from datetime import datetime

# 1. 罗列你所有的爬虫脚本文件名（根据你截图里的名字准确填写）
SCRIPTS = [
    "Kmart.py",
    "Woolworths.py",
    "Bunnings.py",
    "Officeworks.py",
    "JB Hi-Fi.py",
    "McdonaldsMcdonalds.py",
    "Target.py",
    "Bunnings.py",
    "Chemistwarehouse.py",
    "DarwinHarbourCruises.py",
    "EndeavourGroup.py",
    "Harvey Norman.py",
    "Hilton Darwin.py",
    "Hungry Jacks.py",
    "Mindil Beach Casino.py",
    "Shenannigans.py",
    "The Good Guys.py",
    "Auspost.py"
]


def run_all_scrapers():
    """依次运行所有公司的爬虫脚本"""
    print("🚀 开始依次运行所有官方招聘网站爬虫...")

    for script in SCRIPTS:
        if os.path.exists(script):
            print(f"\n" + "=" * 50)
            print(f"▶️ 正在运行: {script}")
            print("=" * 50)
            try:
                # 使用 subprocess 在虚拟环境中调用每个脚本
                subprocess.run(["python", script], check=True, text=True)
                print(f"✅ {script} 运行完成并已即时保存数据！")
            except subprocess.CalledProcessError as e:
                print(f"❌ {script} 运行出错，错误代码: {e.returncode}")
            except Exception as ex:
                print(f"⚠️ 发生未知错误: {ex}")
        else:
            print(f"⚠️ 找不到脚本文件: {script}，跳过。")

    print("\n" + "=" * 50)
    print("🎉 所有爬虫执行完毕！开始合并所有公司的岗位数据...")
    aggregate_jobs()


def aggregate_jobs():
    """自动扫描并合并所有单独的 JSON 文件为一个总的 all_jobs.json"""
    all_combined_jobs = []

    # 遍历当前目录下的所有 json 文件（排除总文件本身）
    for filename in os.listdir("."):
        if filename.endswith(".json") and filename != "all_jobs.json":
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    jobs = data.get("jobs", [])
                    all_combined_jobs.extend(jobs)
                    print(f"  📥 已成功合入 [{filename}] 中的 {len(jobs)} 个岗位")
            except Exception as e:
                print(f"  ⚠️ 解析 {filename} 失败: {e}")

    # 生成最终的大聚合 JSON 文件
    output_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_combined_jobs),
        "jobs": all_combined_jobs
    }

    output_filename = "all_jobs.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"\n💾 [聚合完成] 共有 {len(all_combined_jobs)} 个职位被写入到 {output_filename} 中！")


if __name__ == "__main__":
    run_all_scrapers()