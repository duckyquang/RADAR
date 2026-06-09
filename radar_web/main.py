import json
import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="RADAR - Racial And Demographic Analysis of Research")

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

DATA_DIR = BASE / "data"

JOURNALS = {
    "obesity_aace_2016": {
        "name": "AACE/ACE 2016 — Obesity",
        "file": "obesity.json",
        "disease": "Obesity",
        "society": "AACE/ACE",
        "year": 2016,
    },
}

def load_data(journal_id: str):
    info = JOURNALS.get(journal_id)
    if not info:
        return None
    path = DATA_DIR / info["file"]
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "journals": JOURNALS,
        "active_journal": "obesity_aace_2016",
    })


@app.get("/api/data/{journal_id}")
async def get_data(journal_id: str):
    data = load_data(journal_id)
    if not data:
        raise HTTPException(404, "Journal data not found")
    return data


@app.get("/api/journals")
async def list_journals():
    return {k: v for k, v in JOURNALS.items()}


@app.get("/journal/{journal_id}", response_class=HTMLResponse)
async def journal_view(request: Request, journal_id: str):
    data = load_data(journal_id)
    if not data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "journals": JOURNALS,
            "active_journal": journal_id,
            "error": "Journal data not found",
        })
    return templates.TemplateResponse("index.html", {
        "request": request,
        "journals": JOURNALS,
        "active_journal": journal_id,
        "has_data": True,
    })
