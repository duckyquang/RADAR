from .config import COUNTRY_VALID_CODES, RACE_CATEGORIES, SEX_TOLERANCE, RACE_TOLERANCE


def check_sample_size(n):
    if n is None:
        return False, "Missing"
    try:
        n = int(n)
        return n > 0, str(n)
    except (ValueError, TypeError):
        return False, f"Invalid: {n}"


def check_country(country):
    if not country or str(country).strip() == "":
        return False, "Missing"
    country_str = str(country).strip()
    if country_str.upper() in {c.upper() for c in COUNTRY_VALID_CODES}:
        return True, country_str
    return False, f"Invalid: {country_str}"


def check_sex_data(male_pct, female_pct):
    if male_pct is None or female_pct is None:
        return False, "Missing"
    try:
        m = float(male_pct)
        f = float(female_pct)
    except (ValueError, TypeError):
        return False, f"Invalid M:{male_pct} F:{female_pct}"

    total = m + f
    if abs(total - 100) <= SEX_TOLERANCE:
        return True, f"M:{m:.1f} F:{f:.1f} Sum:{total:.1f}"
    return False, f"M:{m:.1f} F:{f:.1f} Sum:{total:.1f} (off by {abs(total-100):.1f})"


def check_race_data(race_dict):
    missing = [cat for cat in RACE_CATEGORIES if cat not in race_dict or race_dict[cat] is None]
    if missing:
        return False, f"Missing categories: {missing}"

    try:
        values = {k: float(v) for k, v in race_dict.items()}
    except (ValueError, TypeError):
        return False, f"Invalid values: {race_dict}"

    total = sum(values.values())
    if abs(total - 100) <= RACE_TOLERANCE:
        details = " ".join(f"{k}:{v}" for k, v in values.items())
        return True, f"{details} Sum:{total:.1f}"
    return False, f"Sum:{total:.1f} (off by {abs(total-100):.1f})"


def determine_eligibility(study):
    results = {}

    sample_ok, sample_msg = check_sample_size(study.get("sample_size"))
    results["sample_size_check"] = sample_ok
    results["sample_size_detail"] = sample_msg

    country_ok, country_msg = check_country(study.get("country"))
    results["country_check"] = country_ok
    results["country_detail"] = country_msg

    sex_ok, sex_msg = check_sex_data(
        study.get("male_pct"), study.get("female_pct")
    )
    results["sex_check"] = sex_ok
    results["sex_detail"] = sex_msg

    race_dict = {}
    for cat in RACE_CATEGORIES:
        race_dict[cat] = study.get(f"race_{cat.lower()}")
    race_ok, race_msg = check_race_data(race_dict)
    results["race_check"] = race_ok
    results["race_detail"] = race_msg

    all_ok = sample_ok and country_ok and sex_ok and race_ok
    results["eligible"] = all_ok

    failures = []
    if not sample_ok:
        failures.append("sample_size")
    if not country_ok:
        failures.append("country")
    if not sex_ok:
        failures.append("sex")
    if not race_ok:
        failures.append("race")
    results["failures"] = ", ".join(failures) if failures else ""

    return results
