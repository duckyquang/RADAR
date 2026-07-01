import re
import xml.etree.ElementTree as ET
from typing import Optional

SAMPLE_PATTERNS = [
    re.compile(r"(?:total\s+of|n\s*=|N\s*=|n\s*[=:]\s*)([\d, ]+)\s*(?:patients|participants|subjects|individuals|adults|children)", re.IGNORECASE),
    re.compile(r"(?:enrolled|included|recruited|studied)\s+(?:a\s+total\s+of\s+)?([\d, ]+)\s+(?:patients|participants|subjects)", re.IGNORECASE),
    re.compile(r"(?:study|trial|analysis|survey|cohort)\s+(?:included|enrolled|involved|recruited|comprised|consisted\s+of)\s+([\d, ]+)", re.IGNORECASE),
    re.compile(r"([\d, ]+)\s*(?:patients|participants|subjects|individuals)(?:\s+(?:were|from|with|aged|enrolled|included|recruited))", re.IGNORECASE),
    re.compile(r"(?:cohort|sample|population|group)\s+(?:comprised|consisted|included)\s+(?:of\s+)?([\d, ]+)\s+(?:patients|participants|subjects)", re.IGNORECASE),
    re.compile(r"([\d, ]+)\s+women\s+(?:and|,)\s+([\d, ]+)\s+men", re.IGNORECASE),
    re.compile(r"(?:among|of|assessed|studied)\s+([\d, ]+)\s+(?:\w+\s+){0,2}(?:healthy\s+)?(?:US\s+)?(?:women|men|patients|participants|adults|subjects)", re.IGNORECASE),
]

SEX_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:male|men|were\s+men)", re.IGNORECASE),
    re.compile(r"(?:male|men)\s*[:=]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:female|women|were\s+women)", re.IGNORECASE),
    re.compile(r"(?:female|women)\s*[:=]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE),
    re.compile(r"(?:female|women)\s*[:=]\s*(\d+)\s+\((\d+(?:\.\d+)?)\%", re.IGNORECASE),
]

