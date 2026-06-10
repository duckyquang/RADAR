# Quick Start Guide

## 3-Minute Setup

### Step 1: Deploy Backend (2 min)

1. Visit [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select the RADAR repository
4. Railway auto-detects settings and starts building
5. **Copy the deployment URL** when it finishes (e.g., `https://radar-abc123.railway.app`)

### Step 2: Update Frontend (1 min)

1. Edit `/docs/index.html` (line 260)
2. Find: `"https://radar-backend-xxxxx.railway.app"`
3. Replace with your Railway URL from Step 1
4. Commit and push: `git add docs/ && git commit -m "Update API URL" && git push`

### Step 3: Enable GitHub Pages (instant)

1. Go to repo Settings → Pages
2. Source: "Deploy from a branch"
3. Branch: `main` | Folder: `/docs`
4. Save

✅ Done! Visit `https://aly-dhedhi.github.io/RADAR/` to start analyzing guidelines.

## Test It

Enter any clinical guideline DOI:
- ADA Diabetes 2025: `10.1089/dia.2024.0344`
- AACE Obesity 2016: `10.4158/GL.2016.19.2.129`
- ATA Thyroid 2015: `10.1089/thy.2015.0315`

The system extracts all cited studies, analyzes demographics, and displays results in real-time.

## Local Dev

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn radar_web.main:app --reload
# Visit http://localhost:8000
```
