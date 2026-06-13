# RADAR — Racial And Demographic Analysis of Research

**Live site:** https://duckyquang.github.io/RADAR/
**Presentation:** `RADAR_Presentation.pptx` — 14-slide deck for team presentation (slides included in repo)

Analyze any clinical practice guideline to extract demographic diversity metrics from cited studies. Enter a DOI, and RADAR automatically fetches all referenced studies, extracts demographic data (sex, race, country) from PMC full-text XML, runs eligibility checks, and generates interactive charts with a bias assessment.

---

## Quick Start

### Option A: GitHub Pages (static, 6 pre-computed guidelines)

Visit https://duckyquang.github.io/RADAR/ and click any example button — results load instantly. For other guidelines, use the live pipeline.

### Option B: Live pipeline (any DOI)

```bash
pip install -r requirements.txt
python3 -m uvicorn radar_web.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — enter any guideline DOI and the pipeline runs live.

### Option C: Via public API tunnel

GH Pages also tries a public HTTPS API. Currently the API is tunneled from localhost — for permanent production, deploy to Render (see below).

---

## How It Works

1. **CrossRef lookup** — resolves the guideline DOI and fetches all cited references
2. **PubMed/PMC enrichment** — each cited study DOI is looked up in PubMed; if a PMCID exists, the full-text XML is parsed for demographic tables (sample size, sex%, race%)
3. **Eligibility checks** — sample size > 0, valid country code, sex M+F ≈ 100%, 5 race categories reported
4. **Results** — interactive dashboard with KPIs, charts (completeness, design, geography, trends, race distribution), sortable study table, and a bias score card
5. **Downloadable reports** — CSV or standalone HTML with all charts embedded

---

## Deployment to Render (permanent public API)

The repo includes `render.yaml` for one-click deployment:

1. Sign up at https://render.com
2. Click **New Web Service** → connect your GitHub repo
3. Render auto-detects `render.yaml` — deploy
4. Set the resulting URL (e.g. `https://radar-api.onrender.com`) as `PUBLIC_API_URL` in `index.html`

---

## Pre-computed Guidelines

| DOI | Guideline | Studies | Eligible | Participants | With Race |
|-----|-----------|--------:|---------:|-------------:|----------:|
| `10.1097/HEP.0000000000000466` | AASLD HCC 2023 | 318 | 113 | 18.9M | 24 |
| `10.2337/dc25-S001` | ADA Diabetes 2025 | 129 | 35 | 927K | 16 |
| `10.1089/thy.2015.0020` | ATA Thyroid 2015 | 999 | 78 | 60.5M | 2 |
| `10.4158/EP161365.GL` | AACE Obesity 2016 | 205 | 54 | 3.6M | — |
| `10.4158/GL-2020-0524SUPPL` | AACE Osteoporosis 2020 | 343 | 62 | 578K | 4 |
| `10.1093/eurheartj/ehab484` | ESC CVD Prevention 2021 | 773 | 42 | 1.6M | 3 |

---

## Project Structure

```
├── index.html                  # GH Pages frontend (crimson/black theme)
├── data/                       # Pre-computed guideline JSON files
├── radar_web/
│   ├── main.py                 # FastAPI server
│   ├── templates/index.html    # Server-served frontend
│   └── static/                 # Static assets
├── live_pipeline/
│   ├── runner.py               # Pipeline orchestrator
│   ├── fetcher.py              # CrossRef/PubMed/PMC API calls
│   └── demographics.py         # PMC XML parser + text extraction
├── pipeline/                   # Legacy batch pipeline (PDF-based)
├── render.yaml                 # Render deployment config
└── requirements.txt
```

---

## Tech Stack

- **Frontend:** Vanilla JS + Chart.js, responsive CSS (crimson/black/white)
- **Backend:** Python FastAPI + uvicorn
- **Data Sources:** CrossRef API, PubMed E-utilities, PMC Open Access
- **Deployment:** GitHub Pages (frontend), Render/Railway/Fly.io (API)
- **Rate Limiting:** Thread-locked NCBI rate limiter (0.35s interval)
