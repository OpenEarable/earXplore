"""Step 2 of the update pipeline: turn accepted DOIs into proposed EarXplore entries.

This part (2.1 + 2.2) needs no LLM:
  2.1 metadata  Crossref (bibliographic data) + OpenAlex (abstract) per DOI ->
                ID, Main Author, Year, Title, Authors, Abstract, Keywords, Study Link
                and a BibTeX entry in the style of datasets/bibtexs.bib
  2.2 full text the PDF from your own folder (--pdf-dir, checked first) or an
                open-access copy listed by OpenAlex; text via pypdf, reference
                list cut off

Usage:
  python git_actions_scripts/extract_studies.py dois.txt --out proposed.csv
  python git_actions_scripts/extract_studies.py --selfcheck

dois.txt: one DOI per line (lines starting with # are ignored).
Paywalled PDFs: download them yourself and save them as
  pdfs/<DOI with / replaced by _>.pdf     e.g. pdfs/10.1145_3706598.3714133.pdf
PDFs and extracted texts are never committed (copyright): pdfs/ and
extraction_work/ are in .gitignore.
"""
import argparse
import html
import os
import re
import sys
import unicodedata

import pandas as pd
import requests
from dotenv import load_dotenv
from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(__file__))
import search_candidates as search  # noqa: E402  (OpenAlex helpers, corpus DOIs)

load_dotenv()

DATA_PATH = 'datasets/data.csv'
METADATA_COLUMNS = ['ID', 'Main Author', 'Year', 'Title', 'Authors', 'Abstract', 'Keywords', 'Study Link']
BIBTEX_TYPES = {'proceedings-article': ('inproceedings', 'booktitle'),
                'journal-article': ('article', 'journal'),
                'book-chapter': ('incollection', 'booktitle')}
USER_AGENT = 'EarXplore-update-pipeline (https://github.com/OpenEarable/earXplore)'


def slug(doi):
    return doi.replace('/', '_')


# --- 2.1 metadata -------------------------------------------------------------

def fetch_crossref(doi):
    r = requests.get(f'https://api.crossref.org/works/{doi}', timeout=60, headers={'User-Agent': USER_AGENT})
    r.raise_for_status()
    return r.json()['message']


def fetch_openalex(doi):
    params = {'api_key': os.getenv('OPENALEX_API_KEY')} if os.getenv('OPENALEX_API_KEY') else {}
    try:
        return search.get(f'https://api.openalex.org/works/doi:{doi}', params)
    except requests.HTTPError:
        return {}  # not every DOI is in OpenAlex; Crossref alone still gives the metadata


def fetch_publisher(doi):
    """Springer / IEEE record (abstract, author keywords) via the search APIs, if a key is set."""
    try:
        if doi.startswith('10.1007/') and os.getenv('SPRINGER_API_KEY'):
            records = search.get('https://api.springernature.com/meta/v2/json',
                                 {'api_key': os.environ['SPRINGER_API_KEY'], 'q': f'doi:{doi}'}).get('records')
            return search.from_springer(records[0]) if records else {}
        if doi.startswith('10.1109/') and os.getenv('IEEE_API_KEY'):
            articles = search.get('https://ieeexploreapi.ieee.org/api/v1/search/articles',
                                  {'apikey': os.environ['IEEE_API_KEY'], 'doi': doi}).get('articles')
            return search.from_ieee(articles[0]) if articles else {}
    except requests.HTTPError:
        pass
    return {}


def keywords_from_text(text):
    """Author keywords as printed in the paper: ACM 'Keywords', IEEE 'Index Terms—', Springer 'Keywords:'."""
    match = re.search(r'^(?:Keywords|Additional Key Words and Phrases|Index Terms)\s*[:—–-]?\s*(.+?)'
                      r'(?:\n\s*\n|\nACM Reference Format|\n\s*I\.\s|\n\d\s|\n1 Introduction|\Z)',
                      text[:20000], re.S | re.M | re.I)
    if not match:
        return ''
    raw = re.sub(r'-\n', '-', match.group(1))          # 'visible-\nlight' -> 'visible-light'
    parts = re.split(r'\s*[,;·•]\s*', ' '.join(raw.split()).rstrip('.'))
    return ', '.join(p for p in parts if p)


def fold(name):
    """'Favre-Félix' -> 'favre-felix': for comparing names regardless of accents and case."""
    return ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c)).lower().strip()


def name_key(name):
    """(last word, first initial): 'Tobias Röddiger' and 'T. Roddiger' share a key."""
    words = fold(name).replace('.', ' ').split()
    return (words[-1], words[0][0]) if words else ('', '')


