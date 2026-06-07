import csv
from pathlib import Path

from .config import JOURNALS, RACE_CATEGORIES


def find_journal_config(journal_id):
    for j in JOURNALS:
        if j["id"] == journal_id:
            return j
    return None


def find_pdf_path(journal_id, base_dir=None):
    config = find_journal_config(journal_id)
    if not config:
        return None

    filename = config.get("pdf_filename")
    if not filename:
        return None

    if base_dir:
        candidate = Path(base_dir) / filename
        if candidate.exists():
            return str(candidate)

    return filename


def generate_template_csv(studies, output_path):
    fieldnames = [
        "doi",
        "title",
        "included",
        "note",
        "sample_size",
        "country",
        "male_pct",
        "female_pct",
        "race_white",
        "race_black",
        "race_hispanic",
        "race_asian",
        "race_other/mixed",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in studies:
            row = {
                "doi": s["doi"],
                "title": s.get("title", ""),
                "included": s.get("included", ""),
                "note": s.get("note", ""),
                "sample_size": "",
                "country": "",
                "male_pct": "",
                "female_pct": "",
                "race_white": "",
                "race_black": "",
                "race_hispanic": "",
                "race_asian": "",
                "race_other/mixed": "",
            }
            writer.writerow(row)

    print(f"Template CSV written to {output_path}")


def load_study_data(csv_path):
    studies = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            study = {
                "doi": row.get("doi", ""),
                "title": row.get("title", ""),
                "included": row.get("included", ""),
                "note": row.get("note", ""),
            }

            sample = row.get("sample_size", "").strip()
            study["sample_size"] = int(sample) if sample else None

            study["country"] = row.get("country", "").strip()

            male = row.get("male_pct", "").strip()
            study["male_pct"] = float(male) if male else None

            female = row.get("female_pct", "").strip()
            study["female_pct"] = float(female) if female else None

            for cat in RACE_CATEGORIES:
                key = f"race_{cat.lower()}"
                val = row.get(key, "").strip()
                study[key] = float(val) if val else None

            studies.append(study)
    return studies


def generate_report(studies_with_eligibility, output_path):
    fieldnames = [
        "doi",
        "title",
        "included",
        "sample_size",
        "sample_size_check",
        "country",
        "country_check",
        "male_pct",
        "female_pct",
        "sex_check",
        "race_white",
        "race_black",
        "race_hispanic",
        "race_asian",
        "race_other/mixed",
        "race_check",
        "eligible",
        "failures",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in studies_with_eligibility:
            study = item["study"]
            result = item["result"]
            row = {
                "doi": study.get("doi", ""),
                "title": study.get("title", ""),
                "included": study.get("included", ""),
                "sample_size": study.get("sample_size", ""),
                "sample_size_check": result.get("sample_size_check", ""),
                "country": study.get("country", ""),
                "country_check": result.get("country_check", ""),
                "male_pct": study.get("male_pct", ""),
                "female_pct": study.get("female_pct", ""),
                "sex_check": result.get("sex_check", ""),
                "eligible": result.get("eligible", ""),
                "failures": result.get("failures", ""),
            }
            for cat in ["White", "Black", "Hispanic", "Asian", "Other/Mixed"]:
                row[f"race_{cat.lower()}"] = study.get(f"race_{cat.lower()}", "")
            row["race_check"] = result.get("race_check", "")
            writer.writerow(row)

    eligible_count = sum(
        1 for item in studies_with_eligibility if item["result"]["eligible"]
    )
    total = len(studies_with_eligibility)
    print(f"\nReport written to {output_path}")
    print(f"Eligible: {eligible_count}/{total} ({100*eligible_count/total:.1f}%)")