RACE_PATTERNS = [
    (re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:white|caucasian)", re.IGNORECASE), "white_pct"),
    (re.compile(r"(?:white|caucasian)\s*[:=\s]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE), "white_pct"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:black|african.?american)", re.IGNORECASE), "black_pct"),
    (re.compile(r"(?:black|african.?american)\s*[:=\s]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE), "black_pct"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:hispanic|latino)", re.IGNORECASE), "hispanic_pct"),
    (re.compile(r"(?:hispanic|latino|latina|hispanic.?latino)\s*[:=\s]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE), "hispanic_pct"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:asian)", re.IGNORECASE), "asian_pct"),
    (re.compile(r"(?:asian|asian.?american)\s*[:=\s]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE), "asian_pct"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:other|mixed|multiple)\b", re.IGNORECASE), "other_pct"),
    (re.compile(r"(?:other|mixed|multiple)\s*(?:race|races)?\s*[:=\s]\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE), "other_pct"),
]

COUNTRY_PATTERNS = [
    re.compile(r"(?:United\s+States|USA|U\.S\.A\.|U\.S\.)", re.IGNORECASE),
    re.compile(r"(?:United\s+Kingdom|UK|U\.K\.|Great\s+Britain|England|Scotland|Wales)", re.IGNORECASE),
]

CONTINENTS = {
    "USA":"North America","CAN":"North America","GBR":"United Kingdom",
    "DEU":"Germany","FRA":"France","ITA":"Italy","ESP":"Spain",
    "NLD":"Netherlands","SWE":"Sweden","NOR":"Norway","FIN":"Finland",
    "CHN":"China","JPN":"Japan","AUS":"Australia","BRA":"Brazil",
    "IND":"India","ZAF":"South Africa","RUS":"Russia","KOR":"South Korea",
    "MEX":"Mexico","TWN":"Taiwan","CHE":"Switzerland","DNK":"Denmark",
    "PRT":"Portugal","AUT":"Austria","BEL":"Belgium","IRL":"Ireland",
    "NZL":"New Zealand","ISR":"Israel","POL":"Poland","GRC":"Greece",
    "TUR":"Turkey","HKG":"Hong Kong","SGP":"Singapore","ARG":"Argentina",
    "CHL":"Chile","COL":"Colombia","EGY":"Egypt","NGA":"Nigeria","KEN":"Kenya",
    "THA":"Thailand","ARE":"UAE","SAU":"Saudi Arabia","CZE":"Czech Republic",
    "ROU":"Romania","HUN":"Hungary","UKR":"Ukraine",
}

COUNTRY_CODES = {
    "United States": "USA", "USA": "USA", "U.S.A.": "USA", "U.S.": "USA",
    "United Kingdom": "GBR", "UK": "GBR", "England": "GBR", "Scotland": "GBR",
    "Germany": "DEU", "France": "FRA", "Italy": "ITA", "Spain": "ESP",
    "Canada": "CAN", "Australia": "AUS", "Japan": "JPN", "China": "CHN",
    "South Korea": "KOR", "India": "IND", "Brazil": "BRA", "Netherlands": "NLD",
    "Sweden": "SWE", "Switzerland": "CHE", "Denmark": "DNK", "Norway": "NOR",
    "Belgium": "BEL", "Austria": "AUT", "Ireland": "IRL", "New Zealand": "NZL",
    "Israel": "ISR", "South Africa": "ZAF", "Russia": "RUS", "Turkey": "TUR",
    "Poland": "POL", "Portugal": "PRT", "Greece": "GRC", "Finland": "FIN",
    "Taiwan": "TWN", "Hong Kong": "HKG", "Singapore": "SGP", "Mexico": "MEX",
    "Argentina": "ARG", "Chile": "CHL", "Colombia": "COL",
}


def _clean_num(s):
    return int(s.replace(",", "").replace(" ", ""))


def extract_all_text(element) -> str:
    return " ".join(element.itertext()).strip()


def extract_demographics_from_text(text: str) -> dict:
    result = {}
    if not text:
        return result

    sample_matches = []
    for pat in SAMPLE_PATTERNS:
        for m in pat.finditer(text):
            groups = len(m.groups())
            if groups >= 2 and m.lastindex and m.lastindex >= 2:
                try:
                    v1 = int(_clean_num(m.group(1)))
                    v2 = int(_clean_num(m.group(2)))
                    if 10 <= v1 <= 100_000_000: sample_matches.append(v1)
                    if 10 <= v2 <= 100_000_000: sample_matches.append(v2)
                    sample_matches.append(v1 + v2)
                except: pass
                continue
            try:
                val = int(_clean_num(m.group(1)))
                if 10 <= val <= 100_000_000:
                    sample_matches.append(val)
            except: pass
    if sample_matches:
        result["sample_size"] = max(sample_matches)

    male_pct = None
    female_pct = None
    for pat in SEX_PATTERNS:
        for m in pat.finditer(text):
            val = float(m.group(1))
            pl = pat.pattern.lower()
            if "male" in pl or "men" in pl:
                if 0 <= val <= 100: male_pct = val
            else:
                if 0 <= val <= 100: female_pct = val
    if male_pct is not None: result["male_pct"] = male_pct
    if female_pct is not None: result["female_pct"] = female_pct

    race_vals = {}
    for pat, key in RACE_PATTERNS:
        for m in pat.finditer(text):
            val = float(m.group(1))
            if 0 <= val <= 100:
                if key not in race_vals: race_vals[key] = val
    if race_vals:
        result.update(race_vals)

    country_matches = set()
    for pat in COUNTRY_PATTERNS:
        for m in pat.finditer(text):
            country_matches.add(m.group(0))
    if country_matches:
        result["country"] = ", ".join(country_matches)

    return result


def parse_pmc_fulltext(pmc_xml: str) -> dict:
    info = {}
    try:
        root = ET.fromstring(pmc_xml)
    except:
        return info

    # Article metadata (title, journal, year)
    article_meta = root.find(".//article-meta")
    if article_meta is not None:
        for t in article_meta.iter("article-title"):
            info["title"] = extract_all_text(t)
        for jt in article_meta.iter("journal-title"):
            info["journal"] = extract_all_text(jt)
        for yel in article_meta.iter("year"):
            try:
                info["year"] = int(yel.text)
            except: pass

    # Authors
    authors = []
    for contrib in root.iter("contrib"):
        if contrib.get("contrib-type") == "author":
            name = contrib.find("name")
            if name is not None:
                given = name.find("given-names")
                family = name.find("surname")
                g = extract_all_text(given) if given is not None else ""
                f = extract_all_text(family) if family is not None else ""
                authors.append(f"{g} {f}".strip())
    if authors:
        info["authors"] = authors[:10]

    # Affiliations
    affs = []
    for aff in root.iter("aff"):
        affs.append(extract_all_text(aff))
    if affs:
        info["affiliations"] = affs

    all_text = []
    body = root.find(".//body")
    if body is not None:
        for p in body.iter("p"):
            text = extract_all_text(p)
            if len(text) > 20:
                all_text.append(text)

        demos_from_text = extract_demographics_from_text(" ".join(all_text))
        info.update(demos_from_text)

        table_results = _parse_demographic_tables(root)
        if table_results:
            merged = dict(info)
            merged.update(table_results)
            info = merged

    return info


def _parse_demographic_tables(root) -> dict:
    result = {}
    text = extract_all_text(root)
    table_wraps = root.findall(".//table-wrap")
    for tw in table_wraps:
        caption = tw.find("caption")
        cap_text = extract_all_text(caption).lower() if caption is not None else ""
        is_demo_table = any(kw in cap_text for kw in [
            "baseline", "demographic", "characteristic", "participant", "patient",
            "study population", "enrollment", "demography"
        ])
        if not is_demo_table:
            continue

        table = tw.find(".//table")
        if table is None:
            continue

        rows = table.findall(".//tr")
        if len(rows) < 2:
            continue

        # Extract header to find which columns might have total N
        headers = []
        header_row = rows[0]
        for th in header_row.findall("th"):
            headers.append(extract_all_text(th).lower())

        # Look for N=total in header
        col_n = {}
        header_total = 0
        for i, h in enumerate(headers):
            m = re.search(r"n\s*[:=]?\s*([\d,]+)", h)
            if m:
                val = int(m.group(1).replace(",", ""))
                col_n[i] = val
                if val > 10:
                    header_total += val
        if header_total > 0:
            result["sample_size"] = header_total

        _cells = lambda el: [extract_all_text(c) for c in el.findall("td") or el.findall("th")]

        for row in rows[1:]:
            cells = _cells(row)
            if len(cells) < 2:
                continue

            row_label = cells[0].lower().strip()
            if not row_label or len(row_label) < 2:
                continue

            field = _map_row_label(row_label)
            if field is None:
                continue

            values = []
            for cell in cells[1:]:
                vals = re.findall(r"([\d,]+(?:\.\d+)?)", cell.replace("%", ""))
                if vals:
                    try:
                        values.append(float(vals[0].replace(",", "")))
                    except: pass

            if not values:
                continue

            if field == "sample_size":
                val = max(values)
                if 10 < val < 100_000_000:
                    result["sample_size"] = int(val)
                if col_n:
                    for ci, cn in col_n.items():
                        if ci > 0 and cn > 10:
                            result["sample_size"] = cn

            elif field in ("male_pct", "female_pct", "white_pct", "black_pct", "hispanic_pct", "asian_pct"):
                vals_ok = [v for v in values if v <= 100]
                if vals_ok:
                    result[field] = max(vals_ok)

        for row in rows[1:]:
            cells = _cells(row)
            if len(cells) < 2:
                continue
            rl = cells[0].lower().strip()
            if re.search(r"\b(?:female|women)\s+sex|sex\b.*\bfemale|female.*no\.|^female\b", rl):
                # Take the FIRST data cell (first arm/column)
                cell = cells[1]
                m = re.search(r"([\d,]+)\s*\((\d+(?:\.\d+)?)", cell)
                if m:
                    try:
                        pct = float(m.group(2))
                        if 0 <= pct <= 100:
                            result["female_pct"] = pct
                            if "sample_size" not in result or not result.get("sample_size"):
                                result["sample_size"] = int(m.group(1).replace(",", ""))
                    except: pass
                continue
            if re.search(r"\b(?:male|men)\s+sex|sex\b.*\b(?:male|men)|^male\b", rl):
                cell = cells[1]
                m = re.search(r"([\d,]+)\s*\((\d+(?:\.\d+)?)", cell)
                if m:
                    try:
                        pct = float(m.group(2))
                        if 0 <= pct <= 100:
                            result["male_pct"] = pct
                    except: pass
                continue

        # Race/ethnicity sub-rows: look for "Race or ethnic group" header, then parse child rows
        for i, row in enumerate(rows[1:], 1):
            cells = _cells(row)
            if not cells:
                continue
            rl = cells[0].lower().strip()
            if re.search(r"race|ethnic", rl):
                race_set = frozenset(["white_pct", "black_pct", "hispanic_pct", "asian_pct"])
                for j in range(i + 1, len(rows)):
                    sub_cells = _cells(rows[j]) if j < len(rows) else []
                    if not sub_cells or not sub_cells[0].strip():
                        continue
                    sr = sub_cells[0].lower().strip()
                    sub_field = _map_row_label(sr)
                    if sub_field in race_set:
                        if sub_field not in result:
                            _set_from_cell(result, sub_field, sub_cells)
                    elif sub_field is not None and sub_field not in race_set:
                        break

        # Post-extraction validation: reject values that are likely NOT demographic percentages
        # Check 1: M+F must sum to ~100% (±10%) if both present
        if "male_pct" in result and "female_pct" in result:
            sex_sum = result["male_pct"] + result["female_pct"]
            if sex_sum < 80 or sex_sum > 120:
                del result["male_pct"]
                del result["female_pct"]
        # Check 2: if race values are all < 2%, they're likely regression coefficients (HR/OR), not %
        race_keys_found = {k: result[k] for k in ["white_pct","black_pct","hispanic_pct","asian_pct","other_pct"] if k in result}
        if race_keys_found and all(v < 2 for v in race_keys_found.values()):
            for k in race_keys_found:
                del result[k]

    return result


def _set_from_cell(result, field, cells):
    for cell in cells[1:]:
        # Prefer N(pct) format: "120 (55.0%)" -> use 55.0
        m = re.search(r"([\d,]+)\s*\((\d+(?:\.\d+)?)", cell)
        if m:
            try:
                pct = float(m.group(2))
                if 0 <= pct <= 100:
                    result[field] = pct
                    return
            except: pass
        # Fallback: use last number <= 100, not first (first is often raw N, not %)
        m2 = re.findall(r"(\d+(?:\.\d+)?)", cell)
        if m2:
            pct_candidates = [float(x.replace(",","")) for x in m2 if float(x.replace(",","")) <= 100]
            if pct_candidates:
                result[field] = pct_candidates[-1]
                return


def _map_row_label(label: str):
    # Sample size
    if re.search(r"\bn\s*[=:]\s*\d", label) and re.search(r"(?:total|overall|all)", label):
        return "sample_size"
    if re.search(r"^number\s+(?:of\s+)?(?:patients|participants|subjects)", label):
        return "sample_size"
    if re.search(r"^(?:patients|participants|subjects|sample|cohort)", label) and re.search(r"no\.|n\s*=", label):
        return "sample_size"

    # Sex
    if re.search(r"(?:female|women|girls)", label) and re.search(r"(?:no\.?|n\s*=|%|number|pct)", label):
        return "female_pct"
    if re.search(r"(?:male|men|boys)", label) and re.search(r"(?:no\.?|n\s*=|%|number|pct)", label):
        return "male_pct"
    if re.search(r"\bsex\b.*\bfemale\b", label) or re.search(r"\bfemale\b.*\bsex\b", label):
        return "female_pct"
    if re.search(r"^female", label):
        return "female_pct"
    if re.search(r"(?:%|percent|pct)", label) and re.search(r"(?:female|women)", label):
        return "female_pct"
    if re.search(r"(?:%|percent|pct)", label) and re.search(r"(?:male|men)", label):
        return "male_pct"

    # Race
    if re.search(r"(?:non.hispanic\s+)?white\b", label) and not re.search(r"black", label):
        return "white_pct"
    if re.search(r"(?:non.hispanic\s+)?black\b", label) or re.search(r"african.american", label):
        return "black_pct"
    if re.search(r"\bhispanic\b", label):
        return "hispanic_pct"
    if re.search(r"\basian\b", label):
        return "asian_pct"
    if re.search(r"race or ethnic", label):
        return None  # section header, handled separately

    # Explicit male/female from "Male sex — no. (%)" pattern
    if re.search(r"\bsex\b", label):
        if re.search(r"(?:male|men)", label):
            return "male_pct"
        if re.search(r"(?:female|women)", label):
            return "female_pct"

    return None


def parse_pubmed_xml(xml_text: str) -> dict:
    info = {}
    try:
        root = ET.fromstring(xml_text)
        abstract_parts = []
        for at in root.iter("AbstractText"):
            label = at.get("Label", "")
            text = at.text or ""
            if label: text = f"{label}: {text}"
            for sub in at:
                if sub.text: text += " " + sub.text
                if sub.tail: text += " " + sub.tail
            if text.strip(): abstract_parts.append(text.strip())
        info["abstract"] = " ".join(abstract_parts)

        for art in root.iter("ArticleTitle"):
            info["title"] = "".join(art.itertext()).strip()

        countries = []
        for aff in root.iter("Affiliation"):
            if aff.text: countries.append(aff.text)
        info["affiliations"] = countries

        for jt in root.iter("JournalTitle"):
            info["journal"] = jt.text

        pd = root.find(".//PubDate")
        if pd is not None:
            year_el = pd.find("Year")
            if year_el is not None and year_el.text:
                info["year"] = int(year_el.text)

        article = root.find(".//Article")
        if article is not None:
            al = article.find("AuthorList")
            if al is not None:
                authors = []
                for author in al.findall("Author"):
                    last = author.find("LastName")
                    fore = author.find("ForeName")
                    if last is not None and fore is not None:
                        authors.append(f"{fore.text} {last.text}")
                    elif last is not None:
                        authors.append(last.text)
                info["authors"] = authors
    except: pass
    return info


def infer_country_from_affiliations(affiliations: list) -> Optional[str]:
    from collections import Counter
    countries = []
    for aff in affiliations:
        for name, code in COUNTRY_CODES.items():
            if name.lower() in aff.lower() or code.lower() in aff.lower():
                countries.append(code)
                break
    if not countries:
        return None
    return Counter(countries).most_common(1)[0][0]