def known_authors(path=DATA_PATH):
    """{name_key: spelling} of authors already in EarXplore; ambiguous keys are left out."""
    names = pd.read_csv(path, usecols=['Authors'], dtype=str, keep_default_na=False).Authors
    by_key = {}
    for name in {n.strip() for value in names for n in value.split(',') if n.strip()}:
        by_key.setdefault(name_key(name), set()).add(name)
    return {key: spellings.pop() for key, spellings in by_key.items() if len(spellings) == 1}


def author_names(crossref, openalex, known):
    """[(full name, family name)] in paper order.

    The co-author links of the Timeline view need EXACTLY the same spelling across
    papers, so authors already in EarXplore keep their existing spelling. Other
    names come from Crossref, with accents taken from OpenAlex when they only
    differ in accents (Crossref often drops them).
    """
    openalex_names = [a['author']['display_name'] for a in openalex.get('authorships', [])
                      if (a.get('author') or {}).get('display_name')]
    names = []
    for a in crossref.get('author', []):
        if not a.get('family'):
            continue
        given, family = a.get('given', ''), a['family']
        full = f'{given} {family}'.strip()
        n_family = len(family.split())
        if name_key(full) in known:
            full = known[name_key(full)]
        else:
            # same person in OpenAlex (same last word and initial): take its accented family name
            for n in openalex_names:
                accented = ' '.join(n.split()[-n_family:])
                if name_key(n) == name_key(full) and fold(accented) == fold(family):
                    full = f'{given} {accented}'.strip()
                    break
        names.append((full, ' '.join(full.split()[-n_family:])))
    return names


def main_author(families):
    """Same style as data.csv: 'Peng', 'Buil & Hollemans', 'Kim et al.'"""
    if len(families) == 1:
        return families[0]
    if len(families) == 2:
        return f'{families[0]} & {families[1]}'
    return f'{families[0]} et al.'


def bib_escape(value):
    """Plain text -> BibTeX value: one line, no braces, LaTeX specials escaped."""
    value = ' '.join(str(value).replace('{', '').replace('}', '').split())
    return re.sub(r'(?<!\\)([&%#$_])', r'\\\1', value)


def build_entry(study_id, doi, crossref, openalex, publisher=None, text='', known=None):
    """Returns (data.csv metadata row, BibTeX entry, flags).

    Abstract: OpenAlex, else the publisher API, else Crossref.
    Keywords: the publisher API (IEEE index terms, Springer keywords), else the PDF text;
    Crossref and OpenAlex do not have author keywords.
    """
    publisher = publisher or {}
    flags = []
    authors = author_names(crossref, openalex, known or {})
    families = [family for _, family in authors]
    year = str((crossref.get('published') or crossref.get('issued') or {}).get('date-parts', [['']])[0][0])
    # Crossref keeps the part after the colon in a separate field
    title = ': '.join(' '.join(t.split()) for t in [(crossref.get('title') or [''])[0],
                                                     *(crossref.get('subtitle') or [])[:1]] if t)
    abstract = (search.from_openalex(openalex)['abstract'] if openalex else '') or publisher.get('abstract', '')
    if not abstract and crossref.get('abstract'):
        abstract = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', crossref['abstract'])).split())  # JATS -> text
    if not abstract:
        flags.append('no abstract found')
    keywords = publisher.get('keywords') or keywords_from_text(text)
    if not keywords:
        flags.append('keywords missing, fill in by hand')

    row = {
        'ID': str(study_id),
        'Main Author': main_author(families) if families else '',
        'Year': year,
        'Title': title,
        'Authors': ', '.join(full for full, _ in authors),
        'Abstract': abstract,
        'Keywords': keywords,
        'Study Link': f'https://doi.org/{doi}',
    }

    kind, container_field = BIBTEX_TYPES.get(crossref.get('type'), ('misc', 'howpublished'))
    key = f'{study_id}_{re.sub(r"[^a-z]", "", families[0].lower()) if families else "unknown"}_{year}'
    fields = [
        ('author', ' and '.join(f'{family}, {full[:-len(family)].strip()}'.strip(', ') for full, family in authors)),
        ('title', title),
        ('year', year),
        (container_field, (crossref.get('container-title') or [''])[0]),
        ('publisher', crossref.get('publisher', '')),
        ('volume', crossref.get('volume', '')),
        ('number', crossref.get('issue', '')),
        ('pages', crossref.get('page', '')),
        ('articleno', crossref.get('article-number', '')),
        ('isbn', (crossref.get('ISBN') or [''])[0]),
        ('url', f'https://doi.org/{doi}'),
        ('doi', doi),
        ('abstract', abstract),
        ('keywords', keywords),
    ]
    # url and doi stay unescaped: the app reads them as links
    lines = [f'    {name} = {{{value if name in ("url", "doi") else bib_escape(value)}}}'
             for name, value in fields if value]
    entry = f'@{kind}{{{key},\n' + ',\n'.join(lines) + '\n}'
    return row, entry, flags


