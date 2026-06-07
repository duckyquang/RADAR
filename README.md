# RADAR - Racial And Demographic Analysis of Research

Pipeline to extract clinical studies from clinical practice guideline PDF exports, determine eligibility based on demographic data availability, and produce summary statistics for systematic review papers.

## Journals Supported

| ID | Disease | Society | Year |
|----|---------|---------|------|
| `obesity_aace_2016` | Obesity | AACE/ACE | 2016 |
| `diabetes_ada_2025` | Type 2 Diabetes | ADA | 2025 |
| `thyroid_cancer_ata_2015` | Thyroid Cancer | ATA | 2015 |
| `osteoporosis_aace_2020` | Osteoporosis | AACE/ACE | 2020 |
| `hcc_aasld_2023` | Hepatocellular Carcinoma | AASLD | 2023 |

## Setup

```bash
pip install pdfplumber matplotlib openpyxl
```

## Usage

### 1. Parse a PDF
```bash
python run_pipeline.py parse obesity_aace_2016
```
Extracts study DOIs, titles, screening status, and TABLE 1 availability from the guideline PDF.

### 2. Fill demographic data
Open the generated CSV and manually extract from each cited study's full text:
- Sample size, country, sex distribution (M%/F%), race distribution (White/Black/Hispanic/Asian/Other)

### 3. Run eligibility check
```bash
python run_pipeline.py check output/obesity_aace_2016_filled.csv
```

### 4. Alternative: Analyze from spreadsheet
```bash
python scripts/analyze_spreadsheet.py
```
Reads the Google Sheets export directly for journals with manually extracted data.

## Output Structure

```
output/
├── fig1_data_completeness.png     # Data field reporting rates
├── fig2_geo_distribution.png      # Geographic distribution
├── fig3_year_distribution.png     # Publication year histogram
├── fig4_race_reporting.png        # Race category reporting rates
├── fig5_study_design.png          # Study design distribution
├── obesity_final_results.txt      # Paper-ready results
└── obesity_eligible_studies.csv   # All eligible studies with data
```

## Pipeline Modules

| Module | Purpose |
|--------|---------|
| `pipeline/parser.py` | PDF table extraction with pdfplumber |
| `pipeline/eligibility.py` | 4-criteria eligibility check |
| `pipeline/config.py` | Journal definitions, country codes, tolerances |
| `pipeline/utils.py` | CSV I/O, template generation, reporting |

## Results (Obesity 2016)

| Metric | Value |
|--------|-------|
| Studies screened | 205 |
| Eligible | 54 (26.3%) |
| Total participants | 3,559,937 |
| Year range | 1998–2015 |
| Sex reported | 96.3% |
| All 5 race categories | 42.6% |
| USA studies | 59.3% |
