# Deployment Guide

## Quick Start

This project consists of two parts:
1. **Frontend**: GitHub Pages static site (docs/)
2. **Backend**: FastAPI application deployed to Railway.app

### 1. Deploy Backend to Railway

1. Go to [railway.app](https://railway.app)
2. Sign in with your GitHub account
3. Create a new project
4. Select "Deploy from GitHub repo"
5. Choose the RADAR repository
6. Railway will automatically detect the Procfile and deploy
7. Once deployed, copy the Railway domain URL (e.g., `https://radar-abc123.railway.app`)

### 2. Update Frontend API URL

Edit `/docs/index.html` and find this line (around line 260):

```javascript
const API_BASE = (typeof window !== "undefined" && window.location.hostname === "localhost") ? "http://localhost:8000" : window.__RADAR_API_BASE || "https://radar-backend-xxxxx.railway.app";
```

Replace `https://radar-backend-xxxxx.railway.app` with your actual Railway URL:

```javascript
const API_BASE = (typeof window !== "undefined" && window.location.hostname === "localhost") ? "http://localhost:8000" : window.__RADAR_API_BASE || "https://YOUR-RAILWAY-URL.railway.app";
```

### 3. Enable GitHub Pages

1. Go to your repository Settings
2. Scroll to "Pages" section
3. Under "Source", select "Deploy from a branch"
4. Select branch: `main`
5. Select folder: `/docs`
6. Save

Your site will be available at `https://aly-dhedhi.github.io/RADAR/`

### 4. Test

1. Visit `https://aly-dhedhi.github.io/RADAR/`
2. Enter a guideline DOI (e.g., `10.1089/dia.2024.0344` for ADA Diabetes 2025)
3. The system will extract studies, compute demographics, and display results

## Local Development

Run the backend locally:

```bash
pip3 install -r requirements.txt
cd radar_web
uvicorn main:app --reload
```

Then visit `http://localhost:8000` in your browser.

## Supported DOIs for Testing

- ADA Diabetes 2025: `10.1089/dia.2024.0344`
- AACE Obesity 2016: `10.4158/GL.2016.19.2.129`
- ATA Thyroid 2015: `10.1089/thy.2015.0315`
- AACE Osteoporosis 2020: `10.4158/GL.2020.19.4.161`
- AASLD HCC 2023: `10.1002/hep.31852`
