import json, statistics
from pathlib import Path
from collections import Counter

DATA = Path(__file__).parent / "data" / "obesity.json"
with open(DATA) as f:
    raw = json.load(f)

studies = raw["eligible_studies"]

CONTINENTS = {
    "USA": "North America", "CAN": "North America", "MEX": "North America",
    "GBR": "Europe", "DEU": "Europe", "FRA": "Europe", "ITA": "Europe", "ESP": "Europe",
    "NLD": "Europe", "SWE": "Europe", "NOR": "Europe", "FIN": "Europe", "PRT": "Europe",
    "AUS": "Oceania", "NZL": "Oceania",
    "CHN": "Asia", "JPN": "Asia", "TWN": "Asia", "KOR": "Asia", "HKG": "Asia", "IND": "Asia",
    "BRA": "South America",
    "ZAF": "Africa",
    "ISR": "Asia",
}

def parse_continent(country_str):
    if not country_str or country_str in ("Multicentre", "Systematic review", "NR"):
        return "Other / Unknown"
    parts = [c.strip() for c in country_str.replace("(", ",").replace(")", ",").split(",")]
    conts = set()
    for p in parts:
        p = p.strip().upper()
        if p in CONTINENTS:
            conts.add(CONTINENTS[p])
        elif len(p) == 2:
            from pipeline.config import COUNTRY_CODES
            try:
                name = COUNTRY_CODES.get(p, {}).get("name", "")
                for code, info in CONTINENTS.items():
                    if info == name or code == p:
                        conts.add(info)
            except:
                pass
    if len(conts) == 1:
        return list(conts)[0]
    elif len(conts) > 1:
        return "Multi-continent"
    return "Other / Unknown"

def parse_country_category(c):
    if not c or c in ("Multicentre", "Systematic review", "NR"):
        return "Other / Unknown"
    c = c.upper()
    if "USA" in c:
        return "USA"
    parts = [x.strip() for x in c.replace(",", " ").split()]
    if len(parts) > 2:
        return "Multi-country"
    return "Non-USA"

def parse_age(age_str):
    if not age_str or age_str in ("NR", "Adults", "20 years"):
        return None
    import re
    nums = re.findall(r"\d+\.?\d*", str(age_str).replace("(Mean)", "").replace("Mean:", "").replace("years", "").replace("year olds", ""))
    if nums:
        try:
            vals = [float(n) for n in nums]
            if len(vals) == 1:
                return vals[0]
            if "Median" in str(age_str):
                return vals[0]
            if len(vals) >= 2:
                return sum(vals) / len(vals)
        except:
            pass
    return None

def sex_status(s):
    m = s.get("male_pct")
    f = s.get("female_pct")
    if m is not None and f is not None and m >= 0 and f >= 0:
        if m > 0 and f > 0:
            return "Both sexes reported"
        elif m > 0:
            return "Male only"
        elif f > 0:
            return "Female only"
        else:
            return "Neither reported"
    return "Not reported"

def race_cats_count(s):
    fields = ["white_pct", "black_pct", "hispanic_pct", "asian_pct", "other_pct"]
    return sum(1 for f in fields if s.get(f) is not None and s[f] > 0)

def race_sum(s):
    fields = ["white_pct", "black_pct", "hispanic_pct", "asian_pct", "other_pct"]
    vals = [s.get(f, 0) or 0 for f in fields]
    return sum(vals)

# --- Per-study enrichment ---
for s in studies:
    s["continent"] = parse_continent(s.get("country", ""))
    s["country_cat"] = parse_country_category(s.get("country", ""))
    s["age_val"] = parse_age(s.get("age"))
    s["sex_status"] = sex_status(s)
    s["race_cats"] = race_cats_count(s)
    s["race_sum"] = round(race_sum(s), 1)
    s["has_sex"] = 1 if s.get("male_pct") is not None and s.get("female_pct") is not None and (s["male_pct"] > 0 or s["female_pct"] > 0) else 0
    s["has_age"] = 1 if s.get("age_val") is not None else 0
    s["has_any_race"] = 1 if s["race_cats"] > 0 else 0
    s["has_all_5_race"] = 1 if s["race_cats"] == 5 else 0

# --- Continent breakdown ---
continent_counts = Counter()
continent_counts.update(s["continent"] for s in studies)
raw["continent_breakdown"] = {k: {"count": v, "pct": round(v / len(studies) * 100, 1)} for k, v in sorted(continent_counts.items(), key=lambda x: -x[1])}

# --- Country breakdown (top 15) ---
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

def extract_countries_simple(c):
    if not c or c in ("Multicentre", "Systematic review", "NR"):
        return []
    codes_found = set()
    for part in c.replace(",", " ").replace("(", " ").replace(")", " ").split():
        part = part.strip().upper()
        if part in COUNTRY_NAMES:
            codes_found.add(part)
        elif len(part) == 2 and part.isalpha():
            codes_found.add(part)
    return list(codes_found)

all_country_codes = []
for s in studies:
    c = s.get("country", "")
    if "40 countries" in c:
        all_country_codes.append("40_countries")
        continue
    parts = c.replace(",", " ").replace("(", " ").replace(")", " ").split()
    multi = len([p for p in parts if p.strip().upper() in COUNTRY_NAMES or (len(p.strip()) == 2 and p.strip().isalpha())])
    if multi >= 3:
        all_country_codes.append("multi_country")
        continue
    for code in extract_countries_simple(c):
        all_country_codes.append(code)

