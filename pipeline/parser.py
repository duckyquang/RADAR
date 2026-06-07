import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


def extract_studies_from_pdf(pdf_path):
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdfplumber:
        raise ImportError("Install pdfplumber: pip install pdfplumber")
    return _extract_pdfplumber(path)


def _clean_metadata_text(text):
    """Clean garbled text from merged PDF cells (known patterns)."""
    text = text.replace('dYes', 'Yes').replace('dNo', 'No')
    text = text.replace('Yde', 'Yes').replace('Yf', 'Yes')
    text = re.sub(r'^[A-Za-z]\s*', '', text)
    return text.strip()


def _extract_pdfplumber(path):
    seen_dois = set()
    studies = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[0]
            data_rows = table[4:]

            for row in data_rows:
                refs = (row[0] or '').strip()
                titles_raw = (row[1] or '').strip()
                table1_raw = (row[4] or '').strip() if len(row) > 4 else ''
                reviewed_raw = (row[5] or '').strip() if len(row) > 5 else ''
                whom_raw = (row[6] or '').strip() if len(row) > 6 else ''

                if not refs:
                    continue

                refs_list = [
                    r.strip() for r in refs.split('\n')
                    if r.strip() and r.strip().startswith('http')
                ]
                titles_list = [t.strip() for t in titles_raw.split('\n') if t.strip()]
                table1_list = [
                    _clean_metadata_text(t)
                    for t in table1_raw.split('\n') if t.strip()
                ]
                reviewed_list = [
                    _clean_metadata_text(r)
                    for r in reviewed_raw.split('\n') if r.strip()
                ]
                whom_list = [
                    w.strip() for w in whom_raw.split('\n') if w.strip()
                ]

                n = len(refs_list)
                for i in range(n):
                    doi = refs_list[i]
                    if doi in seen_dois:
                        continue
                    seen_dois.add(doi)

                    title_text = titles_list[i] if i < len(titles_list) else ''
                    table1 = table1_list[i] if i < len(table1_list) else ''
                    reviewed = reviewed_list[i] if i < len(reviewed_list) else ''
                    whom = whom_list[i] if i < len(whom_list) else ''

                    title_clean, included, note = _parse_title_row(title_text)

                    if not included and table1 in ('Yes', 'No'):
                        included = 'Yes' if table1 == 'Yes' else 'No'

                    studies.append({
                        'doi': doi,
                        'title': title_clean,
                        'included': included,
                        'note': note,
                        'table1': table1,
                        'reviewed': reviewed,
                        'whom': whom,
                    })

    return studies


def _parse_title_row(text):
    m = re.match(r'^(.+?)\s+(Yes|No)(?:\s+(.*))?$', text)
    if m:
        return m.group(1).strip(), m.group(2), (m.group(3) or '').strip()
    return text.strip(), '', ''