# --- 2.2 PDF and full text ----------------------------------------------------

def pdf_urls(openalex):
    """Open-access PDF links listed by OpenAlex, best first."""
    best = (openalex.get('best_oa_location') or {}).get('pdf_url')
    others = [loc.get('pdf_url') for loc in openalex.get('locations') or []]
    return list(dict.fromkeys(u for u in [best, *others] if u))


def get_pdf(doi, openalex, pdf_dir, work_dir):
    """Returns (path, source) or ('', reason). Your own copy in pdf_dir always wins."""
    own = os.path.join(pdf_dir, slug(doi) + '.pdf')
    if os.path.exists(own):
        return own, 'own copy'
    path = os.path.join(work_dir, 'pdfs', slug(doi) + '.pdf')
    if os.path.exists(path):
        return path, 'downloaded earlier'
    for url in pdf_urls(openalex):
        try:
            r = requests.get(url, timeout=60, headers={'User-Agent': USER_AGENT})
        except requests.RequestException:
            continue
        # publishers often answer with an HTML page (login, bot check) instead of the PDF
        if r.ok and r.content[:5] == b'%PDF-':
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(r.content)
            return path, url
    return '', f'no open-access PDF downloadable, save it as {own}'


def strip_references(text):
    """Cut the text at the last 'References' heading (the LLM does not need the list)."""
    matches = list(re.finditer(r'^\s*(references|bibliography)\s*$', text, re.I | re.M))
    return text[:matches[-1].start()] if matches else text


def pdf_text(path):
    pages = [page.extract_text() or '' for page in PdfReader(path).pages]
    return strip_references('\n'.join(pages))


# --- pipeline -------------------------------------------------------------------

def read_dois(path):
    with open(path, encoding='utf-8') as f:
        lines = [line.strip() for line in f]
    return [search.clean_doi(line) for line in lines if line and not line.startswith('#')]


def extract(dois, pdf_dir='pdfs', work_dir='extraction_work'):
    corpus_dois = {doi for doi, _ in search.load_corpus().values()}
    known = known_authors()
    next_id = int(pd.read_csv(DATA_PATH, usecols=['ID']).ID.max()) + 1
    rows, entries = [], []
    for doi in dict.fromkeys(dois):
        if doi in corpus_dois:
            print(f'{doi}: already in EarXplore, skipped', file=sys.stderr)
            continue
        try:
            crossref = fetch_crossref(doi)
        except requests.HTTPError as e:
            print(f'{doi}: not found at Crossref ({e}), skipped', file=sys.stderr)
            continue
        openalex = fetch_openalex(doi)

        pdf, source = get_pdf(doi, openalex, pdf_dir, work_dir)
        text = ''
        if pdf:
            text = pdf_text(pdf)
            os.makedirs(os.path.join(work_dir, 'text'), exist_ok=True)
            with open(os.path.join(work_dir, 'text', slug(doi) + '.txt'), 'w', encoding='utf-8') as f:
                f.write(text)

        row, entry, flags = build_entry(next_id, doi, crossref, openalex, fetch_publisher(doi), text, known)
        if not pdf:
            flags.append(source)
        elif len(text) < 5000:
            flags.append('very little text extracted (scanned PDF?)')
        if 'arxiv.org' in source:
            flags.append('PDF is the arXiv preprint, may differ from the published version')

        rows.append({**row, 'doi': doi, 'pdf': pdf, 'pdf_source': source if pdf else '',
                     'text_chars': len(text), 'flags': '; '.join(flags)})
        entries.append(entry)
        print(f'{doi}: ID {next_id}, {row["Main Author"]} {row["Year"]}, '
              f'{len(text)} text characters, {"; ".join(flags) or "ok"}', file=sys.stderr)
        next_id += 1
    return pd.DataFrame(rows), entries


# --- self-check ---------------------------------------------------------------