country_counts = Counter(all_country_codes)
raw["top_countries"] = []
for code, count in sorted(country_counts.items(), key=lambda x: -x[1])[:15]:
    name = COUNTRY_NAMES.get(code, code.replace("_", " ").title())
    raw["top_countries"].append({"country": name, "code": code, "count": count, "pct": round(count / len(studies) * 100, 1)})

# --- Sex breakdown detail ---
sex_breakdown = Counter()
sex_breakdown.update(s["sex_status"] for s in studies)
raw["sex_breakdown"] = {k: {"count": v, "pct": round(v / len(studies) * 100, 1)} for k, v in sorted(sex_breakdown.items(), key=lambda x: -x[1])}

# --- Race category breakdown ---
race_cat_dist = Counter()
race_cat_dist.update(s["race_cats"] for s in studies)
raw["race_cats_distribution"] = {str(k): {"count": v, "pct": round(v / len(studies) * 100, 1)} for k, v in sorted(race_cat_dist.items())}

# --- Mean age (where reported) ---
ages = [s["age_val"] for s in studies if s["age_val"] is not None]
if ages:
    raw["age_summary"] = {
        "mean": round(statistics.mean(ages), 1),
        "median": round(statistics.median(ages), 1),
        "min": min(ages),
        "max": max(ages),
        "sd": round(statistics.stdev(ages), 1) if len(ages) > 1 else 0,
        "reported_n": len(ages),
        "reported_pct": round(len(ages) / len(studies) * 100, 1),
    }

# --- Sample size quartiles ---
samples = sorted([s["sample_size"] for s in studies if s.get("sample_size", 0) > 0])
raw["sample_size_quartiles"] = {
    "q1": samples[len(samples)//4] if samples else 0,
    "q2": statistics.median(samples) if samples else 0,
    "q3": samples[3*len(samples)//4] if samples else 0,
    "min": min(samples) if samples else 0,
    "max": max(samples) if samples else 0,
}

# --- Design counts ---
raw["study_design"] = dict(sorted(raw["study_design"].items(), key=lambda x: -x[1]))

# --- Per-decade breakdown ---
decades = Counter()
for s in studies:
    y = s.get("year")
    if y:
        decade = (y // 10) * 10
        decades[f"{decade}s"] += 1
raw["decade_breakdown"] = {k: {"count": v, "pct": round(v / len(studies) * 100, 1)} for k, v in sorted(decades.items())}

# --- Top journals ---
journal_counts = Counter()
for s in studies:
    j = s.get("journal", "Unknown")
    journal_counts[j] += 1
raw["top_journals"] = [{"journal": k, "count": v, "pct": round(v / len(studies) * 100, 1)}
                       for k, v in sorted(journal_counts.items(), key=lambda x: -x[1])[:10]]

# --- Eligibility criteria pass rates (among eligible studies) ---
total = len(studies)
raw["criteria_pass_rates"] = {
    "sample_size_gt_0": {"n": sum(1 for s in studies if s.get("sample_size", 0) > 0), "total": total},
    "country_valid": {"n": sum(1 for s in studies if s.get("country") and s["country"] not in ("NR", "Multicentre", "Systematic review")), "total": total},
    "sex_sum_100": {"n": sum(1 for s in studies if s["has_sex"]), "total": total},
    "all_5_race": {"n": sum(1 for s in studies if s["has_all_5_race"]), "total": total},
    "both_sex_and_race": {"n": sum(1 for s in studies if s["has_sex"] and s["has_any_race"]), "total": total},
}

# --- Race sum histogram bins ---
race_sums = [s["race_sum"] for s in studies if s["race_sum"] > 0]
raw["race_sum_distribution"] = {
    "0-25%": sum(1 for x in race_sums if x <= 25),
    "25-50%": sum(1 for x in race_sums if 25 < x <= 50),
    "50-75%": sum(1 for x in race_sums if 50 < x <= 75),
    "75-99%": sum(1 for x in race_sums if 75 < x < 100),
    "100%": sum(1 for x in race_sums if x == 100),
}

# --- Reporting trends over year ranges ---
year_bins = {"1998-2004": [], "2005-2009": [], "2010-2015": []}
for s in studies:
    y = s.get("year")
    if y:
        if y <= 2004: year_bins["1998-2004"].append(s)
        elif y <= 2009: year_bins["2005-2009"].append(s)
        else: year_bins["2010-2015"].append(s)

raw["reporting_trends"] = {}
for label, group in year_bins.items():
    n = len(group)
    raw["reporting_trends"][label] = {
        "n": n,
        "sex_reported": round(sum(1 for s in group if s["has_sex"]) / n * 100, 1) if n else 0,
        "age_reported": round(sum(1 for s in group if s["has_age"]) / n * 100, 1) if n else 0,
        "any_race": round(sum(1 for s in group if s["has_any_race"]) / n * 100, 1) if n else 0,
        "all_5_race": round(sum(1 for s in group if s["has_all_5_race"]) / n * 100, 1) if n else 0,
    }

with open(DATA, "w") as f:
    json.dump(raw, f, indent=2)

print(f"✅ Enriched {DATA.name}: {len(studies)} eligible studies")
print(f"   Added {len(raw.get('continent_breakdown',{}))} continents")
print(f"   Added {len(raw.get('top_countries',[]))} top countries")
print(f"   Added {len(raw.get('top_journals',[]))} top journals")
print(f"   Added {len(raw.get('age_summary',{}))} age summary fields")
print(f"   Added {len(raw.get('reporting_trends',{}))} year-range trends")
print(f"   Added criteria pass rates, sex breakdown, race distribution, decade breakdown, quartiles")
