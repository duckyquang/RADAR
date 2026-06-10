import re
import io
from typing import List, Optional

import pdfplumber


REF_SECTION_PATTERNS = [
    re.compile(r"(?:^|\n)\s*(?:REFERENCES|BIBLIOGRAPHY|WORKS\s+CITED|REFERENCES\s+CITED)\s*\n", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*(?:REFERENCES|REFERENCES\s+AND\s+NOTES)\s*\n", re.IGNORECASE),
]

DOI_PATTERN = re.compile(r"(?:doi|DOI|Doi)\s*[:\s]\s*(10\.\d{4,}/[^\s,;)\]}>]+)", re.IGNORECASE)
DOI_URL_PATTERN = re.compile(r"https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s,;)\]}>]+)")


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    text_pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_pages.append(t)
    return "\n".join(text_pages)


def find_reference_section(text: str) -> Optional[int]:
    for pat in REF_SECTION_PATTERNS:
        m = pat.search(text)
        if m:
            return m.end()
    return None


REF_NUMBERED = re.compile(r"^\[?(\d+)\]?\.?\s{1,3}(?=[A-Z])", re.MULTILINE)
REF_NUMBERED_NOPAREN = re.compile(r"^(\d+)\.\s+(?=[A-Z\"])", re.MULTILINE)
REF_NUMBERED_PAREN = re.compile(r"^\((\d+)\)\s+(?=[A-Z])", re.MULTILINE)


def split_references(text: str) -> List[str]:
    lines = text.split("\n")
    refs = []
    current = []
    in_refs = False

    for i, line in enumerate(lines):
        if re.match(r"^\s*(?:REFERENCES|BIBLIOGRAPHY|WORKS\s+CITED)\s*$", line, re.IGNORECASE):
            in_refs = True
            continue
        if not in_refs:
            continue

        if re.match(r"^\s*(?:APPENDIX|SUPPLEMENT|FIGURES?\s*AND?\s*TABLES?|AUTHOR\s+CONTRIBUTIONS|ACKNOWLEDGMENTS?|DISCLOSURE|FUNDING|CONFLICT)", line, re.IGNORECASE):
            break
        if re.match(r"^\s*$", line):
            if current:
                refs.append(" ".join(current))
                current = []
            continue

        stripped = line.strip()
        if stripped:
            current.append(stripped)

    if current:
        refs.append(" ".join(current))
    return refs


def extract_doi(ref_text: str) -> Optional[str]:
    m = DOI_PATTERN.search(ref_text)
    if m:
        return m.group(1).rstrip(".")
    m = DOI_URL_PATTERN.search(ref_text)
    if m:
        return m.group(1).rstrip(".")
    return None


def parse_reference(ref_text: str) -> dict:
    result = {"raw": ref_text, "doi": extract_doi(ref_text)}

    year_match = re.search(r"(?:\((\d{4})\)|\.\s*(\d{4})\s*[;:]|(\d{4})\s*[;])", ref_text)
    if year_match:
        result["year"] = int(year_match.group(1) or year_match.group(2) or year_match.group(3))

    title_match = re.search(r"(?:\.\s+|\d+\.\s+)([A-Z][^.]+?)\.\s+(?:(?:[A-Z][a-z]+\s*)+|The\s+[A-Z])", ref_text)
    if title_match:
        potential = title_match.group(1).strip()
        if len(potential) > 20 and not potential.startswith("http"):
            result["title_partial"] = potential[:150]

    volume_match = re.search(r"(?:;\s*|,\s*)(\d+)\s*[\(:]", ref_text)
    if volume_match:
        result["volume"] = volume_match.group(1)

    return result


def extract_all_references(pdf_bytes: bytes) -> List[dict]:
    text = extract_text_from_pdf(pdf_bytes)
    refs = split_references(text)
    results = []
    seen = set()
    for ref in refs:
        if len(ref) < 30:
            continue
        parsed = parse_reference(ref)
        doi = parsed.get("doi")
        if doi and doi in seen:
            continue
        if doi:
            seen.add(doi)
        results.append(parsed)
    return results
