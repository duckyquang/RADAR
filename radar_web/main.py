import json
import os
import re
import statistics
import time
import threading
import uuid
from collections import Counter
from typing import Optional
from pathlib import Path

import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="RADAR - Racial And Demographic Analysis of Research")

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

DATA_DIR = BASE / "data"

GUIDELINES = {}
KNOWN_LINKS = {}
CROSSREF_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
PIPELINE_CACHE = {}

# Background job queue
JOBS = {}  # job_id -> {status, result, doi, meta, started, error}

from pipeline.config import COUNTRY_VALID_CODES as COUNTRY_CODES

CONTINENTS = {
    "USA": "North America", "CAN": "North America", "MEX": "North America",
    "GBR": "Europe", "DEU": "Europe", "FRA": "Europe", "ITA": "Europe", "ESP": "Europe",
    "NLD": "Europe", "SWE": "Europe", "NOR": "Europe", "FIN": "Europe", "PRT": "Europe",
    "CHE": "Europe", "DNK": "Europe", "AUT": "Europe", "BEL": "Europe", "IRL": "Europe",
    "POL": "Europe", "GRC": "Europe", "HUN": "Europe", "CZE": "Europe", "ROU": "Europe",
    "UKR": "Europe", "RUS": "Europe",
    "AUS": "Oceania", "NZL": "Oceania",
    "CHN": "Asia", "JPN": "Asia", "TWN": "Asia", "KOR": "Asia", "HKG": "Asia",
    "IND": "Asia", "ISR": "Asia", "SGP": "Asia", "THA": "Asia", "MYS": "Asia",
    "IDN": "Asia", "VNM": "Asia", "PHL": "Asia", "SAU": "Asia", "ARE": "Asia", "TUR": "Asia",
    "BRA": "South America", "ARG": "South America", "COL": "South America", "CHL": "South America",
    "ZAF": "Africa", "EGY": "Africa", "NGA": "Africa", "KEN": "Africa",
}

COUNTRY_NAMES = {
    "USA": "United States", "CAN": "Canada", "MEX": "Mexico",
    "GBR": "United Kingdom", "DEU": "Germany", "FRA": "France",
    "ITA": "Italy", "ESP": "Spain", "NLD": "Netherlands",
    "SWE": "Sweden", "NOR": "Norway", "FIN": "Finland",
    "PRT": "Portugal", "AUS": "Australia", "NZL": "New Zealand",
    "CHN": "China", "JPN": "Japan", "TWN": "Taiwan",
    "KOR": "South Korea", "HKG": "Hong Kong", "IND": "India",
    "BRA": "Brazil", "ZAF": "South Africa", "ISR": "Israel",
    "CHE": "Switzerland", "DNK": "Denmark", "AUT": "Austria",
    "BEL": "Belgium", "IRL": "Ireland", "POL": "Poland",
    "RUS": "Russia", "TUR": "Turkey", "EGY": "Egypt",
    "NGA": "Nigeria", "ARG": "Argentina", "COL": "Colombia",
    "CHL": "Chile", "KEN": "Kenya", "THA": "Thailand",
    "VNM": "Vietnam", "IDN": "Indonesia", "MYS": "Malaysia",
    "SGP": "Singapore", "PHL": "Philippines", "SAU": "Saudi Arabia",
    "ARE": "UAE", "CZE": "Czech Republic", "ROU": "Romania",
    "UKR": "Ukraine", "HUN": "Hungary", "GRC": "Greece",
}

DESIGN_KEYWORDS = [
    ("randomized", "RCT / Clinical Trial"), ("rct", "RCT / Clinical Trial"),
    ("trial", "RCT / Clinical Trial"), ("clinical trial", "RCT / Clinical Trial"),
    ("cross-sectional", "Cross-sectional"), ("cross sectional", "Cross-sectional"),
    ("cohort", "Cohort"), ("prospective", "Cohort"),
    ("longitudinal", "Cohort"), ("retrospective", "Cohort"),
    ("observational", "Observational"),
    ("meta-analysis", "Review / Meta-analysis"), ("meta analysis", "Review / Meta-analysis"),
    ("systematic review", "Review / Meta-analysis"), ("review", "Review / Meta-analysis"),
    ("survey", "Survey"), ("case-control", "Case-Control"),
    ("case control", "Case-Control"), ("case series", "Case Series"),
]


def resolve_doi(input_str: str) -> str:
    s = input_str.strip().strip('"\' ')
    if s in KNOWN_LINKS:
        return KNOWN_LINKS[s]
    for prefix in ["https://doi.org/", "http://dx.doi.org/", "doi:", "doi.org/"]:
        if s.startswith(prefix):
            s = s[len(prefix):]
    s = s.rstrip("/")
    return s