def selfcheck():
    assert main_author(['Peng']) == 'Peng'
    assert main_author(['Buil', 'Hollemans']) == 'Buil & Hollemans'
    assert main_author(['Kim', 'Han', 'Oakley']) == 'Kim et al.'
    assert bib_escape('Ears & {Earables}: 94% of\n users') == r'Ears \& Earables: 94\% of users'
    assert bib_escape(r'already \& escaped') == r'already \& escaped'

    crossref = {'type': 'proceedings-article', 'title': ['BudsID: Finger Input'], 'publisher': 'ACM',
                'author': [{'given': 'Jiwan', 'family': 'Kim'}, {'given': 'Ian', 'family': 'Oakley'}],
                'published': {'date-parts': [[2025, 4, 25]]}, 'container-title': ['Proc. CHI'],
                'abstract': '<jats:p>Wireless earbuds &amp; more.</jats:p>'}
    row, entry, flags = build_entry(142, '10.1145/x', crossref, {})
    assert row['Main Author'] == 'Kim & Oakley' and row['Year'] == '2025'
    assert row['Authors'] == 'Jiwan Kim, Ian Oakley' and row['Study Link'] == 'https://doi.org/10.1145/x'
    assert row['Abstract'] == 'Wireless earbuds & more.'
    assert r'abstract = {Wireless earbuds \& more.}' in entry
    assert entry.startswith('@inproceedings{142_kim_2025,\n')
    assert '    author = {Kim, Jiwan and Oakley, Ian}' in entry and '    booktitle = {Proc. CHI}' in entry
    # the app's own BibTeX parser must be able to read the entry (one field per line)
    fields = dict(re.findall(r'^\s*(\w+)\s*=\s*\{(.*)\}\s*,?\s*$', entry, re.M))
    assert fields['doi'] == '10.1145/x' and fields['title'] == 'BudsID: Finger Input'

    # names: corpus spelling wins, otherwise Crossref with OpenAlex accents
    known = {name_key('Tobias Röddiger'): 'Tobias Röddiger'}
    cr = {'author': [{'given': 'T.', 'family': 'Roddiger'}, {'given': 'A.', 'family': 'Favre-Felix'},
                     {'given': 'Max', 'family': 'van Oort'}], 'title': ['Bitey'], 'subtitle': ['Tooth Clicks']}
    oa = {'authorships': [{'author': {'display_name': 'Antoine Favre-Félix'}}]}
    assert author_names(cr, oa, known) == [('Tobias Röddiger', 'Röddiger'), ('A. Favre-Félix', 'Favre-Félix'),
                                           ('Max van Oort', 'van Oort')]
    row, entry, _ = build_entry(9, '10.1/z', cr, oa, known=known)
    assert row['Title'] == 'Bitey: Tooth Clicks' and row['Main Author'] == 'Röddiger et al.'
    assert 'author = {Röddiger, Tobias and Favre-Félix, A. and van Oort, Max}' in entry
    assert 'Tobias Röddiger' in known_authors().values()   # real corpus spelling

    acm = 'Abstract\nWe present X.\nKeywords\nContext awareness, gaze, visible-\nlight communication, AI agents.\nACM Reference Format:\nA.'
    assert keywords_from_text(acm) == 'Context awareness, gaze, visible-light communication, AI agents'
    ieee = 'Abstract—We present X.\nIndex Terms—Earables, head gestures; IMU\n\nI. INTRODUCTION'
    assert keywords_from_text(ieee) == 'Earables, head gestures, IMU'
    springer = 'Abstract. We present X.\nKeywords: Earables · Hearing aids · Touch\n1 Introduction'
    assert keywords_from_text(springer) == 'Earables, Hearing aids, Touch'
    assert keywords_from_text('no keywords here') == ''
    row, entry, flags = build_entry(142, '10.1007/y', crossref, {}, {'abstract': 'From Springer.', 'keywords': 'A, B'})
    assert row['Abstract'] == 'From Springer.' and row['Keywords'] == 'A, B' and 'keywords = {A, B}' in entry

    text = 'Intro\nResults\nREFERENCES\n[1] A. Author ...\nAppendix\nReferences\n[2] B.'
    assert strip_references(text) == 'Intro\nResults\nREFERENCES\n[1] A. Author ...\nAppendix\n'
    assert pdf_urls({'best_oa_location': {'pdf_url': 'a'}, 'locations': [{'pdf_url': 'a'}, {'pdf_url': 'b'}, {}]}) == ['a', 'b']
    print('self-check ok')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dois', nargs='?', help='text file with one DOI per line')
    parser.add_argument('--out', default='proposed.csv', help='proposed rows (bib entries go next to it as .bib)')
    parser.add_argument('--pdf-dir', default='pdfs', help='your own PDFs, named <DOI with / as _>.pdf')
    parser.add_argument('--work-dir', default='extraction_work', help='downloaded PDFs and extracted texts')
    parser.add_argument('--selfcheck', action='store_true')
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        raise SystemExit
    if not args.dois:
        parser.error('give a file with DOIs')

    rows, entries = extract(read_dois(args.dois), args.pdf_dir, args.work_dir)
    rows.to_csv(args.out, index=False)
    bib_path = os.path.splitext(args.out)[0] + '.bib'
    with open(bib_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(entries) + '\n')
    print(f'{len(rows)} studies written to {args.out} and {bib_path}', file=sys.stderr)
