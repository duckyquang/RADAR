import re, io, time, requests, json, xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
import threading

CROSSREF_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
NCBI_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
OPENALEX_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
UNPAYWALL_EMAIL = "radar@demo.edu"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

_ncbi_lock = threading.Lock()
_ncbi_last_call = 0.0
NCBI_MIN_INTERVAL = 0.35  # ~3 calls per second


def _ncbi_rate_limit():
    global _ncbi_last_call
    with _ncbi_lock:
        now = time.time()
        since = now - _ncbi_last_call
        if since < NCBI_MIN_INTERVAL:
            time.sleep(NCBI_MIN_INTERVAL - since)
        _ncbi_last_call = time.time()


def search_pubmed(query: str) -> Optional[str]:
    try:
        _ncbi_rate_limit()
        r = requests.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={requests.utils.quote(query)}&retmax=5&retmode=json",
            timeout=10, headers=NCBI_HEADERS
        )
        if r.status_code == 200:
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            if ids:
                return ids[0]
    except: pass
    return None


def search_pubmed_by_doi(doi: str) -> Optional[str]:
    return search_pubmed(f"{doi}[DOI]")


def fetch_pubmed_xml(pmid: str) -> Optional[str]:
    try:
        _ncbi_rate_limit()
        r = requests.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml",
            timeout=15, headers=NCBI_HEADERS
        )
        if r.status_code == 200 and "<PubmedArticle>" in r.text:
            return r.text
    except: pass
    return None


def pmid_to_pmcid(pmid: str) -> Optional[str]:
    try:
        _ncbi_rate_limit()
        r = requests.get(
            f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json&tool=RADAR&email=radar@demo.edu",
            timeout=10, headers=NCBI_HEADERS
        )
        if r.status_code == 200:
            recs = r.json().get("records", [])
            if recs:
                pmcid = recs[0].get("pmcid")
                if pmcid:
                    return pmcid
    except: pass
    return None


def fetch_pmc_fulltext(pmcid: str) -> Optional[str]:
    try:
        _ncbi_rate_limit()
        r = requests.get(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid}&retmode=xml",
            timeout=20, headers=NCBI_HEADERS
        )
        if r.status_code == 200 and "<body>" in r.text and len(r.text) > 1000:
            return r.text
    except: pass
    return None


_crossref_cache: dict[str, Optional[dict]] = {}

def get_crossref_meta(doi: str) -> Optional[dict]:
    if doi in _crossref_cache:
        return _crossref_cache[doi]
    result = None
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=CROSSREF_HEADERS, timeout=10)
        if r.status_code == 200:
            msg = r.json().get("message", {})
            title = msg.get("title", [None])
            if isinstance(title, list): title = title[0] if title else None
            authors = []
            for a in msg.get("author", []):
                name = f"{a.get('given','')} {a.get('family','')}".strip()
                if name: authors.append(name)
            container = msg.get("container-title", [None])
            if isinstance(container, list): container = container[0] if container else None
            pub_date = msg.get("published-print", {}).get("date-parts", [[None]])[0]
            if not pub_date or pub_date == [None]:
                pub_date = msg.get("published-online", {}).get("date-parts", [[None]])[0]
            year = pub_date[0] if pub_date and pub_date[0] else None
            result = {
                "doi": doi,
                "title": title,
                "authors": authors[:5],
                "author_str": "; ".join(authors[:5]),
                "year": year,
                "journal": container,
                "type": msg.get("type", ""),
                "publisher": msg.get("publisher", ""),
            }
    except: pass
    _crossref_cache[doi] = result
    return result


# --- Unpaywall ---
def search_unpaywall(doi: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}",
            timeout=10
        )
        if r.status_code != 200:
            return None
        data = r.json()
        oa_location = data.get("best_oa_location") or data.get("oa_locations", [None]) or [None]
        if isinstance(oa_location, list):
            oa_location = oa_location[0]
        if oa_location:
            landing = oa_location.get("url_for_landing_page", "")
            pdf = oa_location.get("url_for_pdf", "")
            return {
                "is_oa": data.get("is_oa", False),
                "oa_status": data.get("oa_status", "unknown"),
                "landing_url": landing,
                "pdf_url": pdf,
                "host_type": oa_location.get("host_type", ""),
                "publisher": oa_location.get("publisher", ""),
            }
        return {"is_oa": False, "oa_status": "closed"}
    except:
        return None


def get_fulltext_via_unpaywall(doi: str) -> Optional[str]:
    """Try fetching full-text XML/HTML via Unpaywall landing page."""
    up = search_unpaywall(doi)
    if not up or not up.get("is_oa"):
        return None
    pdf_url = up.get("pdf_url", "")
    landing_url = up.get("landing_url", "")
    if pdf_url:
        try:
            r = requests.get(pdf_url, timeout=15)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
        except:
            pass
    return None


# --- OpenAlex ---
def search_openalex(doi: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"https://api.openalex.org/works/doi:{doi}",
            headers=OPENALEX_HEADERS, timeout=10
        )
        if r.status_code != 200:
            return None
        data = r.json()
        authorships = data.get("authorships", [])
        author_names = []
        author_countries = set()
        institutions = []
        for a in authorships:
            name = a.get("author", {}).get("display_name", "")
            if name:
                author_names.append(name)
            for inst in a.get("institutions", []):
                country = inst.get("country_code", "")
                if country:
                    author_countries.add(country)
                inst_name = inst.get("display_name", "")
                if inst_name:
                    institutions.append(inst_name)
        primary_location = data.get("primary_location", {})
        source = primary_location.get("source", {}) if primary_location else {}
        return {
            "title": data.get("title", ""),
            "authors": author_names[:10],
            "author_str": "; ".join(author_names[:5]),
            "year": data.get("publication_year"),
            "journal": source.get("display_name", ""),
            "publisher": source.get("publisher", ""),
            "type": data.get("type", ""),
            "author_countries": list(author_countries),
            "institutions": institutions[:5],
            "cited_by_count": data.get("cited_by_count", 0),
            "is_oa": data.get("is_oa", False),
            "primary_location_url": (primary_location or {}).get("landing_page_url", ""),
        }
    except:
        return None
