#!/usr/bin/env python3
"""
RADAR Pipeline - Extract studies from guideline PDFs and determine eligibility.

Usage:
    # Step 1: Parse a journal PDF to extract studies
    python run_pipeline.py parse obesity_aace_2016

    # Step 2: Manually fill in the generated CSV with sample_size, country, sex%, race%
    # (Use your preferred editor on the output CSV)

    # Step 3: Run eligibility check on the filled CSV
    python run_pipeline.py check output/obesity_aace_2016_filled.csv

    # Step 4: Run full pipeline (parse + template)
    python run_pipeline.py all obesity_aace_2016
"""

import sys
import os
from pathlib import Path

from pipeline.parser import extract_studies_from_pdf
from pipeline.eligibility import determine_eligibility
from pipeline.utils import (
    find_journal_config,
    find_pdf_path,
    generate_template_csv,
    load_study_data,
    generate_report,
)
from pipeline.config import JOURNALS

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def cmd_parse(journal_id):
    config = find_journal_config(journal_id)
    if not config:
        print(f"Unknown journal: {journal_id}")
        print(f"Available: {[j['id'] for j in JOURNALS]}")
        return

    pdf_path = find_pdf_path(journal_id, BASE_DIR)
    if not pdf_path or not Path(pdf_path).exists():
        print(f"PDF not found for {journal_id}. Expected at: {pdf_path}")
        print("Place the exported Google Sheets PDF in the project root.")
        return

    print(f"Parsing {config['disease']} ({config['society']} {config['year']})...")
    print(f"PDF: {pdf_path}")

    studies = extract_studies_from_pdf(pdf_path)

    included = [s for s in studies if s["included"] == "Yes"]
    excluded = [s for s in studies if s["included"] == "No"]
    unknown = [s for s in studies if s["included"] not in ("Yes", "No")]

    print(f"\nTotal unique studies: {len(studies)}")
    print(f"  Included (INCLUDED=Yes): {len(included)}")
    print(f"  Excluded (INCLUDED=No):  {len(excluded)}")
    print(f"  Unknown status:          {len(unknown)}")

    out_csv = OUTPUT_DIR / f"{journal_id}_studies.csv"
    generate_template_csv(studies, out_csv)
    print(f"\nTemplate saved to {out_csv}")
    print("\nNext steps:")
    print(f"  1. Open {out_csv} in your spreadsheet editor")
    print("  2. For studies with included=Yes, fill in:")
    print("     - sample_size, country, male_pct, female_pct")
    print("     - race_white, race_black, race_hispanic, race_asian, race_other/mixed")
    print(f"  3. Run: python run_pipeline.py check {out_csv}")


def cmd_check(csv_path):
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    print(f"Loading study data from {csv_path}...")
    studies = load_study_data(csv_path)
    print(f"Loaded {len(studies)} studies")

    results = []
    for study in studies:
        result = determine_eligibility(study)
        results.append({"study": study, "result": result})

    out_csv = csv_path.parent / f"{csv_path.stem}_eligibility_report.csv"
    generate_report(results, out_csv)

    eligible = [r for r in results if r["result"]["eligible"]]
    print(f"\nEligible studies: {len(eligible)}")
    for r in eligible:
        s = r["study"]
        print(f"  {s['doi']} | {s.get('title', '')[:60]}")


def cmd_all(journal_id):
    cmd_parse(journal_id)
    csv_path = OUTPUT_DIR / f"{journal_id}_studies.csv"
    print(f"\n{'='*60}")
    print(f"Template created at: {csv_path}")
    print(f"Fill in the data columns, then run:")
    print(f"  python run_pipeline.py check {csv_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]

    if command == "parse" and len(sys.argv) >= 3:
        cmd_parse(sys.argv[2])
    elif command == "check" and len(sys.argv) >= 3:
        cmd_check(sys.argv[2])
    elif command == "all" and len(sys.argv) >= 3:
        cmd_all(sys.argv[2])
    elif command == "list":
        print("Available journals:")
        for j in JOURNALS:
            print(f"  {j['id']:30s} - {j['disease']} ({j['society']} {j['year']})")
    else:
        print(f"Unknown command or missing argument: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
