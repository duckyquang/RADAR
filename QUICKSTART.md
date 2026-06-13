# Quick Start Guide - Standalone HTML Reports

## 2-Minute Setup

### Step 1: Install & Run Backend (2 min)

```bash
pip install -r requirements.txt
python3 -m uvicorn radar_web.main:app --host 0.0.0.0 --port 8000
```

Visit: `http://localhost:8000`

### Step 2: Analyze a Guideline

1. Paste a clinical guideline DOI (e.g., `10.4158/EP161365.GL`)
2. Click "Run Analysis"
3. Wait for completion (~30 seconds to 3 minutes depending on study count)

### Step 3: Download Report

Once analysis completes:
- **CSV Report** - Tab-separated metrics data
- **HTML Report** - Standalone file with interactive charts

The HTML report works anywhere:
- Open it in any web browser
- Share it via email
- View on mobile, tablet, desktop
- No internet connection needed (fully offline)

## What's in the HTML Report?

✅ **Bias Score & Verdict**
- USABLE (< 30% bias)
- QUESTIONABLE (30-60% bias)
- NOT USABLE (> 60% bias)

✅ **Key Findings**
- Age data completeness
- Sex reporting gaps
- Race reporting gaps
- Geographic concentration

✅ **Interactive Charts**
- Data completeness by field
- Study design distribution
- Geographic breakdown
- Sex distribution

✅ **Detailed Metrics**
- Top 10 countries
- Sample size statistics
- Year range
- Participant totals

## Test It

```bash
# Start server
python3 -m uvicorn radar_web.main:app --reload

# Try these DOIs:
# - AACE Obesity 2016: 10.4158/EP161365.GL (instant, pre-computed)
# - ADA Diabetes 2025: 10.1089/dia.2024.0344 (live pipeline)
# - ATA Thyroid 2015: 10.1089/thy.2015.0020 (live pipeline)
```

## GitHub Pages Deployment

Coming soon. For now, use standalone HTML reports or the local web interface.