def load_precomputed(doi: str) -> Optional[dict]:
    info = GUIDELINES.get(doi)
    if not info:
        return None
    path = DATA_DIR / info["file"]
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def scan_precomputed():
    for path in DATA_DIR.glob("*.json"):
        with open(path) as f:
            try:
                d = json.load(f)
            except:
                continue
        j = d.get("journal", {})
        doi = j.get("doi", "")
        if doi:
            doi_clean = doi.replace("https://doi.org/", "").rstrip("/")
            if doi_clean and doi_clean not in GUIDELINES:
                GUIDELINES[doi_clean] = {
                    "id": j.get("id", path.stem),
                    "file": path.name,
                    "disease": j.get("disease", ""),
                    "society": j.get("society", ""),
                    "year": j.get("year", ""),
                    "title": j.get("title", ""),
                }
                KNOWN_LINKS[f"https://doi.org/{doi_clean}"] = doi_clean


scan_precomputed()


def lookup_crossref(doi: str) -> Optional[dict]:
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}",
                         headers=CROSSREF_HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        msg = r.json().get("message", {})
        title = msg.get("title", [None])
        if isinstance(title, list):
            title = title[0] if title else None
        authors = []
        for a in msg.get("author", []):
            name = f"{a.get('given','')} {a.get('family','')}".strip()
            if name:
                authors.append(name)
        container = msg.get("container-title", [None])
        if isinstance(container, list):
            container = container[0] if container else None
        pd = msg.get("published-print", {}).get("date-parts", [[None]])[0]
        if not pd or pd == [None]:
            pd = msg.get("published-online", {}).get("date-parts", [[None]])[0]
        year = pd[0] if pd and pd[0] else None
        return {
            "doi": doi, "title": title, "authors": authors[:5],
            "author_str": "; ".join(authors[:5]), "year": year,
            "publisher": msg.get("publisher", ""), "journal": container,
            "type": msg.get("type", ""),
        }
    except:
        return None


def _run_pipeline_job(doi: str, job_id: str):
    try:
        JOBS[job_id]["status"] = "running"
        from live_pipeline.runner import run as live_run
        result = live_run(doi)
        if "error" in result:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = result["error"]
        else:
            PIPELINE_CACHE[doi] = result
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result
    except Exception as e:
        import traceback
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = f"{e}\n{traceback.format_exc()}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "guidelines": {
            doi: {"disease": v["disease"], "society": v["society"], "year": v["year"]}
            for doi, v in GUIDELINES.items()
        },
    })


@app.post("/api/analyze")
async def analyze(doi_url: str = Form(...)):
    doi = resolve_doi(doi_url)

    # Serve precomputed if available
    precomputed = load_precomputed(doi)
    if precomputed:
        return JSONResponse({"found": True, "doi": doi, "data": precomputed, "precomputed": True})

    # Serve from in-memory cache
    if doi in PIPELINE_CACHE:
        return JSONResponse({"found": True, "doi": doi, "data": PIPELINE_CACHE[doi], "precomputed": False, "cached": True})

    # Verify DOI resolves via CrossRef
    meta = lookup_crossref(doi)
    if not meta:
        return JSONResponse({
            "found": False,
            "message": f"Could not resolve DOI: {doi}. Please check the DOI and try again.",
        })

    # Return existing job if already running for this DOI
    for jid, job in JOBS.items():
        if job.get("doi") == doi and job["status"] in ("pending", "running"):
            return JSONResponse({"found": True, "job_id": jid, "status": "running",
                                 "meta": meta, "elapsed": round(time.time() - job["started"])})

    # Start new background job
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "pending", "result": None, "doi": doi,
                    "meta": meta, "started": time.time(), "error": None}
    t = threading.Thread(target=_run_pipeline_job, args=(doi, job_id), daemon=True)
    t.start()

    return JSONResponse({"found": True, "job_id": job_id, "status": "running", "meta": meta, "elapsed": 0})


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in JOBS:
        return JSONResponse({"status": "not_found"}, status_code=404)
    job = JOBS[job_id]
    elapsed = round(time.time() - job["started"])
    if job["status"] == "done":
        return JSONResponse({"status": "done", "found": True, "doi": job["doi"],
                             "data": job["result"], "elapsed": elapsed})
    elif job["status"] == "error":
        return JSONResponse({"status": "error", "message": job.get("error", "Unknown error"),
                             "elapsed": elapsed})
    else:
        return JSONResponse({"status": job["status"], "elapsed": elapsed})


@app.get("/api/guidelines")
async def list_guidelines():
    return {doi: {"disease": v["disease"], "society": v["society"], "year": v["year"]}
            for doi, v in GUIDELINES.items()}
