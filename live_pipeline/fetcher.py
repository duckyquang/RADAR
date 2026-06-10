import re, io, time, requests, xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
import threading

CROSSREF_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
NCBI_HEADERS = {"User-Agent": "RADAR/1.0 (mailto:radar@demo.edu)"}
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


def get_crossref_meta(doi: str) -> Optional[dict]:
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}", headers=CROSSREF_HEADERS, timeout=10)
        if r.status_code != 200: return None
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
        return {
            "doi": doi,
            "title": title,
            "authors": authors[:5],
            "author_str": "; ".join(authors[:5]),
            "year": year,
            "journal": container,
            "type": msg.get("type", ""),
            "publisher": msg.get("publisher", ""),
        }
    except: return None
