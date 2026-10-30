import json
import os
import subprocess
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Mount static files directory for logos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Bind the templates directory
templates = Jinja2Templates(directory="templates")

JSON_FILE = "all_jobs.json"

# List of all company scrapers to run on startup
SCRIPTS = [
    "Auspost.py",
    "Bunnings.py",
    "Chemistwarehouse.py",
    "DarwinHarbourCruises.py",
    "EndeavourGroup.py",
    "Harvey Norman.py",
    "Hilton Darwin.py",
    "Hungry Jacks.py",
    "JB Hi-Fi.py",
    "KFC.py",
    "Kmart.py",
    "Mcdonalds.py",
    "Mindil Beach Casino.py",
    "Officeworks.py",
    "Shenannigans.py",
    "Target.py",
    "The Good Guys.py",
    "Woolworths.py"
]


def run_all_scrapers():
    """Sequentially execute all company scrapers on startup."""
    print("🚀 [Startup Trigger] Starting sequential execution of all official career site scrapers...")

    for script in SCRIPTS:
        if os.path.exists(script):
            print("\n" + "=" * 50)
            print(f"▶️ Running: {script}")
            print("=" * 50)
            try:
                subprocess.run(["python", script], check=True, text=True)
                print(f"✅ {script} completed and data saved instantly!")
            except subprocess.CalledProcessError as e:
                print(f"❌ {script} failed with exit code: {e.returncode}")
            except Exception as ex:
                print(f"⚠️ An unknown error occurred: {ex}")
        else:
            print(f"⚠️ Script file not found: {script}, skipping.")

    print("\n" + "=" * 50)
    print("🎉 All scrapers executed! Starting to aggregate all job data into all_jobs.json...")
    aggregate_jobs()


def aggregate_jobs():
    """Automatically scan and merge all individual JSON files into a unified all_jobs.json."""
    all_combined_jobs = []

    for filename in os.listdir("."):
        if filename.endswith(".json") and filename != "all_jobs.json":
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    jobs = data.get("jobs", [])
                    all_combined_jobs.extend(jobs)
                    print(f"  📥 Successfully merged {len(jobs)} job(s) from [{filename}]")
            except Exception as e:
                print(f"  ⚠️ Failed to parse {filename}: {e}")

    output_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_unique_jobs": len(all_combined_jobs),
        "jobs": all_combined_jobs
    }

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"\n💾 [Aggregation Complete] A total of {len(all_combined_jobs)} positions have been written to {JSON_FILE}!\n")


def get_logo_filename(brand_name):
    """Map company brand names precisely to the files in static/logos/."""
    mapping = {
        "auspost": "auspost.png",
        "bunnings": "bunnings.png",
        "chemist warehouse": "chemistwarehouse.png",
        "darwin harbour cruises": "darwinharbourcruises.svg",
        "endeavour group": "endeavourgroup.png",
        "alh hotels": "endeavourgroup.png",       # ALH Hotels 映射至 endeavorgroup.png
        "harvey norman": "harveynorman.png",
        "hilton darwin": "hiltondarwin.png",
        "hungry jack's": "hungryjacks.png",
        "jb hi-fi": "jbhifi.png",
        "kfc": "kfc.png",
        "kmart": "kmart.png",
        "mcdonald's": "mcdonalds.png",
        "mindil beach casino resort": "mindilbeachcasino.svg",
        "officeworks": "officeworks.png",
        "shenannigans": "shenannigans.png",
        "target australia": "target.png",
        "the good guys": "thegoodguys.png",
        "woolworths": "woolworths.png"
    }
    normalized = brand_name.lower().strip()
    return mapping.get(normalized, f"{normalized.replace(' ', '').replace('\'', '')}.png")


def load_all_jobs():
    """Load saved job data from local storage and attach correct logo paths."""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                jobs = data.get("jobs", [])
                for job in jobs:
                    brand = job.get("brand", "Company")
                    job["logo_file"] = get_logo_filename(brand)
                return jobs
        except Exception as e:
            print(f"⚠️ Failed to read JSON: {e}")
    return []


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the home page and pass job data to the frontend."""
    jobs = load_all_jobs()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "jobs": jobs,
            "total": len(jobs)
        }
    )


if __name__ == "__main__":
    # Uncomment below if you want scrapers to run automatically on every server restart
    # run_all_scrapers()

    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001, reload=False)
